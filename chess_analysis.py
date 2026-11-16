"""Analyze personal mistakes. Importing this module does not run analysis."""
import argparse
import hashlib
import io
import os
from pathlib import Path
import shutil

import chess
import chess.engine
import chess.pgn
import requests


def engine_path(value=None):
    path = value or os.environ.get('STOCKFISH_PATH') or shutil.which('stockfish')
    if not path:
        raise ValueError('Set STOCKFISH_PATH or enter the Stockfish executable path.')
    return path


def fetch_chesscom_pgn(username, year, month):
    if not username.strip() or not 1 <= month <= 12:
        raise ValueError('Enter a username and valid month.')
    response = requests.get(
        f'https://api.chess.com/pub/player/{username.strip()}/games/{year}/{month:02d}',
        headers={'User-Agent': 'ChessMistakeTrainer/1.0'}, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or not isinstance(data.get('games'), list):
        raise ValueError('Archive response does not contain a games list.')
    return data


def read_games(text):
    stream = io.StringIO(text)
    while (game := chess.pgn.read_game(stream)) is not None:
        if game.errors:
            raise ValueError(f'Invalid PGN: {game.errors[0]}')
        yield game


def mistake_kind(before, after, threshold):
    if before.is_mate() or after.is_mate():
        if before.is_mate() and before > chess.engine.Cp(0) and not after.is_mate():
            return 'missed_mate', None
        if after.is_mate() and after < chess.engine.Cp(0) and not (
            before.is_mate() and before < chess.engine.Cp(0)):
            return 'allowed_mate', None
        return None, None
    loss = before.score() - after.score()
    return ('evaluation_drop', loss) if loss >= threshold else (None, loss)


def score_data(score):
    return {'cp': score.score(), 'mate': score.mate()}


def analyze_game(game, username, engine, depth=15, threshold=150, tolerance=30):
    name = username.strip().casefold()
    if not name:
        raise ValueError('Enter the username whose mistakes you want to study.')
    if game.headers.get('White', '').casefold() == name:
        color = chess.WHITE
    elif game.headers.get('Black', '').casefold() == name:
        color = chess.BLACK
    else:
        return []
    board = game.board()
    if board.chess960 or type(board) is not chess.Board:
        return []
    puzzles = []
    for move in game.mainline_moves():
        if board.turn != color:
            board.push(move)
            continue
        # Rank all first moves to identify acceptable alternatives consistently.
        lines = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=board.legal_moves.count())
        lines = [line for line in lines if line.get('pv')]
        if not lines:
            board.push(move)
            continue
        best = lines[0]
        before = best['score'].pov(color)
        actual = next((line for line in lines if line['pv'][0] == move), None)
        if actual is None:
            raise ValueError('Engine did not evaluate the played move.')
        after = actual['score'].pov(color)
        kind, loss = mistake_kind(before, after, threshold)
        accepted = []
        for line in lines:
            score = line['score'].pov(color)
            equivalent = (score.is_mate() and before.is_mate() and score == before) or (
                not score.is_mate() and not before.is_mate()
                and before.score() - score.score() <= tolerance)
            if equivalent:
                accepted.append(line['pv'][0].uci())
        if kind and move.uci() not in accepted and len(accepted) < board.legal_moves.count():
            fen = board.fen()
            source = game.headers.get('Link') or game.headers.get('Site', '')
            identity = '|'.join([name, source, game.headers.get('Date', ''),
                                 game.headers.get('White', ''), game.headers.get('Black', ''),
                                 fen, move.uci()])
            puzzles.append({
                'id': hashlib.sha256(identity.encode()).hexdigest()[:24],
                'username': username.strip(), 'fen': fen, 'played': move.uci(),
                'best_move': best['pv'][0].uci(), 'accepted_moves': accepted,
                'solution': [m.uci() for m in best['pv'][:10]],
                'loss': loss, 'kind': kind, 'before': score_data(before),
                'after': score_data(after), 'color': 'white' if color else 'black',
                'opponent': game.headers.get('Black' if color else 'White', '?'),
                'date': game.headers.get('Date', '?'), 'game_url': source,
                'move_number': board.fullmove_number, 'depth': depth})
        board.push(move)
    return puzzles


def main():
    from puzzle_store import load_library, merge_puzzles, save_library
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('username')
    parser.add_argument('--pgn', type=Path)
    parser.add_argument('--year', type=int)
    parser.add_argument('--month', type=int)
    parser.add_argument('--engine')
    parser.add_argument('--depth', type=int, default=15)
    parser.add_argument('--threshold', type=int, default=150)
    args = parser.parse_args()
    if args.depth < 1 or args.threshold < 1:
        parser.error('Depth and threshold must be positive.')
    if args.pgn:
        texts = [args.pgn.read_text(encoding='utf-8-sig')]
    elif args.year and args.month:
        texts = [g['pgn'] for g in fetch_chesscom_pgn(args.username, args.year, args.month)['games']
                 if g.get('rules', 'chess') == 'chess']
    else:
        parser.error('Provide --pgn or both --year and --month.')
    library = load_library()
    puzzles = []
    with chess.engine.SimpleEngine.popen_uci(engine_path(args.engine)) as engine:
        for text in texts:
            for game in read_games(text):
                puzzles.extend(analyze_game(game, args.username, engine, args.depth, args.threshold))
    added = merge_puzzles(library, puzzles)
    save_library(library)
    print(f"Added {added} puzzles; library contains {len(library['puzzles'])}.")


if __name__ == '__main__':
    main()
