"""Completed game coverage; lower thresholds and deeper searches cover more."""
from datetime import datetime, timezone
import hashlib
import json

import chess
import chess.pgn

from chess_analysis import read_games
from puzzle_store import puzzle_key

LOCAL_POLICY = 'local-depth-v1'
BETA_POLICY = 'beta-0.15s-v1'


def game_items(username, texts):
    player = username.strip().casefold()
    result, seen = [], set()
    for text in texts:
        for game in read_games(text):
            names = [game.headers.get(color, '').strip().casefold() for color in ('White', 'Black')]
            if player not in names:
                raise ValueError('Every imported game must include your specified username.')
            board = game.board()
            if type(board) is not chess.Board or board.chess960 or not board.is_valid():
                raise ValueError('Only valid standard chess games are supported.')
            moves = [move.uci() for move in game.mainline_moves()]
            context = puzzle_key(dict(id='', fen=board.fen(), played=moves[0] if moves else '0000',
                username=player, opponent=names[1] if names[0] == player else names[0],
                date=game.headers.get('Date', ''), game_url=game.headers.get('Link') or game.headers.get('Site', '')))
            key = hashlib.sha256(json.dumps([context, moves], sort_keys=True).encode()).hexdigest()
            if key not in seen:
                result.append(dict(game_key=key, game=game, player=player,
                    text=game.accept(chess.pgn.StringExporter(headers=True, variations=False, comments=False))))
                seen.add(key)
    return result


def plan_analysis(username, texts, records, depth, threshold, policy, limit=None):
    items = game_items(username, texts)
    missing = [item for item in items if not any(
        record['game_key'] == item['game_key'] and record['policy'] == policy
        and record['depth'] >= depth and record['threshold'] <= threshold for record in records)]
    selected = missing if limit is None else missing[:limit]
    return dict(items=selected, reused=len(items) - len(missing),
                selected=len(selected), remaining=len(missing) - len(selected), fetched=len(items))


def coverage_records(username, texts, depth, threshold, policy):
    now = datetime.now(timezone.utc).isoformat()
    return [dict(game_key=item['game_key'], player=item['player'], depth=depth,
                 threshold=threshold, policy=policy, completed_at=now)
            for item in game_items(username, texts)]


def merge_coverage(library, records):
    existing = {(r['game_key'], r['depth'], r['threshold'], r['policy']): r
                for r in library.get('analyses', [])}
    for record in records:
        existing[record['game_key'], record['depth'], record['threshold'], record['policy']] = record
    library['analyses'] = list(existing.values())
