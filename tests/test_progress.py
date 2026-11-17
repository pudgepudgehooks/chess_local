from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from chess_analysis import analyze_game, read_games, count_player_moves
from test_trainer import FakeEngine, PGN


class AnalysisProgressTests(unittest.TestCase):
    def test_progress_tracks_only_the_selected_players_moves(self):
        game = next(read_games(PGN))
        for player in ['Me', 'Opponent']:
            with self.subTest(player=player):
                reports = []
                analyze_game(game, player, FakeEngine(), on_progress=lambda done, total: reports.append((done, total)))
                self.assertEqual(reports, [(0, 2), (1, 2), (2, 2)])
        self.assertEqual(count_player_moves(game, 'SomeoneElse'), 0)

    def test_failed_analysis_does_not_report_completion(self):
        reports = []
        engine = FakeEngine()
        with patch.object(engine, 'analyse', side_effect=RuntimeError('Engine stopped')):
            with self.assertRaises(RuntimeError):
                analyze_game(next(read_games(PGN)), 'Me', engine,
                             on_progress=lambda done, total: reports.append((done, total)))
        self.assertEqual(reports, [(0, 2)])


class StoredProgressTests(unittest.TestCase):
    def setUp(self):
        from beta_store import BetaStore
        self.temp = tempfile.TemporaryDirectory()
        self.store = BetaStore('sqlite:///' + str(Path(self.temp.name) / 'progress.db'))
        self.store.submit('alice', {'username': 'Me', 'texts': [PGN], 'depth': 5, 'threshold': 150})

    def tearDown(self):
        self.store.engine.dispose()
        self.temp.cleanup()

    def test_progress_is_private_persistent_and_stale_workers_cannot_write(self):
        from sqlalchemy import update
        from beta_store import BetaStore, jobs
        job = self.store.claim()
        self.store.progress(job, 0, games_total=1, game_index=1, positions_done=1, positions_total=2)
        other = BetaStore(str(self.store.engine.url))
        try:
            self.assertEqual(other.recent_jobs('bob'), [])
            self.assertEqual(other.recent_jobs('alice')[0]['positions_done'], 1)
        finally:
            other.engine.dispose()
        with self.store.engine.begin() as db:
            db.execute(update(jobs).where(jobs.c.id == job['id']).values(lease=0))
        recovered = self.store.claim()
        self.store.progress(job, 1, games_total=1, game_index=1, positions_done=2, positions_total=2)
        self.assertIsNone(self.store.recent_jobs('alice')[0]['positions_done'])
        self.store.progress(recovered, 0, games_total=1, game_index=1, positions_done=0, positions_total=2)
        self.assertEqual(self.store.recent_jobs('alice')[0]['positions_done'], 0)

    def test_worker_stores_move_totals(self):
        from beta_worker import run_job
        with patch('beta_worker.chess.engine.SimpleEngine.popen_uci') as engine:
            fake = FakeEngine()
            fake.configure = lambda options: None
            engine.return_value.__enter__.return_value = fake
            run_job(self.store, self.store.claim(), 'fake-engine')
        job = self.store.recent_jobs('alice')[0]
        self.assertEqual(job['state'], 'done')
        self.assertEqual(job['positions_done'], 2)
        self.assertEqual(job['positions_total'], 2)
        self.assertEqual(job['completed'], 1)


class ProgressUITests(unittest.TestCase):
    def test_only_latest_job_is_shown_with_localized_progress(self):
        from streamlit.testing.v1 import AppTest
        jobs = [
            dict(state='running', completed=0, message='Analyzing games', game_index=1,
                 games_total=2, positions_done=5, positions_total=20),
            dict(state='queued', completed=0, message='Waiting for analysis'),
            dict(state='failed', completed=0, message='Failed', positions_done=5, positions_total=20),
            dict(state='done', completed=2, message='Done'),
        ]
        code = "from visualization_all import job_status\nfrom beta_store import UserLibrary\njob_status(UserLibrary(None, 'alice'))"
        with patch('beta_store.UserLibrary.recent_jobs', return_value=jobs):
            app = AppTest.from_string(code).run(timeout=30)
            self.assertFalse(app.exception)
            bars = app.get('progress')
            self.assertEqual([bar.proto.value for bar in bars], [25])
            self.assertIn('5/20', bars[0].proto.text)
            app.session_state.ui_language = 'zh'
            app.run()
            self.assertFalse(app.exception)
            self.assertIn('已分析你的着法', app.get('progress')[0].proto.text)

    def test_only_newest_completed_message_is_visible(self):
        from streamlit.testing.v1 import AppTest
        jobs = [dict(state='done', completed=1, message='Added 7 puzzles. Refresh your library to review them.'),
                dict(state='done', completed=1, message='Added 3 puzzles. Refresh your library to review them.')]
        with patch('beta_store.UserLibrary.recent_jobs', return_value=jobs):
            app = AppTest.from_string("from visualization_all import job_status\nfrom beta_store import UserLibrary\njob_status(UserLibrary(None, 'alice'))").run(timeout=30)
            self.assertEqual(len(app.get('progress')), 1)
            text = ' '.join(item.value for item in app.markdown)
            self.assertIn('Added 7 puzzles', text)
            self.assertNotIn('Added 3 puzzles', text)

    def test_saving_stays_below_100_percent(self):
        from visualization_all import progress_display
        fraction, _ = progress_display(dict(state='running', positions_done=20, positions_total=20))
        self.assertEqual(fraction, 0.99)
