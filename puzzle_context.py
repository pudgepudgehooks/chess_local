"""Recover the opponent's preceding move from the actual game, without an engine."""
import chess
from puzzle_store import puzzle_key


def opponent_move(board):
    if not board.move_stack:
        return None
    before = board.copy()
    move = before.pop()
    return {'fen': before.fen(), 'uci': move.uci(), 'san': before.san(move)}


def enrich_puzzles(puzzles, games, username):
    """Update matching saved positions only; preserve IDs and all review history."""
    targets = {puzzle_key(p): p for p in puzzles}
    changed = []
    name = username.strip().casefold()
    for game in games:
        white, black = (game.headers.get(side, '') for side in ('White', 'Black'))
        if name not in (white.casefold(), black.casefold()):
            continue
        color = chess.WHITE if white.casefold() == name else chess.BLACK
        board = game.board()
        for move in game.mainline_moves():
            if board.turn == color and board.move_stack:
                key = puzzle_key(dict(id='', fen=board.fen(), played=move.uci(), username=username,
                    opponent=black if color else white, date=game.headers.get('Date', ''),
                    game_url=game.headers.get('Link') or game.headers.get('Site', '')))
                puzzle = targets.get(key)
                context = opponent_move(board)
                if puzzle is not None and puzzle.get('opponent_move') != context:
                    puzzle['opponent_move'] = context
                    changed.append(puzzle)
            board.push(move)
    return changed


def validated_opponent_move(board, context):
    if not isinstance(context, dict):
        return None
    try:
        before = chess.Board(context['fen'])
        move = before.parse_uci(context['uci'])
        if not before.is_valid() or before.turn == board.turn:
            return None
        san = before.san(move)
        before.push(move)
        return dict(context, san=san) if before.fen() == board.fen() else None
    except (KeyError, ValueError, TypeError):
        return None
