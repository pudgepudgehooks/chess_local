import importlib.util
import unittest
import chess


@unittest.skipUnless(importlib.util.find_spec('streamlit'), 'Streamlit is not installed')
class DragBoardTests(unittest.TestCase):
    def test_replayed_and_stale_events_do_not_repeat_reviews(self):
        from drag_board import consume_move
        board = chess.Board()
        seen = []
        event = {'fen': board.fen(), 'event_id': 'one', 'uci': 'e2e4'}
        self.assertEqual(consume_move(event, board, seen).uci(), 'e2e4')
        self.assertIsNone(consume_move(event, board, seen))
        self.assertIsNone(consume_move(dict(event, event_id='two', fen='old position'), board, seen))
        self.assertIsNone(consume_move(dict(event, event_id='three', uci='e2e5'), board, seen))

    def test_promotion_castling_and_en_passant(self):
        from drag_board import consume_move
        cases = [
            ('7k/P7/8/8/8/8/8/7K w - - 0 1', 'a7a8n'),
            ('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1', 'e1g1'),
            ('7k/8/8/3pP3/8/8/8/7K w - d6 0 1', 'e5d6'),
        ]
        for fen, uci in cases:
            board = chess.Board(fen)
            self.assertEqual(consume_move({'fen': fen, 'event_id': uci, 'uci': uci}, board, []).uci(), uci)
