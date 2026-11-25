from datetime import datetime, timezone, date
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

import requests
from chess_analysis import fetch_lichess_pgn, read_games, analyze_game

PGN = '[White "Me"]\n[Black "Other"]\n[Site "https://lichess.org/abcdefgh"]\n[Result "1-0"]\n\n1. e4 e5 1-0'


class LichessTests(unittest.TestCase):
    @patch('chess_analysis.requests.get')
    def test_month_boundaries_filters_and_multiple_games(self, get):
        response = get.return_value.__enter__.return_value
        response.status_code = 200
        response.iter_content.return_value = [(PGN + '\n\n' + PGN.replace('abcdefgh', 'ijklmnop')).encode()]
        texts = fetch_lichess_pgn(' Me ', 2026, 12, 5)
        self.assertEqual(len(texts), 2)
        self.assertEqual(next(read_games(texts[0])).headers['Site'], 'https://lichess.org/abcdefgh')
        params = get.call_args.kwargs['params']
        self.assertEqual(params['since'], int(datetime(2026, 12, 1, tzinfo=timezone.utc).timestamp() * 1000))
        self.assertEqual(params['until'], int(datetime(2027, 1, 1, tzinfo=timezone.utc).timestamp() * 1000) - 1)
        self.assertEqual(params['max'], 5)
        self.assertEqual(params['ongoing'], 'false')
        self.assertEqual(params['finished'], 'true')
        self.assertNotIn('chess960', params['perfType'])
        self.assertTrue(get.call_args.kwargs['stream'])
        get.return_value.__exit__.assert_called_once()

    @patch('chess_analysis.requests.get')
    def test_empty_history_and_game_cap(self, get):
        response = get.return_value.__enter__.return_value
        response.status_code = 200
        response.iter_content.return_value = []
        self.assertEqual(fetch_lichess_pgn('Me', 2026, 1), [])
        response.iter_content.return_value = [(PGN + '\n\n' + PGN).encode()]
        self.assertEqual(len(fetch_lichess_pgn('Me', 2026, 1, 1)), 1)

    @patch('chess_analysis.requests.get')
    def test_ongoing_and_variant_games_are_excluded(self, get):
        response = get.return_value.__enter__.return_value
        response.status_code = 200
        ongoing = PGN.replace('[Result "1-0"]', '[Result "*"]').replace('e5 1-0', 'e5 *')
        variant = '[Variant "Atomic"]\n' + PGN
        response.iter_content.return_value = [(ongoing + '\n\n' + variant + '\n\n' + PGN).encode()]
        self.assertEqual(len(fetch_lichess_pgn('Me', 2026, 1)), 1)

    @patch('chess_analysis.requests.get')
    def test_http_errors_and_size_limit(self, get):
        response = get.return_value.__enter__.return_value
        for status in [404, 429]:
            response.status_code = status
            with self.assertRaises(ValueError):
                fetch_lichess_pgn('Me', 2026, 1)
        response.status_code = 200
        response.iter_content.return_value = [b'x' * (1024 * 1024 + 1)]
        with self.assertRaises(ValueError):
            fetch_lichess_pgn('Me', 2026, 1)
        response.raise_for_status.side_effect = requests.HTTPError('503')
        with self.assertRaises(requests.HTTPError):
            fetch_lichess_pgn('Me', 2026, 1)

    @patch('chess_analysis.requests.get')
    def test_invalid_arguments_do_not_call_network(self, get):
        for username, year, month, maximum in [('Me/path', 2026, 1, 5), ('Me', 2012, 1, 5),
                                               ('Me', 2026, 13, 5), ('Me', 2026, 1, 101)]:
            with self.assertRaises(ValueError):
                fetch_lichess_pgn(username, year, month, maximum)
        get.assert_not_called()

    def test_platform_identity_keeps_games_distinct(self):
        from test_trainer import FakeEngine
        lichess = analyze_game(next(read_games(PGN)), 'Me', FakeEngine())
        chesscom = analyze_game(next(read_games(PGN.replace('https://lichess.org/abcdefgh', 'https://www.chess.com/game/live/123'))), 'Me', FakeEngine())
        self.assertEqual(lichess[0]['platform'], 'Lichess')
        self.assertEqual(chesscom[0]['platform'], 'Chess.com')
        self.assertNotEqual(lichess[0]['id'], chesscom[0]['id'])


@unittest.skipUnless(importlib.util.find_spec('streamlit'), 'Streamlit is not installed')
class LichessUITests(unittest.TestCase):
    def test_lichess_selection_import_and_chinese_labels(self):
        from streamlit.testing.v1 import AppTest
        from puzzle_store import load_library
        from test_trainer import FakeEngine
        library = load_library()
        with patch('puzzle_store.load_library', return_value=library), patch('puzzle_store.save_library') as save, \
             patch('chess_analysis.fetch_lichess_range', return_value=['[Date \"2026.08.01\"]\n' + PGN]) as fetch, \
             patch('chess_analysis.engine_path', return_value='test-engine'), \
             patch('chess.engine.SimpleEngine.popen_uci') as engine:
            engine.return_value.__enter__.return_value = FakeEngine()
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'visualization_all.py')).run(timeout=30)
            app.radio(key='analysis_source').set_value('Lichess month').run()
            self.assertFalse(app.exception)
            self.assertEqual(app.text_input(key='analysis_username').label, 'Your Lichess username')
            self.assertEqual(app.number_input(key='analysis_import_limit').value, 100)
            app.text_input(key='analysis_username').set_value('Me')
            app.date_input(key='analysis_start_date').set_value(date(2026, 8, 1))
            app.date_input(key='analysis_end_date').set_value(date(2026, 8, 31))
            app.button(key='language_toggle').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.text_input(key='analysis_username').label, '你的 Lichess 用户名')
            self.assertEqual(app.radio(key='analysis_source').value, 'Lichess month')
            app.button(key='start_review').click().run()
            self.assertFalse(app.exception)
            self.assertIn('review_setup', app.session_state)
            self.assertEqual(fetch.call_args.args[0], 'Me')
            self.assertEqual(fetch.call_args.args[3], 100)
            save.assert_called_once()
