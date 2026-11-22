from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from analysis_cache import plan_analysis, coverage_records, LOCAL_POLICY
from beta_store import BetaStore, jobs
from review_setup import prepare_start
from sqlalchemy import update


def pgn(index=1):
    return f'[White "Me"]\n[Black "Other"]\n[Date "2026.08.01"]\n[Site "https://www.chess.com/game/live/{index}"]\n\n1. e4 e5 *'


class AnalysisCoverageTests(unittest.TestCase):
    def test_incomplete_engine_output_is_not_recorded_as_completed(self):
        from beta_worker import run_job
        with tempfile.TemporaryDirectory() as directory:
            store = BetaStore('sqlite:///' + str(Path(directory) / 'cache.db'))
            try:
                store.prepare_analysis('alice', 'Me', [pgn()], 10, 100)
                with patch('chess.engine.SimpleEngine.popen_uci') as engine:
                    engine.return_value.__enter__.return_value.analyse.return_value = []
                    with self.assertLogs('beta_worker', level='ERROR'):
                        run_job(store, store.claim(), 'fake-engine')
                self.assertEqual(store.coverage('alice'), [])
                self.assertEqual(store.recent_jobs('alice')[0]['state'], 'failed')
            finally:
                store.engine.dispose()

    def test_threshold_depth_and_game_content_must_all_be_covered(self):
        records = coverage_records('Me', [pgn()], 10, 100, LOCAL_POLICY)
        plan = lambda threshold, depth=10, texts=None: plan_analysis('me', texts or [pgn()], records, depth, threshold, LOCAL_POLICY)
        self.assertEqual(plan(200)['selected'], 0)
        self.assertEqual(plan(50)['selected'], 1)
        self.assertEqual(plan(200, 12)['selected'], 1)
        records.extend(coverage_records('Me', [pgn()], 12, 200, LOCAL_POLICY))
        self.assertEqual(plan(100, 12)['selected'], 1, 'separate searches must not create imaginary combined coverage')
        self.assertEqual(plan(200, 12)['selected'], 0)
        self.assertEqual(plan(200, texts=[pgn().replace('e4 e5 *', 'e4 e5 2. Nf3 *')])['selected'], 1)
        self.assertEqual(plan(200, texts=[pgn(2)])['selected'], 1)

    def test_beta_zero_puzzle_games_cache_and_new_games_fill_next_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BetaStore('sqlite:///' + str(Path(directory) / 'cache.db'))
            try:
                texts = [pgn(i) for i in range(7)]
                first = store.prepare_analysis('alice', 'Me', texts, 10, 100)
                self.assertEqual((first['reused'], first['selected'], first['remaining']), (0, 5, 2))
                store.finish(store.claim(), [])
                second = store.prepare_analysis('alice', 'Me', texts, 10, 200)
                self.assertEqual((second['reused'], second['selected'], second['remaining']), (5, 2, 0))
                store.finish(store.claim(), [])
                third = store.prepare_analysis('alice', 'Me', texts, 10, 200)
                self.assertIsNone(third['job_id'])
                self.assertEqual(third['reused'], 7)
                self.assertEqual(store.coverage('bob'), [])
                lower = store.prepare_analysis('alice', 'Me', texts, 10, 50)
                self.assertEqual(lower['selected'], 5)
                store.finish(store.claim(), [], error='Test failure')
                self.assertFalse(any(r['threshold'] == 50 for r in store.coverage('alice')))
            finally:
                store.engine.dispose()

    def test_old_completed_job_without_coverage_is_not_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BetaStore('sqlite:///' + str(Path(directory) / 'cache.db'))
            try:
                from beta_worker import validate_payload
                from analysis_cache import game_items
                texts = [game_items('Me', [pgn()])[0]['text']]
                old = store.submit('alice', validate_payload('Me', texts, 10, 100))
                with store.engine.begin() as db:
                    db.execute(update(jobs).where(jobs.c.id == old).values(state='done', payload='{}'))
                plan = store.prepare_analysis('alice', 'Me', texts, 10, 100)
                self.assertNotEqual(plan['job_id'], old)
                self.assertEqual(plan['selected'], 1)
            finally:
                store.engine.dispose()

    def test_local_reuse_does_not_launch_stockfish_or_require_its_path(self):
        library = dict(version=1, puzzles=[])
        setup = dict(source='Chess.com month', username='Me', start=date(2026, 8, 1),
                     end=date(2026, 8, 31), threshold=100, depth=10, due_only=False, import_limit=100)
        with patch('chess_analysis.fetch_chesscom_range', return_value=[pgn()]), \
             patch('chess_analysis.engine_path', return_value='engine') as path, \
             patch('chess.engine.SimpleEngine.popen_uci') as engine, \
             patch('chess_analysis.analyze_game', return_value=[]), \
             patch('puzzle_store.save_library') as save:
            first = prepare_start(library, setup, executable='engine')
            self.assertEqual(first['selected'], 1)
            second = prepare_start(library, dict(setup, threshold=200))
            self.assertEqual((second['reused'], second['selected']), (1, 0))
            self.assertEqual(engine.call_count, 1)
            self.assertEqual(path.call_count, 1)
            self.assertEqual(save.call_count, 1)
            prepare_start(library, dict(setup, threshold=50), executable='engine')
            self.assertEqual(engine.call_count, 2)
