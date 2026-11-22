from copy import deepcopy
from datetime import date, datetime, timezone
import unittest
from unittest.mock import patch

import chess
import requests

from chess_analysis import fetch_chesscom_range, fetch_lichess_range, filter_games_by_date, read_games
from game_dates import validate_date_range


def pgn(day):
    return f'[White "Me"]\n[Black "Other"]\n[Date "{day}"]\n[Result "1-0"]\n\n1. e4 e5 1-0'


class DateRangeTests(unittest.TestCase):
    def test_chesscom_cross_month_includes_both_dates_before_applying_limit(self):
        archives = {
            (2026, 9): {'games': [{'pgn': pgn('2026.09.01')}, {'pgn': pgn('2026.09.02')}]},
            (2026, 8): {'games': [{'pgn': pgn('2026.08.29')}, {'pgn': pgn('2026.08.30')},
                                {'pgn': pgn('2026.08.31'), 'rules': 'chess960'}]},
        }
        with patch('chess_analysis.fetch_chesscom_pgn', side_effect=lambda username, year, month: archives[year, month]) as fetch:
            result = fetch_chesscom_range('Me', date(2026, 8, 30), date(2026, 9, 1))
            self.assertEqual([next(read_games(text)).headers['Date'] for text in result], ['2026.09.01', '2026.08.30'])
            self.assertEqual([call.args[1:] for call in fetch.call_args_list], [(2026, 9), (2026, 8)])
            fetch.reset_mock()
            result = fetch_chesscom_range('Me', date(2026, 8, 30), date(2026, 9, 1), max_games=1)
            self.assertEqual(len(result), 1)
            self.assertEqual(fetch.call_count, 1)

    def test_lichess_single_day_includes_end_of_day_and_preserves_beta_limit(self):
        with patch('chess_analysis.requests.get') as get:
            response = get.return_value.__enter__.return_value
            response.status_code = 200
            response.iter_content.return_value = [pgn('2024.02.29').encode()]
            result = fetch_lichess_range('Me', date(2024, 2, 29), date(2024, 2, 29), max_games=5)
            self.assertEqual(len(result), 1)
            params = get.call_args.kwargs['params']
            self.assertEqual(params['since'], int(datetime(2024, 2, 29, tzinfo=timezone.utc).timestamp() * 1000))
            self.assertEqual(params['until'], int(datetime(2024, 3, 1, tzinfo=timezone.utc).timestamp() * 1000) - 1)
            self.assertEqual(params['max'], 5)

    def test_chesscom_range_skips_missing_month_but_keeps_real_errors(self):
        response = requests.Response()
        response.status_code = 404
        with patch('chess_analysis.fetch_chesscom_pgn', side_effect=[
                requests.HTTPError(response=response), {'games': [{'pgn': pgn('2026.08.30')}]}]):
            self.assertEqual(len(fetch_chesscom_range('Me', date(2026, 8, 30), date(2026, 9, 1))), 1)
        response.status_code = 500
        with patch('chess_analysis.fetch_chesscom_pgn', side_effect=requests.HTTPError(response=response)):
            with self.assertRaises(requests.HTTPError):
                fetch_chesscom_range('Me', date(2026, 8, 30), date(2026, 9, 1))

    def test_uploaded_games_unknown_dates_and_invalid_ranges(self):
        texts = [pgn('2026.08.01') + '\n\n' + pgn('2026.08.02') + '\n\n' + pgn('????.??.??')]
        selected = filter_games_by_date(texts, date(2026, 8, 2), date(2026, 8, 2))
        self.assertEqual(len(selected), 1)
        self.assertEqual(next(read_games(selected[0])).headers['Date'], '2026.08.02')
        with patch('chess_analysis.requests.get') as get:
            for start, end in [(None, date(2026, 8, 1)), (date(2026, 9, 1), date(2026, 8, 1)),
                               (date(2024, 1, 1), date(2026, 1, 1))]:
                with self.assertRaises(ValueError):
                    fetch_chesscom_range('Me', start, end)
            get.assert_not_called()
        validate_date_range(date(2024, 1, 1), date(2024, 12, 31), max_days=366)


