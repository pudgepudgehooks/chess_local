"""Offline Streamlit board component and defensive move-event handling."""
from pathlib import Path
import chess
import chess.svg
from streamlit.components.v1 import declare_component

_component = declare_component('chess_drag_board', path=str(Path(__file__).parent / 'board_component'))


def drag_board(board, key):
    return _component(
        fen=board.fen(), white=board.turn == chess.WHITE,
        pieces={chess.square_name(s): {
            'svg': chess.svg.piece(p),
            'label': f"{'White' if p.color else 'Black'} {chess.piece_name(p.piece_type)}",
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
        return board.parse_uci(event.get('uci', ''))
    except (ValueError, TypeError):
        return None
