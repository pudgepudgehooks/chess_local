from datetime import date
from pathlib import Path
import unittest
from unittest.mock import patch

import chess

from player_names import normalize_player_username


class PlayerNameTests(unittest.TestCase):
    def test_clipboard_whitespace_invisible_marks_and_full_width_text(self):
        for value in ['timberrrrrrrr', '  timberrrrrrrr\r\n', '\u00a0timberrrrrrrr\u00a0',
                      '\ufeff\u200etimber\u200brrrrrrr\u2060', 'ｔｉｍｂｅｒｒｒｒｒｒｒｒ']:
            with self.subTest(value=value):
                self.assertEqual(normalize_player_username(value), 'timberrrrrrrr')
        self.assertEqual(normalize_player_username(' Player_Name-123 '), 'Player_Name-123')

    def test_invalid_visible_characters_are_not_silently_removed(self):
        for value in ['', '\u200b', 'tim ber', 'tim\nber', '@timber', 'timber/other', 'x' * 51, None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_player_username(value)

    def test_imports_send_clean_usernames_to_both_services(self):
        from chess_analysis import fetch_chesscom_pgn, fetch_lichess_pgn
        with patch('chess_analysis.requests.get') as get:
            get.return_value.json.return_value = {'games': []}
            fetch_chesscom_pgn('\u200btimberrrrrrrr\u00a0', 2026, 11)
            self.assertEqual(get.call_args.args[0], 'https://api.chess.com/pub/player/timberrrrrrrr/games/2026/11')
            response = get.return_value.__enter__.return_value
            response.status_code = 200
            response.iter_content.return_value = []
            fetch_lichess_pgn('\u200eMe\ufeff', 2026, 11)
            self.assertEqual(get.call_args.args[0], 'https://lichess.org/api/games/user/Me')

    def test_worker_checks_game_ownership_using_clean_name(self):
        from beta_worker import validate_payload
        pgn = '[White "timberrrrrrrr"]\n[Black "Other"]\n\n1. e4 e5 *'
        payload = validate_payload('\u200btimberrrrrrrr\ufeff', [pgn], 10, 250)
        self.assertEqual(payload['username'], 'timberrrrrrrr')
        with self.assertRaises(ValueError):
            validate_payload('\u200bSomebodyElse', [pgn], 10, 250)

    def test_pasted_input_is_cleaned_and_start_uses_the_same_player(self):
        from streamlit.testing.v1 import AppTest
        puzzle = dict(id='copied-player', username='timberrrrrrrr', opponent='Other', date='2026.11.24',
            fen=chess.STARTING_FEN, played='f2f3', best_move='e2e4', accepted_moves=['e2e4'],
            solution=['e2e4', 'e7e5'], loss=300, move_number=1)
        with patch('puzzle_store.load_library', return_value={'puzzles': [puzzle]}), \
             patch('chess_analysis.fetch_chesscom_range', return_value=[]) as fetch, \
             patch('drag_board.drag_board', return_value=None):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'visualization_all.py'), default_timeout=30).run()
            app.text_input(key='analysis_username').set_value('\u200e\u200btimberrrrrrrr\u00a0')
            app.date_input(key='analysis_start_date').set_value(date(2026, 11, 24))
            app.date_input(key='analysis_end_date').set_value(date(2026, 11, 24))
            app.run()
            self.assertFalse(app.exception)
            self.assertEqual(app.text_input(key='analysis_username').value, 'timberrrrrrrr')
            app.button(key='start_review').click().run()
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            self.assertEqual(fetch.call_args.args[0], 'timberrrrrrrr')
            self.assertEqual(app.session_state['review_setup']['username'], 'timberrrrrrrr')
            self.assertEqual(app.session_state['active_id'], 'copied-player')
