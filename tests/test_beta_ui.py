from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from beta_store import BetaStore
from beta_auth import PASSWORDS


class BetaGateUITests(unittest.TestCase):
    def app(self):
        from streamlit.testing.v1 import AppTest
        return AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'beta_app.py'))

    def test_missing_configuration_fails_closed(self):
        with patch('beta_store.BetaStore') as database, patch('puzzle_store.load_library') as local:
            app = self.app().run(timeout=30)
            self.assertFalse(app.exception)
            self.assertTrue(app.error)
            database.assert_not_called()
            local.assert_not_called()

    def test_assigned_login_logout_and_no_registration(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BetaStore('sqlite:///' + str(Path(directory) / 'test.db'))
            executable = Path(directory) / 'fake-stockfish'
            executable.touch()
            try:
                with patch('puzzle_store.load_library') as local, \
                     patch('beta_store.BetaStore', return_value=store), patch('beta_worker.Worker') as worker:
                    app = self.app()
                    app.secrets['beta'] = {'database_url': 'postgresql://example/' + Path(directory).name,
                        'stockfish_path': str(executable), 'accounts': {'alice': {'password_hash': PASSWORDS.hash('assigned password here')}}}
                    app.run(timeout=30)
                    self.assertFalse(app.exception)
                    self.assertFalse(any(b.label in ['Create account', 'Sign in with Google'] for b in app.button))
                    self.assertEqual(len(app.text_input), 2)
                    self.assertFalse(any(b.label == 'Generate puzzles' for b in app.button))
                    app.button(key='help_page').click().run()
                    self.assertFalse(app.exception)
                    self.assertFalse(any(t.label == 'Password' for t in app.text_input))
                    self.assertTrue(any('all uncovered games from that selection' in item.value for item in app.markdown))
                    app.button(key='back_to_signin').click().run()
                    self.assertFalse(app.exception)
                    self.assertEqual(len(app.text_input), 2)
                    worker.assert_not_called()
                    app.text_input(key='account_username').set_value('alice')
                    app.text_input(key='account_password').set_value('wrong password')
                    next(b for b in app.button if b.label == 'Sign in').click().run()
                    self.assertFalse(app.exception)
                    self.assertTrue(app.error)
                    app.text_input(key='account_username').set_value('alice')
                    app.text_input(key='account_password').set_value('assigned password here')
                    next(b for b in app.button if b.label == 'Sign in').click().run()
                    self.assertFalse(app.exception)
                    self.assertTrue(any('click Start reviewing' in item.value for item in app.info))
                    self.assertFalse(any(t.label == 'Stockfish executable path' for t in app.text_input))
                    token = app.session_state['account_token']
                    self.assertEqual(app.session_state['_session_cookie_command']['token'], token)
                    self.assertFalse(any('A full page refresh requires' in item.value for item in app.caption))
                    self.assertFalse(any('Signed in as' in item.value for item in app.sidebar.caption))
                    self.assertFalse(any(b.label == 'Sign out' for b in app.sidebar.button))
                    self.assertTrue(any('Signed in as alice' in item.value for item in app.markdown))
                    self.assertFalse(any('Fetches up to 100 recent games.' in item.value for item in app.caption))
                    app.text_input(key='account_player_username').set_value('AliceChess')
                    next(b for b in app.button if b.label == 'Save default username').click().run()
                    self.assertFalse(app.exception)
                    self.assertEqual(app.text_input(key='analysis_username').value, 'AliceChess')
                    # A new AppTest has no Streamlit session state, like a browser refresh.
                    refreshed = self.app()
                    refreshed.secrets['beta'] = app.secrets['beta']
                    with patch('browser_session.request_token', return_value=token):
                        refreshed.run(timeout=30)
                    self.assertFalse(refreshed.exception)
                    self.assertEqual(refreshed.session_state['account_token'], token)
                    self.assertEqual(refreshed.session_state['beta_owner'], app.session_state['beta_owner'])
                    self.assertFalse(any(t.label == 'Username' for t in refreshed.text_input))
                    self.assertEqual(refreshed.text_input(key='analysis_username').value, 'AliceChess')
                    legacy = self.app()
                    legacy.secrets['beta'] = app.secrets['beta']
                    legacy.session_state.account_token = token
                    with patch('browser_session.request_token', return_value=None):
                        legacy.run(timeout=30)
                    self.assertFalse(legacy.exception)
                    self.assertEqual(legacy.session_state['_session_cookie_command']['token'], token)
                    app.button(key='beta_logout').click().run()
                    self.assertFalse(app.exception)
                    self.assertTrue(any(t.label == 'Username' for t in app.text_input))
                    local.assert_not_called()
                    from beta_auth import Accounts
                    accounts = Accounts(store.engine, {'alice': app.secrets['beta']['accounts']['alice']['password_hash']})
                    self.assertIsNone(accounts.identity(token))
                    self.assertEqual(app.session_state['_session_cookie_command']['max_age'], 0)
                    revoked = self.app()
                    revoked.secrets['beta'] = app.secrets['beta']
                    with patch('browser_session.request_token', return_value=token):
                        revoked.run(timeout=30)
                    self.assertFalse(revoked.exception)
                    self.assertTrue(any(t.label == 'Username' for t in revoked.text_input))
                    self.assertEqual(revoked.session_state['_session_cookie_command']['max_age'], 0)
            finally:
                store.engine.dispose()
