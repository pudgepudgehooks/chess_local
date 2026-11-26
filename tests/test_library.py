from copy import deepcopy
from datetime import date
from ui_helpers import seed_review, choose_review
from pathlib import Path
import unittest
from unittest.mock import patch

import chess

from puzzle_store import record_review


def fixture_library(count=18):
    return {'version': 1, 'puzzles': [
        dict(id=f'p{i}', fen=chess.STARTING_FEN, username='alice' if i != 17 else 'bob',
             opponent=f'Opponent {i}', date='2026.08.01' if i < 16 else '2026.09.01',
             loss=150 if i % 2 else 300, legacy=True, played='h2h3',
             best_move='e2e4', accepted_moves=['e2e4'], solution=['e2e4', 'e7e5'])
        for i in range(count)]}


class LibraryUITests(unittest.TestCase):
    def setUp(self):
        visible = patch('visualization_all.SHOW_MISTAKE_LIBRARY', True)
        visible.start()
        self.addCleanup(visible.stop)

    def test_hidden_library_keeps_practice_and_saved_data(self):
        library = fixture_library()
        before = deepcopy(library)
        with patch('visualization_all.SHOW_MISTAKE_LIBRARY', False), \
             patch('visualization_all.load_library', return_value=library), \
             patch('visualization_all.save_library') as save, \
             patch('visualization_all.drag_board', return_value=None):
            app = self.app(library)
            app.session_state.main_tab_name = 'Mistake library'
            app.run(timeout=30)
            self.assertFalse(app.exception)
            self.assertFalse(app.get('tab'))
            self.assertEqual(app.session_state['main_tab_name'], 'Practice')
            self.assertFalse(self.open_ids(app))
            self.assertTrue(app.button(key='next_puzzle'))
            self.assertEqual(library, before)
            save.assert_not_called()

    def app(self, library):
        from streamlit.testing.v1 import AppTest
        return seed_review(AppTest.from_string('from visualization_all import main\nmain()'), library, username='alice')

    def open_ids(self, app):
        return [b.key for b in app.button if b.key and b.key.startswith('open-puzzle-')]

    def test_browse_pages_select_and_reopen_solved_puzzle_without_extra_attempts(self):
        library = fixture_library()
        record_review(library['puzzles'][1], True)
        before = deepcopy(library)
        with patch('visualization_all.load_library', return_value=library), \
             patch('visualization_all.save_library') as save, \
             patch('visualization_all.drag_board', return_value=None) as board:
            app = self.app(library).run(timeout=30)
            self.assertFalse(app.exception)
            self.assertNotIn('open-puzzle-p1', self.open_ids(app), 'due-only hides scheduled puzzles')
            choose_review(app, 'alice', date(2026, 8, 1), date(2026, 9, 30))
            self.assertEqual(len(self.open_ids(app)), 12)
            self.assertTrue(app.button(key='library-top-previous').disabled)
            self.assertTrue(app.button(key='library-top-page-1').disabled)
            app.button(key='library-bottom-next').click().run()
            self.assertEqual(self.open_ids(app), [f'open-puzzle-p{i}' for i in range(12, 17)])
            self.assertEqual(app.session_state['main_tab'], 'Mistake library')
            self.assertTrue(app.button(key='library-bottom-next').disabled)
            app.button(key='library-top-previous').click().run()
            self.assertEqual(len(self.open_ids(app)), 12)
            app.button(key='library-top-page-2').click().run()
            self.assertEqual(self.open_ids(app), [f'open-puzzle-p{i}' for i in range(12, 17)])
            self.assertEqual(library, before, 'browsing cannot alter review history')
            save.assert_not_called()
            app.button(key='open-puzzle-p15').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['main_tab'], 'Practice')
            self.assertEqual(app.session_state['active_id'], 'p15')
            self.assertEqual(app.session_state['review_cycle']['ids'][0], 'p15')
            self.assertEqual(len(set(app.session_state['review_cycle']['ids'])), 17)
            key = board.call_args.kwargs['key']
            board.return_value = dict(fen=chess.STARTING_FEN, uci='e2e4', event_id='solve-library-p15')
            app.run()
            self.assertEqual(save.call_count, 1)
            self.assertEqual(library['puzzles'][15]['review']['attempts'], 1)
            app.button(key='open-puzzle-p15').click().run()
            self.assertIsNone(board.call_args.kwargs['response'])
            self.assertNotEqual(board.call_args.kwargs['key'], key)
            self.assertEqual(library['puzzles'][15]['review']['attempts'], 1)
            self.assertEqual(save.call_count, 1)

    def test_filters_reset_pagination_and_language_keeps_library_tab(self):
        library = fixture_library()
        with patch('visualization_all.load_library', return_value=library), \
             patch('visualization_all.save_library') as save, \
             patch('visualization_all.drag_board', return_value=None):
            app = self.app(library).run(timeout=30)
            app.button(key='library-top-page-2').click().run()
            choose_review(app, 'alice', date(2026, 8, 1), date(2026, 8, 31), threshold=300)
            self.assertEqual(app.session_state['library_page'], 1)
            self.assertFalse(any(b.key.startswith('library-top-') for b in app.button if b.key))
            self.assertEqual(self.open_ids(app), [f'open-puzzle-p{i}' for i in range(0, 16, 2)])
            app.session_state.main_tab_name = 'Mistake library'
            app.run()
            app.button(key='language_toggle').click().run()
            self.assertEqual(app.session_state['main_tab'], '错题库')
            self.assertEqual(app.button(key='open-puzzle-p4').label, '练习此题')
            app.button(key='open-puzzle-p4').click().run()
            self.assertEqual(app.session_state['main_tab'], '练习')
            self.assertEqual(app.session_state['active_id'], 'p4')
            self.assertTrue(set(app.session_state['review_cycle']['ids']) <= {f'p{i}' for i in range(0, 16, 2)})
            choose_review(app, 'alice', date(2026, 8, 1), date(2026, 8, 31), threshold=1000)
            self.assertFalse(self.open_ids(app))
            self.assertFalse(app.exception)
            save.assert_not_called()
