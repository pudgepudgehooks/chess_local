from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import chess

from beta_store import BetaStore, puzzles, events
from puzzle_store import load_library, save_library, merge_puzzles, record_review, deduplicate_puzzles
from sqlalchemy import select, func


def mistake(pid='first', url='https://www.chess.com/game/live/123'):
    return dict(id=pid, username='Me', opponent='Other', date='2026.08.01',
                game_url=url, fen=chess.STARTING_FEN, played='e2e4', best_move='d2d4',
                accepted_moves=['d2d4'], solution=['d2d4', 'd7d5'], loss=300,
                move_number=1)


class GenerationTests(unittest.TestCase):
    def test_duplicate_reviews_and_lichess_exports_are_consolidated(self):
        first = mistake('first', 'https://lichess.org/Abcd1234/white')
        second = mistake('exported', 'https://lichess.org/Abcd1234zzzz?analysis=1')
        record_review(first, True, datetime(2026, 11, 1, tzinfo=timezone.utc))
        record_review(second, False, datetime(2026, 11, 2, tzinfo=timezone.utc))
        latest = deepcopy(second['review'])
        unique, aliases = deduplicate_puzzles([first, second])
        self.assertEqual(aliases, {'exported': 'first'})
        self.assertEqual(len(unique), 1)
        self.assertEqual(unique[0]['review']['attempts'], 2)
        self.assertEqual(unique[0]['review']['correct'], 1)
        self.assertEqual(unique[0]['review']['next_review'], latest['next_review'])
        self.assertEqual(unique[0]['review']['streak'], 0)

    def test_local_duplicates_merge_without_losing_reviews_or_distinct_games(self):
        first = mistake()
        record_review(first, True)
        review = deepcopy(first['review'])
        library = dict(version=1, puzzles=[first, deepcopy(first)])
        imported = mistake('different-export-id', 'http://chess.com/live/game/123?source=pgn#board')
        imported['username'] = 'me'
        self.assertEqual(merge_puzzles(library, [imported, deepcopy(imported)]), 0)
        self.assertEqual(len(library['puzzles']), 1)
        self.assertEqual(library['puzzles'][0]['id'], 'first')
        self.assertEqual(library['puzzles'][0]['review'], review)
        other_game = mistake('another-game', 'https://www.chess.com/game/live/456')
        self.assertEqual(merge_puzzles(library, [other_game]), 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'puzzles.json'
            save_library(library, path)
            loaded = load_library(path)
            self.assertEqual(len(loaded['puzzles']), 2)
            self.assertEqual(loaded['puzzles'][0]['review'], review)

    def test_beta_reanalysis_and_historical_duplicates_keep_owner_and_review_events(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BetaStore('sqlite:///' + str(Path(directory) / 'beta.db'))
            try:
                payload = {'sample': 1}
                store.submit('alice', payload)
                store.finish(store.claim(), [mistake(), mistake('second-id')])
                self.assertEqual(len(store.load('alice')['puzzles']), 1)
                first = store.review('alice', 'first', True, 'first-event')
                store.submit('alice', {'sample': 2})
                store.finish(store.claim(), [mistake('new-id', 'https://chess.com/live/game/123')])
                self.assertEqual(store.recent_jobs('alice')[0]['message'], 'Added 0 puzzles. Your library is up to date.')
                self.assertEqual(store.load('alice')['puzzles'][0]['review'], first['review'])
                # Simulate old duplicate rows already saved by a previous version.
                with store.engine.begin() as db:
                    duplicate = mistake('historical-id')
                    duplicate['review'] = deepcopy(first['review'])
                    db.execute(puzzles.insert().values(owner='alice', id=duplicate['id'], data=json.dumps(duplicate)))
                    db.execute(events.insert().values(owner='alice', event='historical-event', puzzle_id=duplicate['id'], created=1))
                    db.execute(puzzles.insert().values(owner='bob', id=duplicate['id'], data=json.dumps(duplicate)))
                loaded = store.load('alice')['puzzles']
                self.assertEqual(len(loaded), 1)
                self.assertEqual(loaded[0]['review'], first['review'], 'identical copied review is counted once')
                with store.engine.connect() as db:
                    self.assertEqual(db.scalar(select(func.count()).select_from(puzzles).where(puzzles.c.owner == 'alice')), 1)
                    self.assertEqual(db.scalar(select(events.c.puzzle_id).where(events.c.owner == 'alice', events.c.event == 'historical-event')), 'first')
                self.assertEqual(len(store.load('bob')['puzzles']), 1)
                self.assertEqual(store.review('alice', 'first', True, 'historical-event')['review'], first['review'])
            finally:
                store.engine.dispose()

    def test_generate_refreshes_library_automatically_when_background_job_finishes(self):
        from streamlit.testing.v1 import AppTest
        pgn = '[White "Me"]\n[Black "Other"]\n\n1. e4 e5 *'
        with tempfile.TemporaryDirectory() as directory:
            store = BetaStore('sqlite:///' + str(Path(directory) / 'beta.db'))
            code = "from beta_store import BetaStore, UserLibrary\nfrom visualization_all import main\nmain(UserLibrary(BetaStore('test'), 'alice'))"
            try:
                with patch('beta_store.BetaStore', return_value=store), \
                     patch('visualization_all.fetch_chesscom_pgn', return_value={'games': [{'pgn': pgn}]}), \
                     patch('drag_board.drag_board', return_value=None):
                    app = AppTest.from_string(code).run(timeout=30)
                    app.text_input(key='analysis_username').set_value('Me')
                    app.button(key='generate_puzzles').click().run()
                    self.assertFalse(app.exception)
                    job = store.claim()
                    self.assertIsNotNone(job)
                    self.assertFalse(any(b.key == 'open-puzzle-first' for b in app.button))
                    store.finish(job, [mistake(), mistake('duplicate')])
                    app.run()
                    self.assertFalse(app.exception)
                    self.assertEqual(app.session_state['analysis_library_loaded_job'], ('alice', job['id']))
                    self.assertTrue(any(b.key == 'open-puzzle-first' for b in app.button))
                    self.assertFalse(any(b.key == 'refresh_library' for b in app.button))
                    self.assertEqual(app.session_state['review_cycle']['ids'], ['first'])
                    token = app.session_state['review_cycle']['token']
                    app.run()
                    self.assertEqual(app.session_state['review_cycle']['token'], token)
                    self.assertEqual(len(store.load('alice')['puzzles']), 1)
            finally:
                store.engine.dispose()
