import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
from puzzle_store import load_library


@unittest.skipUnless(importlib.util.find_spec('streamlit'), 'Streamlit is not installed')
class TrainerUITests(unittest.TestCase):
    def app(self):
        from streamlit.testing.v1 import AppTest
        return AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'visualization_all.py'))

    def test_dragged_answer_saved_once_across_reruns(self):
        library = load_library()
        puzzle = library['puzzles'][0]
        puzzle.pop('review', None)
        event = {'fen': puzzle['fen'], 'uci': puzzle['best_move'], 'event_id': 'drag-1'}
        with patch('puzzle_store.load_library', return_value=library), \
             patch('puzzle_store.save_library') as save, \
             patch('drag_board.drag_board', return_value=event) as component:
            app = self.app().run(timeout=30)
            self.assertFalse(app.exception)
            self.assertTrue(app.success)
            self.assertEqual(save.call_count, 1)
            response = component.call_args.kwargs['response']
            self.assertEqual(response['status'], 'correct')
            self.assertEqual(response['frames'][0]['uci'], puzzle['best_move'])
            app.run()
            self.assertFalse(app.exception)
            self.assertEqual(save.call_count, 1)
            self.assertEqual(puzzle['review']['attempts'], 1)

    def test_drag_only_retry_navigation_and_empty_queue(self):
        library = load_library()
        library['puzzles'] = library['puzzles'][:2]
        for puzzle in library['puzzles']:
            puzzle.pop('review', None)
        with patch('puzzle_store.load_library', return_value=library), patch('puzzle_store.save_library') as save, \
             patch('drag_board.drag_board', return_value=None) as component:
            app = self.app().run(timeout=30)
            self.assertFalse(app.exception)
            self.assertFalse(any(t.label.startswith('Your move') for t in app.text_input))
            self.assertFalse(any(b.label == 'Check move' for b in app.button))
            first = library['puzzles'][0]
            component.return_value = {'fen': first['fen'], 'uci': '0000', 'event_id': 'invalid'}
            app.run()
            self.assertTrue(app.error)
            save.assert_not_called()
            component.return_value = {'fen': first['fen'], 'uci': first['played'], 'event_id': 'wrong'}
            app.run()
            self.assertTrue(app.error)
            self.assertEqual(component.call_args.kwargs['response']['status'], 'incorrect')
            self.assertEqual(component.call_args.kwargs['response']['frames'], [])
            component.return_value = {'fen': first['fen'], 'uci': first['best_move'], 'event_id': 'correct'}
            app.run()
            self.assertTrue(app.success)
            self.assertEqual(save.call_count, 2)
            app.button(key=f"hint-{first['id']}").click().run()
            self.assertEqual(app.session_state['active_id'], first['id'])
            app.button(key='next_puzzle').click().run()
            second = library['puzzles'][1]
            self.assertEqual(app.session_state['active_id'], second['id'])
            self.assertIsNone(component.call_args.kwargs['response'])
            component.return_value = {'fen': second['fen'], 'uci': second['best_move'], 'event_id': 'second'}
            app.run()
            app.button(key='next_puzzle').click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any('No puzzles are due' in info.value for info in app.info))
