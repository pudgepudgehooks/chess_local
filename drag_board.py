"""Offline Streamlit board component and defensive move-event handling."""
from pathlib import Path
import chess
import chess.svg
import chess.engine
from streamlit.components.v1 import declare_component
from i18n import tr, language
from board_theme import BOARD_COLORS

_component = declare_component('chess_drag_board', path=str(Path(__file__).parent / 'board_component'))


def playback_frames(board, move, puzzle, executable=None):
    """Return legal board snapshots, starting with the user's accepted move."""
    line = puzzle.get('accepted_lines', {}).get(move.uci())
    if not line and move.uci() == puzzle['best_move']:
        line = puzzle.get('solution')
    follow = list(line[1:10]) if line and line[0] == move.uci() else []
    position = board.copy()
    frames = []
    def append(candidate):
        if candidate not in position.legal_moves:
            return False
        san = position.san(candidate)
        position.push(candidate)
        frames.append({'fen': position.fen(), 'uci': candidate.uci(), 'san': san})
        return True
    append(move)
    for uci in follow:
        try:
            if not append(chess.Move.from_uci(uci)):
                break
        except ValueError:
            break
    # Old puzzles and accepted alternatives may not have a saved continuation.
    if len(frames) == 1 and not position.is_game_over() and executable:
        with chess.engine.SimpleEngine.popen_uci(executable, timeout=10) as engine:
            engine.configure({'Threads': 1, 'Hash': 32})
            info = engine.analyse(position, chess.engine.Limit(time=0.4, depth=12))
            for candidate in info.get('pv', [])[:9]:
                if not append(candidate):
                    break
    return frames


def drag_board(board, key, response=None):
    previews = {}
    for move in board.legal_moves:
        after = board.copy()
        after.push(move)
        previews[move.uci()] = after.fen()
    return _component(
        fen=board.fen(), white=board.turn == chess.WHITE,
        response=response, previews=previews, colors=BOARD_COLORS,
        assets={chess.Piece(piece, color).symbol(): {
            'svg': chess.svg.piece(chess.Piece(piece, color)),
            'label': f"{tr('White' if color else 'Black')} {tr(chess.piece_name(piece))}",
        } for color in [chess.WHITE, chess.BLACK] for piece in chess.PIECE_TYPES},
        language=language(),
        labels={key: tr(key) for key in [
            'Chess puzzle board', 'empty',
            'Move submitted. See the result below the board.', 'Illegal move. Try another destination.',
            'Promote to:', 'Queen', 'Rook', 'Bishop', 'Knight', 'Cancel', 'Choose your promotion piece.',
            'Checking move…', 'The answer is incorrect, please try again',
            'Correct! Use Forward and Back to review the continuation.', 'Click Next Puzzle to proceed.',
            'Back', 'Forward', 'Starting position.', 'Step {step}/{total}: {move}',
            'Correct! No continuation is available for this position.',
            'Could not save your review. Please try again.',
        ]},
        pieces={chess.square_name(s): {
            'svg': chess.svg.piece(p),
            'label': f"{tr('White' if p.color else 'Black')} {tr(chess.piece_name(p.piece_type))}",
            'own': p.color == board.turn,
        } for s, p in board.piece_map().items()},
        legal=[m.uci() for m in board.legal_moves], key=key, default=None,
    )


def consume_move(event, board, seen):
    """Ignore stale/replayed component values; validate moves on the server."""
    if not isinstance(event, dict) or event.get('fen') != board.fen():
        return None
    event_id = event.get('event_id')
    if not isinstance(event_id, str) or not event_id or event_id in seen:
        return None
    seen.append(event_id)
    del seen[:-100]
    try:
        move = board.parse_uci(event.get('uci', ''))
        return move if move in board.legal_moves else None
    except (ValueError, TypeError):
        return None
