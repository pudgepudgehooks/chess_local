import importlib.util
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch


@unittest.skipUnless(importlib.util.find_spec('streamlit'), 'Streamlit is not installed')
class BetaGateUITests(unittest.TestCase):
    def app(self):
        from streamlit.testing.v1 import AppTest
        return AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'beta_app.py'))

    def settings(self, app):
        app.secrets['beta'] = {'allowed_emails': ['friend@example.com'],
                               'database_url': 'postgresql://example/never-connect'}
        app.secrets['auth'] = {'client_id': 'test-client'}

    def test_missing_configuration_fails_closed(self):
        with patch('beta_store.BetaStore') as database, patch('puzzle_store.load_library') as local:
            app = self.app().run(timeout=30)
            self.assertFalse(app.exception)
            self.assertTrue(app.error)
            database.assert_not_called()
            local.assert_not_called()

    def test_logged_out_and_uninvited_never_load_data(self):
        with patch('beta_store.BetaStore') as database, patch('puzzle_store.load_library') as local:
            app = self.app()
            self.settings(app)
            app.user = {'is_logged_in': False}
            app.run(timeout=30)
            self.assertFalse(app.exception)
            self.assertTrue(any(b.label == 'Sign in with Google' for b in app.button))
            app.user = {'is_logged_in': True, 'email': 'stranger@example.com', 'email_verified': True,
                        'iss': 'https://accounts.google.com', 'sub': 'stranger', 'exp': time.time() + 3600}
            app.run()
            self.assertFalse(app.exception)
            self.assertTrue(app.error)
            database.assert_not_called()
            local.assert_not_called()

    def test_invited_beta_has_no_executable_field_or_local_samples(self):
        from beta_store import BetaStore
        with tempfile.TemporaryDirectory() as directory:
            store = BetaStore('sqlite:///' + str(Path(directory) / 'test.db'))
            executable = Path(directory) / 'fake-stockfish'
            executable.touch()
            try:
                with patch('puzzle_store.load_library') as local:
                    with patch('beta_store.BetaStore', return_value=store), patch('beta_worker.Worker'):
                        app = self.app()
                        self.settings(app)
                        app.secrets['beta']['stockfish_path'] = str(executable)
                        app.user = {'is_logged_in': True, 'email': 'friend@example.com', 'email_verified': True,
                                    'iss': 'https://accounts.google.com', 'sub': 'friend', 'exp': time.time() + 3600}
                        app.run(timeout=30)
                        self.assertFalse(app.exception)
                        self.assertFalse(any(t.label == 'Stockfish executable path' for t in app.text_input))
                        self.assertTrue(any('No puzzles are due' in item.value for item in app.info))
                        local.assert_not_called()
            finally:
                store.engine.dispose()
