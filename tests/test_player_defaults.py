from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from beta_auth import Accounts, PASSWORDS
from beta_store import BetaStore


class PlayerDefaultTests(unittest.TestCase):
    def test_defaults_persist_and_edits_are_owned_and_not_reseeded(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BetaStore('sqlite:///' + str(Path(directory) / 'players.db'))
            configured = dict.fromkeys(('deer', 'bear', 'coco'), PASSWORDS.hash('assigned password here'))
            try:
                accounts = Accounts(store.engine, configured)
                tokens = {name: accounts.login(name, 'assigned password here') for name in configured}
                expected = {'deer': 'timberrrrrrrr', 'bear': 'ursabearattack', 'coco': 'mimiyamg'}
                for name, player in expected.items():
                    self.assertEqual(accounts.player_username(tokens[name]), player)
                self.assertEqual(accounts.save_player_username(tokens['deer'], ' OtherPlayer '), 'OtherPlayer')
                reloaded = Accounts(store.engine, configured)
                self.assertEqual(reloaded.player_username(tokens['deer']), 'OtherPlayer')
                self.assertEqual(reloaded.player_username(tokens['bear']), expected['bear'])
                with self.assertRaises(ValueError):
                    reloaded.save_player_username(tokens['deer'], 'invalid name!')
                reloaded.logout(tokens['deer'])
                with self.assertRaises(ValueError):
                    reloaded.save_player_username(tokens['deer'], 'AnotherPlayer')
            finally:
                store.engine.dispose()

    def test_temporary_override_is_used_once_then_defaults_return(self):
        from streamlit.testing.v1 import AppTest
        with patch('review_setup.prepare_start', return_value=dict(job_id=None, fetched=0)) as prepare:
            code = "from types import SimpleNamespace\nfrom review_setup import setup_sidebar\nsetup_sidebar({'puzzles': []}, SimpleNamespace(owner='owner', default_username='SavedPlayer'))"
            app = AppTest.from_string(code).run(timeout=30)
            self.assertFalse(app.exception)
            self.assertTrue(app.text_input(key='analysis_username').disabled)
            self.assertEqual(app.text_input(key='analysis_username').value, 'SavedPlayer')
            app.button(key='start_review').click().run()
            self.assertEqual(prepare.call_args.args[1]['username'], 'SavedPlayer')
            self.assertEqual(prepare.call_args.args[1]['source'], 'Chess.com month')
            app.checkbox(key='review_player_override').check().run()
            app.radio(key='analysis_source').set_value('Lichess month').run()
            app.text_input(key='analysis_username').set_value('TemporaryPlayer').run()
            app.button(key='start_review').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['review_setup']['username'], 'TemporaryPlayer')
            self.assertEqual(app.session_state['review_setup']['source'], 'Lichess month')
            self.assertFalse(app.checkbox(key='review_player_override').value)
            self.assertEqual(app.text_input(key='analysis_username').value, 'SavedPlayer')
            app.button(key='start_review').click().run()
            self.assertEqual(prepare.call_args.args[1]['username'], 'SavedPlayer')
            self.assertEqual(prepare.call_args.args[1]['source'], 'Chess.com month')

