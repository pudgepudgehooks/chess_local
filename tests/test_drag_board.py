import importlib.util
import unittest
import chess


@unittest.skipUnless(importlib.util.find_spec('streamlit'), 'Streamlit is not installed')
class DragBoardTests(unittest.TestCase):
    def test_preloaded_positions_reuse_legal_previews(self):
        from drag_board import prepare_board
        prepare_board.cache_clear()
        fen = chess.STARTING_FEN
        prepared = prepare_board(fen)
        self.assertIs(prepare_board(fen), prepared)
        board = chess.Board(fen)
        self.assertEqual(set(prepared['legal']), {m.uci() for m in board.legal_moves})
        for uci, preview in prepared['previews'].items():
            after = board.copy()
            after.push_uci(uci)
            self.assertEqual(after.fen(), preview)

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

    def test_playback_frames_follow_a_legal_continuation(self):
        from drag_board import playback_frames
        board = chess.Board()
        line = ['d2d4', 'd7d5', 'c2c4', 'e7e6']
        frames = playback_frames(board, chess.Move.from_uci(line[0]), {'best_move': line[0], 'solution': line})
        self.assertEqual([frame['uci'] for frame in frames], line)
        for uci, frame in zip(line, frames):
            board.push_uci(uci)
            self.assertEqual(frame['fen'], board.fen())

    def test_alternative_does_not_play_the_best_moves_unrelated_line(self):
        from drag_board import playback_frames
        board = chess.Board()
        frames = playback_frames(board, board.parse_uci('e2e4'), {'best_move': 'd2d4', 'solution': ['d2d4', 'd7d5']})
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0]['uci'], 'e2e4')

    def test_special_move_previews_and_playback(self):
        from drag_board import playback_frames
        cases = [('7k/P7/8/8/8/8/8/7K w - - 0 1', 'a7a8n'),
                 ('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1', 'e1g1'),
                 ('7k/8/8/3pP3/8/8/8/7K w - d6 0 1', 'e5d6')]
        for fen, uci in cases:
            board = chess.Board(fen)
            frames = playback_frames(board, chess.Move.from_uci(uci), {'best_move': uci})
            board.push_uci(uci)
            self.assertEqual(frames[0]['fen'], board.fen())
