from pathlib import Path
import unittest
from unittest.mock import patch

from puzzle_store import load_library


class GuideUITests(unittest.TestCase):
    def test_tabs_and_language_switch_keep_the_current_review(self):
        from streamlit.testing.v1 import AppTest
        library = load_library()
        for puzzle in library['puzzles']:
            puzzle.pop('review', None)
        with patch('puzzle_store.load_library', return_value=library), \
             patch('puzzle_store.save_library') as save, \
             patch('drag_board.drag_board', return_value=None):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'visualization_all.py')).run(timeout=30)
            self.assertFalse(app.exception)
            self.assertEqual([tab.proto.label for tab in app.get('tab')], ['Practice', 'Mistake library', 'How it works'])
            app.number_input(key='review_loss').set_value(300).run()
            app.button(key='next_puzzle').click().run()
            active = app.session_state['active_id']
            token = app.session_state['review_cycle']['token']
            app.selectbox(key='ui_language').set_value('zh').run()
            self.assertFalse(app.exception)
            self.assertEqual([tab.proto.label for tab in app.get('tab')], ['练习', '错题库', '使用说明'])
            self.assertEqual(app.session_state['active_id'], active)
            self.assertEqual(app.session_state['review_cycle']['token'], token)
            self.assertEqual(app.number_input(key='review_loss').value, 300)
            self.assertTrue(any('10 分钟' in item.value for item in app.markdown))
            save.assert_not_called()

    def test_online_guide_explains_beta_instead_of_local_setup(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_string('from trainer_guide import show_guide\nshow_guide(online=True)').run(timeout=30)
        self.assertFalse(app.exception)
        text = '\n'.join(item.value for item in app.markdown)
        self.assertIn('Update puzzle library', text)
        self.assertIn('five games per request', text)
        self.assertNotIn('Stockfish executable path', text)
