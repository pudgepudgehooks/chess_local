from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import chess
import chess.engine

from chess_analysis import analyze_game, fetch_chesscom_pgn, mistake_kind, read_games
from puzzle_store import is_due, load_library, merge_puzzles, record_review, save_library


PGN = '[White "Me"]\n[Black "Opponent"]\n[Site "https://example.com/game/1"]\n\n1. e4 e5 2. Nf3 Nc6 *'


class FakeEngine:
    def __init__(self):
        self.turns = []

    def analyse(self, board, limit, multipv):
        self.turns.append(board.turn)
        moves = list(board.legal_moves)
        target = chess.Move.from_uci('e2e4' if board.fullmove_number == 1 and board.turn else
                                     'e7e5' if board.fullmove_number == 1 else
                                     'g1f3' if board.turn else 'b8c6')
        alternatives = [m for m in moves if m != target]
        ranked = alternatives + ([target] if target in moves else [])
        return [{'score': chess.engine.PovScore(chess.engine.Cp(-400 if m == target else -10 if i == 1 else 0), board.turn),
                 'pv': [m]} for i, m in enumerate(ranked)]


class AnalysisTests(unittest.TestCase):
    def test_only_owner_moves_and_both_games(self):
        engine = FakeEngine()
        puzzles = [p for g in read_games(PGN + '\n\n' + PGN.replace('/1', '/2'))
                   for p in analyze_game(g, 'mE', engine)]
        self.assertEqual(len(puzzles), 4)
        self.assertTrue(all(engine.turns))
        self.assertEqual(len({p['id'] for p in puzzles}), 4)
        self.assertTrue(all('e2e4' not in p['accepted_moves'] for p in puzzles))
        self.assertTrue(all(len(p['accepted_moves']) > 1 for p in puzzles))

    def test_black_owner_and_unrelated_games(self):
        engine = FakeEngine()
        game = next(read_games(PGN))
        self.assertEqual(len(analyze_game(game, 'Opponent', engine)), 2)
        self.assertTrue(all(turn == chess.BLACK for turn in engine.turns))
        self.assertEqual(analyze_game(game, 'SomeoneElse', engine), [])

    def test_mate_classification(self):
        cp, mate = chess.engine.Cp, chess.engine.Mate
        self.assertEqual(mistake_kind(cp(50), cp(-150), 150), ('evaluation_drop', 200))
        self.assertEqual(mistake_kind(mate(3), cp(400), 150), ('missed_mate', None))
        self.assertEqual(mistake_kind(cp(50), mate(-2), 150), ('allowed_mate', None))
        self.assertIsNone(mistake_kind(mate(-5), mate(-2), 150)[0])
        self.assertIsNone(mistake_kind(cp(50), cp(0), 150)[0])

    @patch('chess_analysis.requests.get')
    def test_empty_archive_and_timeout(self, get):
        get.return_value.json.return_value = {'games': []}
        self.assertEqual(fetch_chesscom_pgn('Me', 2026, 6), {'games': []})
        self.assertEqual(get.call_args.kwargs['timeout'], 30)

    def test_promotion_and_castling_inputs(self):
        board = chess.Board('7k/P7/8/8/8/8/8/7K w - - 0 1')
        self.assertEqual(board.parse_san('a8=Q').uci(), 'a7a8q')
        self.assertEqual(board.parse_uci('a7a8n').promotion, chess.KNIGHT)
        board = chess.Board('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1')
        self.assertEqual(board.parse_san('O-O').uci(), 'e1g1')


class StoreTests(unittest.TestCase):
    def test_legacy_import_merge_and_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'puzzles.json'
            old = [{'fen': chess.STARTING_FEN, 'played': 'e2e4', 'best_move': 'd2d4', 'loss': 400}]
            legacy = path.parent / 'mistakes.json'
            legacy.write_text(json.dumps(old))
            library = load_library(path)
            puzzle = library['puzzles'][0]
            self.assertTrue(puzzle['legacy'])
            record_review(puzzle, True)
            self.assertEqual(merge_puzzles(library, [dict(puzzle, loss=500)]), 0)
            self.assertEqual(puzzle['review']['correct'], 1)
            save_library(library, path)
            self.assertEqual(load_library(path), library)
            self.assertEqual(json.loads(legacy.read_text()), old)

    def test_review_schedule(self):
        now = datetime(2026, 11, 16, tzinfo=timezone.utc)
        puzzle = {}
        self.assertTrue(is_due(puzzle, now))
        record_review(puzzle, True, now)
        self.assertFalse(is_due(puzzle, now))
        self.assertTrue(is_due(puzzle, now + timedelta(days=1)))
        record_review(puzzle, False, now)
        self.assertEqual(puzzle['review']['streak'], 0)
        self.assertTrue(is_due(puzzle, now + timedelta(minutes=10)))

    def test_invalid_library_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'puzzles.json'
            path.write_text('[]')
            with self.assertRaises(ValueError):
                load_library(path)
            self.assertEqual(path.read_text(), '[]')


if __name__ == '__main__':
    unittest.main()
