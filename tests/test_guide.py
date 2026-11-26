from pathlib import Path
import unittest
from unittest.mock import patch

from puzzle_store import load_library
from ui_helpers import seed_review


class GuideUITests(unittest.TestCase):
    def test_tabs_and_language_switch_keep_the_current_review(self):
        from streamlit.testing.v1 import AppTest
        library = load_library()
        for puzzle in library['puzzles']:
            puzzle.pop('review', None)
        with patch('puzzle_store.load_library', return_value=library), \
             patch('puzzle_store.save_library') as save, \
             patch('drag_board.drag_board', return_value=None):
            app = seed_review(AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'visualization_all.py')), library).run(timeout=30)
            self.assertFalse(app.exception)
            self.assertEqual([tab.proto.label for tab in app.get('tab')], ['Practice'])
            app.checkbox(key='analysis_use_custom_loss').check().run()
            app.number_input(key='analysis_threshold').set_value(300).run()
            app.button(key='next_puzzle').click().run()
            active = app.session_state['active_id']
            token = app.session_state['review_cycle']['token']
            app.button(key='language_toggle').click().run()
            self.assertFalse(app.exception)
            self.assertEqual([tab.proto.label for tab in app.get('tab')], ['练习'])
            self.assertEqual(app.session_state['active_id'], active)
            self.assertEqual(app.session_state['review_cycle']['token'], token)
            self.assertEqual(app.number_input(key='analysis_threshold').value, 300)
            app.button(key='sound_toggle').click().run()
            self.assertFalse(app.session_state['sound_enabled'])
            self.assertEqual(app.session_state['active_id'], active)
            self.assertEqual(app.session_state['review_cycle']['token'], token)
            app.button(key='help_page').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.query_params['page'], 'help')
            self.assertFalse(app.get('tab'))
            self.assertTrue(any('10 分钟' in item.value for item in app.markdown))
            self.assertTrue(any('30 厘兵' in item.value for item in app.markdown))
            app.button(key='language_toggle').click().run()
            self.assertTrue(any('30 centipawns' in item.value for item in app.markdown))
            app.button(key='back_to_puzzles').click().run()
            self.assertFalse(app.exception)
            self.assertNotIn('page', app.query_params)
            self.assertEqual(app.session_state['active_id'], active)
            self.assertEqual(app.session_state['review_cycle']['token'], token)
            self.assertEqual(app.number_input(key='analysis_threshold').value, 300)
            save.assert_not_called()

    def test_online_guide_explains_beta_instead_of_local_setup(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_string('from trainer_guide import show_guide\nshow_guide(online=True)').run(timeout=30)
        self.assertFalse(app.exception)
        text = '\n'.join(item.value for item in app.markdown)
        self.assertIn('review opens automatically', text)
        self.assertIn('all uncovered games from that selection', text)
        self.assertIn('30 centipawns (0.3 pawns)', text)
        self.assertIn('same review schedule', text)
        self.assertIn('Low uses a minimum loss of 150 centipawns; High uses 300', text)
        self.assertNotIn('Stockfish executable path', text)
