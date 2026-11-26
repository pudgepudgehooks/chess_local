import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
from puzzle_store import load_library
from ui_helpers import seed_review


@unittest.skipUnless(importlib.util.find_spec('streamlit'), 'Streamlit is not installed')
class TrainerUITests(unittest.TestCase):
    def app(self, library):
        from streamlit.testing.v1 import AppTest
        app = seed_review(AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'visualization_all.py')), library)
        # Event-based tests address specific positions in a known round order.
        import uuid
        app.session_state.review_cycle = dict(ids=[p['id'] for p in library['puzzles']],
            index=0, state='active', token=uuid.uuid4().hex)
        return app

    def test_preload_and_reused_board_ignore_previous_puzzle_events(self):
        library = load_library()
        first = library['puzzles'][0]
        second = dict(first, id='same-position-next-puzzle')
        library['puzzles'] = [first, second]
        with patch('puzzle_store.load_library', return_value=library), \
             patch('puzzle_store.save_library') as save, \
             patch('drag_board.prepare_board') as prepare, \
             patch('drag_board.drag_board', return_value=None) as component:
            app = self.app(library).run(timeout=30)
            self.assertFalse(app.exception)
            self.assertIn(second['fen'], [call.args[0] for call in prepare.call_args_list])
            board_key = component.call_args.kwargs['key']
            self.assertTrue(app.button(key='previous_puzzle').disabled)
            self.assertEqual(component.call_args.kwargs['hint_square'], first['best_move'][:2])
            captions = '\n'.join(item.value for item in app.caption)
            self.assertNotIn('Reviewing ', captions)
            self.assertNotIn('Reused saved analysis', captions)
            self.assertNotIn('Drag a piece', captions)
            self.assertFalse(any(b.label == 'Hint' for b in app.button), 'hint is handled inside the board')
            component.return_value = dict(fen=first['fen'], uci=first['best_move'],
                                          context_id=first['id'], event_id='delayed-old-puzzle')
            app.button(key='next_puzzle').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['active_id'], second['id'])
            self.assertEqual(component.call_args.kwargs['key'], board_key)
            self.assertEqual(component.call_args.kwargs['context_id'], second['id'])
            self.assertIsNone(component.call_args.kwargs['response'])
            self.assertFalse(app.button(key='previous_puzzle').disabled)
            component.return_value = None
            app.button(key='previous_puzzle').click().run()
            self.assertEqual(app.session_state['active_id'], first['id'])
            self.assertTrue(app.button(key='previous_puzzle').disabled)
            save.assert_not_called()

    def test_alternative_feedback_and_own_continuation_in_both_languages(self):
        import chess
        for continuation in (True, False):
            with self.subTest(continuation=continuation):
                puzzle = dict(id='alternative', fen=chess.STARTING_FEN, best_move='d2d4', played='f2f3',
                    accepted_moves=['d2d4', 'g1f3'], accepted_lines={'g1f3': ['g1f3', 'd7d5']},
                    solution=['d2d4', 'd7d5'], username='Player', opponent='Other', date='2026.11.01',
                    move_number=1, loss=200)
                library = {'puzzles': [puzzle]}
                board = chess.Board()
                frames = []
                for uci in (['g1f3', 'd7d5'] if continuation else ['g1f3']):
                    move = chess.Move.from_uci(uci)
                    san = board.san(move)
                    board.push(move)
                    frames.append(dict(fen=board.fen(), uci=uci, san=san))
                event = dict(fen=puzzle['fen'], uci='g1f3', event_id='alternative-answer')
                with patch('puzzle_store.load_library', return_value=library), \
                     patch('puzzle_store.save_library') as save, \
                     patch('drag_board.drag_board', return_value=event) as component, \
                     patch('drag_board.playback_frames', return_value=frames) as playback:
                    app = self.app(library).run(timeout=30)
                    self.assertFalse(app.exception)
                    response = component.call_args.kwargs['response']
                    self.assertEqual(response['status'], 'correct')
                    self.assertEqual(response['message_values'], {'move': 'd4'})
                    self.assertEqual(response['frames'][0]['uci'], 'g1f3')
                    self.assertEqual(playback.call_args.args[1].uci(), 'g1f3')
                    self.assertIn('acceptable alternative', app.success[0].value)
                    self.assertIn('d4', app.success[0].value)
                    self.assertNotIn('{move}', app.success[0].value)
                    if not continuation:
                        self.assertIn('No continuation', app.success[0].value)
                    self.assertEqual(puzzle['review']['correct'], 1)
                    app.button(key='language_toggle').click().run()
                    self.assertFalse(app.exception)
                    self.assertIn('另一种着法', app.success[0].value)
                    self.assertIn('d4', app.success[0].value)
                    self.assertEqual(save.call_count, 1)

    def test_dragged_answer_saved_once_across_reruns(self):
        library = load_library()
        puzzle = library['puzzles'][0]
        puzzle.pop('review', None)
        event = {'fen': puzzle['fen'], 'uci': puzzle['best_move'], 'event_id': 'drag-1'}
        with patch('puzzle_store.load_library', return_value=library), \
             patch('puzzle_store.save_library') as save, \
             patch('drag_board.drag_board', return_value=event) as component:
            app = self.app(library).run(timeout=30)
            self.assertFalse(app.exception)
            self.assertFalse(any('Correct! Use Forward and Back to review the continuation.' in item.value for item in app.success))
            self.assertFalse(any('Saved attempts:' in item.value for item in app.caption))
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
            app = self.app(library).run(timeout=30)
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
            self.assertTrue(component.call_args.kwargs['response']['repeat_game_mistake'])
            import chess
            attempted = chess.Board(first['fen'])
            attempted.push_uci(first['played'])
            self.assertEqual(component.call_args.kwargs['response']['attempt_fen'], attempted.fen())
            component.return_value = {'fen': first['fen'], 'uci': first['best_move'], 'event_id': 'correct'}
            app.run()
            self.assertFalse(any('Correct! Use Forward and Back' in item.value for item in app.success))
            self.assertEqual(save.call_count, 2)
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
            app = self.app(library).run(timeout=30)
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
            app.button(key='language_toggle').click().run()
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
            app = self.app(library).run(timeout=30)
            first_key = component.call_args.kwargs['key']
            app.button(key='next_puzzle').click().run()
            app.button(key='restart_cycle').click().run()
            self.assertFalse(app.exception)
            self.assertNotEqual(component.call_args.kwargs['key'], first_key)
            self.assertIsNone(component.call_args.kwargs['response'])
