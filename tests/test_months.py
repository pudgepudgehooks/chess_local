from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

import chess

from puzzle_store import puzzle_month, record_review


class MonthTests(unittest.TestCase):
    def test_saved_dates_group_by_year_and_month(self):
        for date in ['2026.08.16', '2026.08.??', '2026-08-16', '2026-08']:
            self.assertEqual(puzzle_month({'date': date}), '2026-08')
        self.assertEqual(puzzle_month({'date': '2025.08.16'}), '2025-08')
        for value in [None, '?', '????.??.??', '2026.??.16', '2026.13.01',
                      '2026.00.01', '0000.08.01', 20260816]:
            self.assertEqual(puzzle_month({'date': value}), 'Unknown date')

    def test_month_switch_restart_and_language_keep_saved_progress(self):
        from streamlit.testing.v1 import AppTest
        dates = [('aug-1', 'alice', '2026.08.01'), ('sep', 'alice', '2026.09.01'),
                 ('aug-2', 'alice', '2026-08-20'), ('old-aug', 'alice', '2025.08.01'),
                 ('unknown', 'alice', '?'), ('bob', 'bob', '2026.07.01')]
        library = {'version': 1, 'puzzles': [
            {'id': pid, 'username': owner, 'date': date, 'legacy': True,
             'fen': chess.STARTING_FEN, 'played': 'h2h3', 'best_move': 'e2e4',
             'accepted_moves': ['e2e4'], 'solution': ['e2e4', 'e7e5']}
            for pid, owner, date in dates]}
        record_review(library['puzzles'][1], True)
        original = deepcopy(library)
        with patch('puzzle_store.load_library', return_value=library), \
             patch('puzzle_store.save_library') as save, \
             patch('drag_board.drag_board', return_value=None) as board:
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'visualization_all.py')).run(timeout=30)
            app.checkbox(key='due_only').uncheck().run()
            app.selectbox(key='puzzle_player').set_value('alice').run()
            self.assertEqual(app.selectbox(key='review_month').options,
                             ['All months', '2026-09', '2026-08', '2025-08', 'Unknown date'])
            app.selectbox(key='review_month').set_value('2026-08').run()
            self.assertEqual(app.session_state['review_cycle']['ids'], ['aug-1', 'aug-2'])
            august_token = app.session_state['review_cycle']['token']
            app.button(key='next_puzzle').click().run()
            app.button(key='next_puzzle').click().run()
            self.assertEqual(app.session_state['review_cycle']['state'], 'complete')
            with patch('random.shuffle', side_effect=lambda ids: ids.reverse()):
                app.button(key='restart_cycle').click().run()
            self.assertEqual(app.session_state['review_cycle']['ids'], ['aug-2', 'aug-1'])
            app.selectbox(key='review_month').set_value('2026-09').run()
            self.assertEqual(app.session_state['active_id'], 'sep')
            self.assertNotEqual(app.session_state['review_cycle']['token'], august_token)
            self.assertIsNone(board.call_args.kwargs['response'])
            app.selectbox(key='ui_language').set_value('zh').run()
            self.assertEqual(app.selectbox(key='review_month').value, '2026-09')
            self.assertEqual(app.selectbox(key='review_month').label, '已保存棋谱的月份')
            app.selectbox(key='review_month').set_value('Unknown date').run()
            self.assertEqual(app.session_state['review_cycle']['ids'], ['unknown'])
            app.selectbox(key='puzzle_player').set_value('bob').run()
            self.assertEqual(app.selectbox(key='review_month').value, 'All months')
            self.assertEqual(app.session_state['review_cycle']['ids'], ['bob'])
            self.assertFalse(app.exception)
            self.assertEqual(library, original)
            save.assert_not_called()
