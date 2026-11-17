import importlib.util
from pathlib import Path
from string import Formatter
import unittest
from unittest.mock import patch


@unittest.skipUnless(importlib.util.find_spec('streamlit'), 'Streamlit is not installed')
class LanguageTests(unittest.TestCase):
    def app(self, filename='visualization_all.py'):
        from streamlit.testing.v1 import AppTest
        return AppTest.from_file(str(Path(__file__).resolve().parents[1] / filename))

    def test_translation_placeholders_match(self):
        from i18n import ZH
        fields = lambda text: {name for _, name, _, _ in Formatter().parse(text) if name}
        for english, chinese in ZH.items():
            with self.subTest(message=english):
                self.assertEqual(fields(english), fields(chinese))

    def test_switch_preserves_position_inputs_and_progress(self):
        from puzzle_store import load_library
        library = load_library()
        with patch('puzzle_store.load_library', return_value=library), patch('puzzle_store.save_library') as save:
            app = self.app().run(timeout=30)
            app.text_input(key='analysis_username').set_value('MyPlayer')
            app.button(key='next_puzzle').click()
            app.run()
            active = app.session_state['active_id']
            app.radio(key='analysis_source').set_value('Upload PGN').run()
            app.selectbox(key='ui_language').set_value('zh').run()
            self.assertFalse(app.exception)
            self.assertEqual(app.title[0].value, '国际象棋错题训练')
            self.assertEqual(app.text_input(key='analysis_username').value, 'MyPlayer')
            self.assertEqual(app.radio(key='analysis_source').value, 'Upload PGN')
            self.assertEqual(app.session_state['active_id'], active)
            self.assertEqual(app.query_params['lang'], 'zh')
            self.assertEqual(app.button(key='next_puzzle').label, '下一题')
            app.selectbox(key='ui_language').set_value('en').run()
            self.assertEqual(app.title[0].value, 'Chess Mistake Trainer')
            self.assertEqual(app.session_state['active_id'], active)
            save.assert_not_called()

    def test_chinese_answer_validation(self):
        from puzzle_store import load_library
        puzzle = load_library()['puzzles'][0]
        with patch('drag_board.drag_board', return_value={'fen': puzzle['fen'], 'uci': '0000', 'event_id': 'invalid-zh'}) as component:
            app = self.app()
            app.query_params['lang'] = 'zh'
            app.run(timeout=30)
            self.assertFalse(app.exception)
            from i18n import tr
            self.assertFalse(app.error)
            with patch('i18n.language', return_value='zh'):
                self.assertIn('请再试一次', tr(component.call_args.kwargs['response']['message']))

    def test_beta_switch_before_login(self):
        import tempfile
        from beta_store import BetaStore
        from beta_auth import PASSWORDS
        with tempfile.TemporaryDirectory() as directory:
            store = BetaStore('sqlite:///' + str(Path(directory) / 'test.db'))
            try:
                with patch('beta_store.BetaStore', return_value=store):
                    app = self.app('beta_app.py')
                    app.secrets['beta'] = {'database_url': 'postgresql://example/' + Path(directory).name,
                        'accounts': {'alice': {'password_hash': PASSWORDS.hash('assigned password here')}}}
                    app.run(timeout=30)
                    app.selectbox(key='ui_language').set_value('zh').run()
                    self.assertFalse(app.exception)
                    self.assertTrue(any(b.label == '登录' for b in app.button))
                    self.assertTrue(any(t.label == '用户名' for t in app.text_input))
            finally:
                store.engine.dispose()

    def test_board_and_job_messages_translate(self):
        from i18n import job_message
        from drag_board import drag_board
        import chess
        with patch('i18n.language', return_value='zh'), patch('drag_board.language', return_value='zh'), patch('drag_board._component') as component:
            drag_board(chess.Board(), 'test')
            arguments = component.call_args.kwargs
            self.assertEqual(arguments['language'], 'zh')
            self.assertEqual(arguments['labels']['Queen'], '后')
            self.assertIn('白方', arguments['pieces']['e1']['label'])
            self.assertIn('3 道', job_message('Added 3 puzzles. Refresh your library to review them.'))
