from copy import deepcopy
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
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'visualization_all.py')).run(timeout=30)
            app.checkbox(key='due_only').uncheck().run()
            app.selectbox(key='puzzle_player').set_value('alice').run()
            app.selectbox(key='review_month').set_value('2026-08').run()
            token = app.session_state['review_cycle']['token']
            app.number_input(key='review_loss').set_value(300).run()
            self.assertEqual(app.session_state['review_cycle']['ids'], ['boundary', 'large'])
            self.assertNotEqual(app.session_state['review_cycle']['token'], token)
            self.assertIsNone(board.call_args.kwargs['response'])
            self.assertEqual(app.number_input(key='analysis_threshold').value, 150)
            app.checkbox(key='due_only').check().run()
            self.assertEqual(app.session_state['review_cycle']['ids'], ['large'])
            app.checkbox(key='due_only').uncheck().run()
            for _ in range(2):
                app.button(key='next_puzzle').click().run()
            with patch('random.shuffle', side_effect=lambda ids: ids.reverse()):
                app.button(key='restart_cycle').click().run()
            self.assertEqual(app.session_state['review_cycle']['ids'], ['large', 'boundary'])
            app.selectbox(key='ui_language').set_value('zh').run()
            self.assertEqual(app.number_input(key='review_loss').value, 300)
            self.assertEqual(app.number_input(key='review_loss').label, '复习最低失分（厘兵）')
            app.selectbox(key='ui_language').set_value('en').run()
            app.number_input(key='review_loss').set_value(1000).run()
            self.assertTrue(any('No saved puzzles match' in item.value for item in app.info))
            self.assertFalse(any(b.key == 'next_puzzle' for b in app.button))
            app.number_input(key='review_loss').set_value(0).run()
            self.assertEqual(app.session_state['review_cycle']['ids'], ['small', 'below', 'boundary', 'large', 'mate'])
            self.assertFalse(app.exception)
            self.assertEqual(library, original)
            save.assert_not_called()
