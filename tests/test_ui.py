import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

from puzzle_store import load_library


@unittest.skipUnless(importlib.util.find_spec('streamlit'), 'Streamlit is not installed')
class TrainerUITests(unittest.TestCase):
    def test_dragged_answer_saved_once_across_reruns(self):
        from streamlit.testing.v1 import AppTest
        library = load_library()
        puzzle = library['puzzles'][0]
        puzzle.pop('review', None)
        event = {'fen': puzzle['fen'], 'uci': puzzle['best_move'], 'event_id': 'drag-1'}
        with patch('puzzle_store.load_library', return_value=library), \
             patch('puzzle_store.save_library') as save, \
             patch('drag_board.drag_board', return_value=event):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'visualization_all.py')).run(timeout=30)
            self.assertFalse(app.exception)
            self.assertTrue(app.success)
            self.assertEqual(save.call_count, 1)
            app.run()
            self.assertFalse(app.exception)
            self.assertEqual(save.call_count, 1)
            self.assertEqual(puzzle['review']['attempts'], 1)

    def test_answer_feedback_navigation_and_empty_queue(self):
        from streamlit.testing.v1 import AppTest
        library = load_library()
        library['puzzles'] = library['puzzles'][:2]
        for puzzle in library['puzzles']:
            puzzle.pop('review', None)
        with patch('puzzle_store.load_library', return_value=library), patch('puzzle_store.save_library') as save:
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'visualization_all.py')).run(timeout=30)
            self.assertFalse(app.exception)
            next(t for t in app.text_input if t.label.startswith('Your move')).set_value('invalid')
            next(b for b in app.button if b.label == 'Check move').click()
            app.run()
            self.assertTrue(app.error)
            save.assert_not_called()
            next(t for t in app.text_input if t.label.startswith('Your move')).set_value(library['puzzles'][0]['best_move'])
            next(b for b in app.button if b.label == 'Check move').click()
            app.run()
            self.assertFalse(app.exception)
            self.assertTrue(app.success)
            self.assertEqual(save.call_count, 1)
            # The solved puzzle stays visible until Next is explicitly selected.
            next(b for b in app.button if b.label == 'Hint').click()
            app.run()
            self.assertEqual(app.session_state['active_id'], library['puzzles'][0]['id'])
            next(b for b in app.button if b.label == 'Next puzzle').click()
            app.run()
            self.assertEqual(app.session_state['active_id'], library['puzzles'][1]['id'])
            next(t for t in app.text_input if t.label.startswith('Your move')).set_value(library['puzzles'][1]['best_move'])
            next(b for b in app.button if b.label == 'Check move').click()
            app.run()
            next(b for b in app.button if b.label == 'Next puzzle').click()
            app.run()
            self.assertFalse(app.exception)
            self.assertTrue(any('No puzzles are due' in info.value for info in app.info))


if __name__ == '__main__':
    unittest.main()
