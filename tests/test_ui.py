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
            self.assertFalse(app.error)
            self.assertEqual(component.call_args.kwargs['response']['message'], 'The answer is incorrect, please try again')
            save.assert_not_called()
            component.return_value = {'fen': first['fen'], 'uci': first['played'], 'event_id': 'wrong'}
            app.run()
            self.assertFalse(app.error, 'board feedback must not leave a persistent error banner')
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
            self.assertTrue(any('Cycle complete!' in item.value for item in app.success))
            self.assertTrue(app.button(key='rest_cycle'))
            self.assertTrue(app.button(key='restart_cycle'))

    def test_cycle_rest_restart_shuffles_and_keeps_reviews(self):
        from copy import deepcopy
        from puzzle_store import record_review
        library = load_library()
        library['puzzles'] = library['puzzles'][:3]
        for puzzle in library['puzzles']:
            puzzle.pop('review', None)
        with patch('puzzle_store.load_library', return_value=library), \
             patch('puzzle_store.save_library') as save, \
             patch('drag_board.drag_board', return_value=None) as component:
            app = self.app().run(timeout=30)
            original_order = list(app.session_state['review_cycle']['ids'])
            original_token = app.session_state['review_cycle']['token']
            for puzzle in library['puzzles']:
                record_review(puzzle, True)
            saved_reviews = deepcopy([p['review'] for p in library['puzzles']])
            for _ in original_order:
                app.button(key='next_puzzle').click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any('Cycle complete!' in item.value for item in app.success))
            self.assertFalse(any(b.key == 'next_puzzle' for b in app.button))
            app.button(key='rest_cycle').click().run()
            self.assertEqual(app.session_state['review_cycle']['state'], 'rest')
            self.assertTrue(any('Enjoy your break' in item.value for item in app.info))
            app.run()
            self.assertEqual(app.session_state['review_cycle']['state'], 'rest')
            with patch('random.shuffle', side_effect=lambda ids: ids.reverse()) as shuffle:
                app.button(key='restart_cycle').click().run()
                shuffle.assert_called_once()
            cycle = app.session_state['review_cycle']
            self.assertEqual(cycle['ids'], original_order[::-1])
            self.assertNotEqual(cycle['token'], original_token)
            self.assertEqual(app.session_state['active_id'], cycle['ids'][0])
            self.assertIsNone(component.call_args.kwargs['response'])
            self.assertEqual([p['review'] for p in library['puzzles']], saved_reviews)
            save.assert_not_called()
            app.selectbox(key='ui_language').set_value('zh').run()
            self.assertEqual(app.session_state['review_cycle']['ids'], cycle['ids'])
            for _ in original_order:
                app.button(key='next_puzzle').click().run()
            self.assertEqual(app.session_state['review_cycle']['state'], 'complete')
            self.assertEqual(app.button(key='rest_cycle').label, '休息一下')

    def test_single_puzzle_cycle_can_restart_without_stale_board(self):
        library = load_library()
        library['puzzles'] = library['puzzles'][:1]
        library['puzzles'][0].pop('review', None)
        with patch('puzzle_store.load_library', return_value=library), \
             patch('drag_board.drag_board', return_value=None) as component:
            app = self.app().run(timeout=30)
            first_key = component.call_args.kwargs['key']
            app.button(key='next_puzzle').click().run()
            app.button(key='restart_cycle').click().run()
            self.assertFalse(app.exception)
            self.assertNotEqual(component.call_args.kwargs['key'], first_key)
            self.assertIsNone(component.call_args.kwargs['response'])
