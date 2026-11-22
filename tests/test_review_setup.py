from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import chess

from beta_store import BetaStore
from beta_worker import validate_payload
from test_analysis_cache import pgn


def mistake():
    return dict(id='chosen', username='Me', opponent='Other', date='2026.08.01',
                game_url='https://www.chess.com/game/live/1', fen=chess.STARTING_FEN,
                played='e2e4', best_move='d2d4', accepted_moves=['d2d4'],
                solution=['d2d4', 'd7d5'], loss=150, move_number=1, platform='Chess.com')


def enter_settings(app, threshold):
    app.text_input(key='analysis_username').set_value('Me')
    app.date_input(key='analysis_start_date').set_value(date(2026, 8, 1))
    app.date_input(key='analysis_end_date').set_value(date(2026, 8, 31))
    app.number_input(key='analysis_threshold').set_value(threshold)
    app.checkbox(key='due_only').uncheck()
    app.run()
    return app


class ReviewSetupUITests(unittest.TestCase):
    def test_single_sidebar_start_and_cached_higher_threshold(self):
        from streamlit.testing.v1 import AppTest
        library = dict(version=1, puzzles=[])
        with patch('visualization_all.load_library', return_value=library), \
             patch('puzzle_store.save_library'), \
             patch('chess_analysis.fetch_chesscom_range', return_value=[pgn()]) as fetch, \
             patch('chess_analysis.engine_path', return_value='engine'), \
             patch('chess.engine.SimpleEngine.popen_uci') as engine, \
             patch('chess_analysis.analyze_game', side_effect=lambda *args, **kwargs: [mistake()]), \
             patch('drag_board.drag_board', return_value=None):
            app = AppTest.from_string('from visualization_all import main\nmain()', default_timeout=30).run(timeout=30)
            self.assertFalse(app.exception)
            self.assertTrue(any('click Start reviewing' in item.value for item in app.info))
            self.assertFalse(any(b.key == 'next_puzzle' for b in app.button))
            self.assertTrue(app.sidebar.button(key='start_review'))
            self.assertFalse(app.main.number_input)
            self.assertFalse(app.main.selectbox)
            enter_settings(app, 100)
            engine.assert_not_called()
            app.button(key='start_review').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['review_setup']['threshold'], 100)
            self.assertEqual(app.session_state['review_cycle']['ids'], ['chosen'])
            token = app.session_state['review_cycle']['token']
            app.number_input(key='analysis_threshold').set_value(200).run()
            self.assertEqual(app.session_state['review_setup']['threshold'], 100)
            self.assertEqual(app.session_state['review_cycle']['token'], token, 'draft edits cannot interrupt practice')
            app.button(key='start_review').click().run()
            self.assertEqual(app.session_state['review_setup']['threshold'], 200)
            self.assertEqual(app.session_state['review_plan']['reused'], 1)
            self.assertEqual(engine.call_count, 1, 'raising 100 to 200 only filters saved results')
            self.assertFalse(any(b.key == 'open-puzzle-chosen' for b in app.button))
            app.number_input(key='analysis_threshold').set_value(50).run()
            app.button(key='start_review').click().run()
            self.assertEqual(engine.call_count, 2, 'lowering the minimum must find previously unsaved mistakes')
            self.assertEqual(len(library['puzzles']), 1)
            self.assertEqual(fetch.call_args.kwargs['max_games'], 100)

    def test_beta_waits_for_analysis_and_failure_keeps_previous_selection(self):
        from streamlit.testing.v1 import AppTest
        with tempfile.TemporaryDirectory() as directory:
            store = BetaStore('sqlite:///' + str(Path(directory) / 'beta.db'))
            try:
                store.submit('alice', validate_payload('Me', [pgn()], 10, 100))
                store.finish(store.claim(), [mistake()])
                code = "from beta_store import BetaStore, UserLibrary\nfrom visualization_all import main\nmain(UserLibrary(BetaStore('test'), 'alice'))"
                with patch('beta_store.BetaStore', return_value=store), \
                     patch('chess_analysis.fetch_chesscom_range', return_value=[pgn()]), \
                     patch('drag_board.drag_board', return_value=None), \
                     patch('chess.engine.SimpleEngine.popen_uci') as engine:
                    app = AppTest.from_string(code, default_timeout=30).run(timeout=30)
                    enter_settings(app, 200)
                    app.button(key='start_review').click().run()
                    self.assertFalse(app.exception)
                    self.assertEqual(app.session_state['review_plan']['reused'], 1)
                    self.assertEqual(len(store.recent_jobs('alice')), 1)
                    engine.assert_not_called()
                    app.number_input(key='analysis_threshold').set_value(50).run()
                    app.button(key='start_review').click().run()
                    self.assertEqual(app.session_state['pending_review_setup']['threshold'], 50)
                    self.assertEqual(app.session_state['review_setup']['threshold'], 200)
                    self.assertTrue(app.button(key='start_review').disabled)
                    job = store.claim()
                    store.finish(job, [mistake()])
                    app.run()
                    self.assertFalse(app.exception)
                    self.assertNotIn('pending_review_setup', app.session_state)
                    self.assertEqual(app.session_state['review_setup']['threshold'], 50)
                    self.assertEqual(app.session_state['active_id'], 'chosen')
                    app.number_input(key='analysis_depth').set_value(11).run()
                    app.button(key='start_review').click().run()
                    store.finish(store.claim(), [], error='Test analysis failed')
                    app.run()
                    self.assertEqual(app.session_state['review_setup']['depth'], 10)
                    self.assertEqual(app.session_state['review_setup']['threshold'], 50)
                    self.assertNotIn('pending_review_setup', app.session_state)
                    self.assertTrue(any('Test analysis failed' in item.value for item in app.error))
                    self.assertFalse(any(r['depth'] == 11 for r in store.coverage('alice')))
            finally:
                store.engine.dispose()
