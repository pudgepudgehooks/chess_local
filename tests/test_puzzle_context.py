import io
from pathlib import Path
import tempfile
import unittest

import chess
import chess.pgn

from puzzle_context import opponent_move, validated_opponent_move, enrich_puzzles

PGN = '[White "Other"]\n[Black "Me"]\n[Site "https://lichess.org/abcd1234"]\n[Date "2026.11.26"]\n\n1. e4 e5 2. Nf3 Nc6 *'


class PuzzleContextTests(unittest.TestCase):
    def test_intro_handles_special_moves_and_rejects_unrelated_positions(self):
        cases = [('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1', 'e1g1'),
                 ('7k/P7/8/8/8/8/8/7K w - - 0 1', 'a7a8n'),
                 ('7k/8/8/3pP3/8/8/8/7K w - d6 0 1', 'e5d6'),
                 (chess.STARTING_FEN, 'e2e4')]
        self.assertIsNone(opponent_move(chess.Board()))
        for fen, uci in cases:
            board = chess.Board(fen)
            board.push_uci(uci)
            context = opponent_move(board)
            self.assertEqual(context['fen'], fen)
            self.assertEqual(context['uci'], uci)
            self.assertEqual(validated_opponent_move(board, context), context)
            self.assertIsNone(validated_opponent_move(chess.Board(), context))
        self.assertIsNone(validated_opponent_move(chess.Board(), {'fen':'invalid','uci':'e2e4'}))

    def puzzle(self):
        board = chess.Board()
        board.push_uci('e2e4')
        return dict(id='saved', username='Me', opponent='Other', date='2026.11.26',
            game_url='https://lichess.org/abcd1234', fen=board.fen(), played='e7e5', best_move='c7c5')

    def test_enrichment_uses_matching_game_and_keeps_review_history(self):
        puzzle = self.puzzle()
        puzzle['review'] = {'attempts':3, 'correct':1}
        other = dict(puzzle, id='other', username='AnotherPlayer')
        changed = enrich_puzzles([puzzle, other], [chess.pgn.read_game(io.StringIO(PGN))], 'Me')
        self.assertEqual(changed, [puzzle])
        self.assertEqual(puzzle['opponent_move']['uci'], 'e2e4')
        self.assertEqual(puzzle['review'], {'attempts':3, 'correct':1})
        self.assertNotIn('opponent_move', other)

    def test_cached_beta_game_gets_intro_without_reanalysis(self):
        from beta_store import BetaStore
        from beta_worker import validate_payload
        with tempfile.TemporaryDirectory() as directory:
            store = BetaStore('sqlite:///' + str(Path(directory) / 'context.db'))
            try:
                store.submit('alice', validate_payload('Me', [PGN], 10, 150))
                store.finish(store.claim(), [self.puzzle()])
                store.review('alice', 'saved', False, 'one')
                plan = store.prepare_analysis('alice', 'Me', [PGN], 10, 150)
                self.assertIsNone(plan['job_id'])
                puzzle = store.load('alice')['puzzles'][0]
                self.assertEqual(puzzle['opponent_move']['uci'], 'e2e4')
                self.assertEqual(puzzle['review']['attempts'], 1)
            finally:
                store.engine.dispose()