class DateRangeUITests(unittest.TestCase):
    def test_review_range_filters_both_views_and_shuffled_restart_without_deleting(self):
        from streamlit.testing.v1 import AppTest
        dates = ['2026.08.29', '2026.08.30', '2026.09.01', '2026.09.02', '?']
        library = {'version': 1, 'puzzles': [dict(
            id=f'd{i}', username='Me', date=day, legacy=True, fen=chess.STARTING_FEN,
            played='h2h3', best_move='e2e4', accepted_moves=['e2e4'],
            solution=['e2e4', 'e7e5'], loss=300) for i, day in enumerate(dates)]}
        original = deepcopy(library)
        with patch('visualization_all.load_library', return_value=library), \
             patch('visualization_all.save_library') as save, \
             patch('visualization_all.drag_board', return_value=None):
            app = AppTest.from_string('from visualization_all import main\nmain()').run(timeout=30)
            app.selectbox(key='review_period').set_value('Date range').run()
            app.date_input(key='review_start_date').set_value(date(2026, 8, 30)).run()
            app.date_input(key='review_end_date').set_value(date(2026, 9, 1)).run()
            self.assertEqual(app.session_state['review_cycle']['ids'], ['d1', 'd2'])
            self.assertEqual([b.key for b in app.button if b.key and b.key.startswith('open-puzzle-')], ['open-puzzle-d1', 'open-puzzle-d2'])
            for _ in range(2):
                app.button(key='next_puzzle').click().run()
            app.button(key='restart_cycle').click().run()
            self.assertEqual(set(app.session_state['review_cycle']['ids']), {'d1', 'd2'})
            app.selectbox(key='ui_language').set_value('zh').run()
            self.assertEqual(app.date_input(key='review_start_date').value, date(2026, 8, 30))
            self.assertEqual(app.date_input(key='review_end_date').label, '复习结束日期')
            app.selectbox(key='ui_language').set_value('en').run()
            app.date_input(key='review_start_date').set_value(date(2026, 9, 3)).run()
            self.assertTrue(any('Start date must be' in item.value for item in app.error))
            self.assertFalse(app.exception)
            self.assertEqual(library, original)
            save.assert_not_called()

    def test_generate_passes_selected_range_and_disables_invalid_dates(self):
        from streamlit.testing.v1 import AppTest
        with patch('visualization_all.load_library', return_value={'version': 1, 'puzzles': []}), \
             patch('visualization_all.save_library'), \
             patch('visualization_all.fetch_chesscom_range', return_value=[pgn('2026.08.01')]) as fetch, \
             patch('visualization_all.fetch_chesscom_pgn') as monthly, \
             patch('visualization_all.engine_path', return_value='test'), \
             patch('visualization_all.analyze_game', return_value=[]), \
             patch('chess.engine.SimpleEngine.popen_uci'):
            app = AppTest.from_string('from visualization_all import main\nmain()').run(timeout=30)
            app.selectbox(key='analysis_period').set_value('Date range').run()
            app.date_input(key='analysis_start_date').set_value(date(2026, 8, 1)).run()
            app.date_input(key='analysis_end_date').set_value(date(2026, 8, 31)).run()
            app.text_input(key='analysis_username').set_value('Me')
            app.button(key='generate_puzzles').click().run()
            fetch.assert_called_once_with('Me', date(2026, 8, 1), date(2026, 8, 31), max_games=None)
            monthly.assert_not_called()
            app.date_input(key='analysis_start_date').set_value(date(2026, 9, 1)).run()
            self.assertTrue(app.button(key='generate_puzzles').disabled)
            self.assertFalse(app.exception)
