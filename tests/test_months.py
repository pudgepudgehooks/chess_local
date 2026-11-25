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
        from datetime import date
        from streamlit.testing.v1 import AppTest
        from ui_helpers import seed_review, choose_review
        dates = [('aug-1', 'alice', '2026.08.01'), ('sep', 'alice', '2026.09.01'),
                 ('aug-2', 'alice', '2026-08-20'), ('old-aug', 'alice', '2025.08.01'),
                 ('bob', 'bob', '2026.07.01')]
        library = {'version': 1, 'puzzles': [
            {'id': pid, 'username': owner, 'date': day, 'legacy': True,
             'fen': chess.STARTING_FEN, 'played': 'h2h3', 'best_move': 'e2e4',
             'accepted_moves': ['e2e4'], 'solution': ['e2e4', 'e7e5']}
            for pid, owner, day in dates]}
        record_review(library['puzzles'][1], True)
        original = deepcopy(library)
        with patch('puzzle_store.load_library', return_value=library), \
             patch('puzzle_store.save_library') as save, \
             patch('drag_board.drag_board', return_value=None) as board:
            app = seed_review(AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'visualization_all.py')),
                              library, username='alice', start=date(2026, 8, 1), end=date(2026, 8, 31), due_only=False).run(timeout=30)
            self.assertEqual(set(app.session_state['review_cycle']['ids']), {'aug-1', 'aug-2'})
            previous_order = list(app.session_state['review_cycle']['ids'])
            august_token = app.session_state['review_cycle']['token']
            app.button(key='next_puzzle').click().run()
            app.button(key='next_puzzle').click().run()
            with patch('random.shuffle', side_effect=lambda ids: ids.reverse()):
                app.button(key='restart_cycle').click().run()
            self.assertEqual(app.session_state['review_cycle']['ids'], previous_order[::-1])
            choose_review(app, 'alice', date(2026, 9, 1), date(2026, 9, 30))
            self.assertEqual(app.session_state['active_id'], 'sep')
            self.assertNotEqual(app.session_state['review_cycle']['token'], august_token)
            self.assertIsNone(board.call_args.kwargs['response'])
            app.button(key='language_toggle').click().run()
            self.assertEqual(app.session_state['review_setup']['start'], date(2026, 9, 1))
            choose_review(app, 'bob', date(2026, 7, 1), date(2026, 7, 31))
            self.assertEqual(app.session_state['review_cycle']['ids'], ['bob'])
            self.assertFalse(app.exception)
            self.assertEqual(library, original)
            save.assert_not_called()
