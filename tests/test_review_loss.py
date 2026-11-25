from copy import deepcopy
from datetime import date
from ui_helpers import seed_review, choose_review
from pathlib import Path
import unittest
from unittest.mock import patch

import chess

from puzzle_store import record_review


class ReviewLossTests(unittest.TestCase):
    def test_review_threshold_filters_saved_rounds_without_changing_library(self):
        from streamlit.testing.v1 import AppTest
        rows = [('small', 150, '2026.08.01', 'alice'),
                ('below', 299, '2026.08.02', 'alice'),
                ('boundary', 300, '2026.08.03', 'alice'),
                ('large', 450, '2026.08.04', 'alice'),
                ('mate', None, '2026.08.05', 'alice'),
                ('september', 600, '2026.09.01', 'alice'),
                ('other-player', 700, '2026.08.01', 'bob')]
        library = {'version': 1, 'puzzles': [
            dict(id=pid, loss=loss, date=date, username=owner, legacy=True,
                 fen=chess.STARTING_FEN, played='h2h3', best_move='e2e4',
                 solution=['e2e4', 'e7e5']) for pid, loss, date, owner in rows]}
        record_review(library['puzzles'][2], True)
        original = deepcopy(library)
        with patch('puzzle_store.load_library', return_value=library), \
             patch('puzzle_store.save_library') as save, \
             patch('drag_board.drag_board', return_value=None) as board:
            app = seed_review(AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'visualization_all.py')),
                              library, username='alice', start=date(2026, 8, 1), end=date(2026, 8, 31), due_only=False).run(timeout=30)
            token = app.session_state['review_cycle']['token']
            choose_review(app, 'alice', date(2026, 8, 1), date(2026, 8, 31), threshold=300)
            self.assertEqual(set(app.session_state['review_cycle']['ids']), {'boundary', 'large'})
            self.assertNotEqual(app.session_state['review_cycle']['token'], token)
            self.assertIsNone(board.call_args.kwargs['response'])
            self.assertEqual(app.number_input(key='analysis_threshold').value, 300)
            choose_review(app, 'alice', date(2026, 8, 1), date(2026, 8, 31), threshold=300, due_only=True)
            self.assertEqual(app.session_state['review_cycle']['ids'], ['large'])
            choose_review(app, 'alice', date(2026, 8, 1), date(2026, 8, 31), threshold=300)
            previous_order = list(app.session_state['review_cycle']['ids'])
            for _ in range(2):
                app.button(key='next_puzzle').click().run()
            with patch('random.shuffle', side_effect=lambda ids: ids.reverse()):
                app.button(key='restart_cycle').click().run()
            self.assertEqual(app.session_state['review_cycle']['ids'], previous_order[::-1])
            app.button(key='language_toggle').click().run()
            self.assertEqual(app.number_input(key='analysis_threshold').value, 300)
            self.assertEqual(app.session_state['review_setup']['threshold'], 300)
            app.button(key='language_toggle').click().run()
            choose_review(app, 'alice', date(2026, 8, 1), date(2026, 8, 31), threshold=1000)
            self.assertTrue(any('No puzzles match' in item.value for item in app.info))
            self.assertFalse(any(b.key == 'next_puzzle' for b in app.button))
            choose_review(app, 'alice', date(2026, 8, 1), date(2026, 8, 31), threshold=0)
            self.assertEqual(set(app.session_state['review_cycle']['ids']), {'small', 'below', 'boundary', 'large', 'mate'})
            self.assertFalse(app.exception)
            self.assertEqual(library, original)
            save.assert_not_called()
