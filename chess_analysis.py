"""Analyze personal mistakes. Importing this module does not run analysis."""
import argparse
import hashlib
import io
import os
from pathlib import Path
import shutil
import time
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

import chess
import chess.engine
import chess.pgn
import requests
from game_dates import validate_date_range, within_dates


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


def filter_games_by_date(texts, start, end):
    validate_date_range(start, end, max_days=366)
    return [game.accept(chess.pgn.StringExporter(headers=True, variations=False, comments=False))
            for text in texts for game in read_games(text)
            if within_dates(game.headers.get('Date'), start, end)]


def fetch_chesscom_range(username, start, end, max_games=None):
    """Read monthly archives newest first, filtering dates before applying limits."""
    validate_date_range(start, end, max_days=366)
    year, month = end.year, end.month
    selected = []
    while (year, month) >= (start.year, start.month):
        try:
            archive = fetch_chesscom_pgn(username, year, month)
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code != 404:
                raise
            archive = {'games': []}
        for entry in reversed(archive['games']):
            if entry.get('rules', 'chess') != 'chess' or not entry.get('pgn'):
                continue
            selected.extend(filter_games_by_date([entry['pgn']], start, end))
            if max_games is not None and len(selected) >= max_games:
                return selected[:max_games]
        year, month = (year - 1, 12) if month == 1 else (year, month - 1)
    return selected


def fetch_lichess_pgn(username, year, month, max_games=20):
    """Fetch bounded, completed standard games in a UTC calendar month."""
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,50}', username.strip()):
        raise ValueError('Enter a valid player username (letters, numbers, underscores or hyphens).')
    if not 2013 <= year <= 2200 or not 1 <= month <= 12 or not 1 <= max_games <= 100:
        raise ValueError('Choose a valid Lichess month (2013 or later) and 1–100 games.')
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end = datetime(year + (month == 12), 1 if month == 12 else month + 1, 1, tzinfo=timezone.utc)
    return _fetch_lichess_window(username, start, end, max_games)


def fetch_lichess_range(username, start, end, max_games=20):
    validate_date_range(start, end, max_days=366)
    if start.year < 2013 or end.year > 2200:
        raise ValueError('Choose a Lichess date range between 2013 and 2200.')
    start_time = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    end_time = datetime(end.year, end.month, end.day, tzinfo=timezone.utc) + timedelta(days=1)
    return filter_games_by_date(_fetch_lichess_window(username, start_time, end_time, max_games), start, end)


def _fetch_lichess_window(username, start, end, max_games):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,50}', username.strip()):
        raise ValueError('Enter a valid player username (letters, numbers, underscores or hyphens).')
    if not 1 <= max_games <= 100:
        raise ValueError('Choose a valid Lichess month (2013 or later) and 1–100 games.')
    params = {
        'since': max(1356998400070, int(start.timestamp() * 1000)),
        'until': int(end.timestamp() * 1000) - 1, 'max': max_games,
        'perfType': 'ultraBullet,bullet,blitz,rapid,classical,correspondence',
        'moves': 'true', 'tags': 'true', 'clocks': 'false', 'evals': 'false',
        'ongoing': 'false', 'finished': 'true', 'sort': 'dateDesc',
    }
    with requests.get(f'https://lichess.org/api/games/user/{username.strip()}', params=params,
                      headers={'Accept': 'application/x-chess-pgn', 'User-Agent': 'ChessMistakeTrainer/1.0'},
                      timeout=(10, 30), stream=True) as response:
        if response.status_code == 429:
            raise ValueError('Lichess is rate limiting requests. Wait at least one minute before retrying.')
        if response.status_code == 404:
            raise ValueError('Lichess username not found.')
        response.raise_for_status()
        chunks, size = [], 0
        for chunk in response.iter_content(chunk_size=16384):
            size += len(chunk)
            if size > 1024 * 1024:
                raise ValueError('Lichess download exceeded 1 MB. Request fewer games.')
            chunks.append(chunk)
    games = []
    for game in read_games(b''.join(chunks).decode('utf-8-sig')):
        board = game.board()
        if type(board) is chess.Board and not board.chess960 and game.headers.get('Result') != '*':
            games.append(game.accept(chess.pgn.StringExporter(headers=True, variations=False, comments=False)))
        if len(games) >= max_games:
            break
    return games


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


def count_player_moves(game, username):
    """Number of this player's positions that the engine will examine."""
    name = username.strip().casefold()
    if game.headers.get('White', '').casefold() == name:
        color = chess.WHITE
    elif game.headers.get('Black', '').casefold() == name:
        color = chess.BLACK
    else:
        return 0
    board = game.board()
    if board.chess960 or type(board) is not chess.Board:
        return 0
    offset = 0 if board.turn == color else 1
    return sum(1 for index, _ in enumerate(game.mainline_moves()) if index % 2 == offset)


def analyze_game(game, username, engine, depth=15, threshold=150, tolerance=30,
                 position_time=None, deadline=None, on_progress=None):
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
    total = count_player_moves(game, username)
    completed = 0
    if on_progress:
        on_progress(0, total)
    for move in game.mainline_moves():
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError('Analysis time limit reached')
        if board.turn != color:
            board.push(move)
            continue
        # Rank all first moves to identify acceptable alternatives consistently.
        lines = engine.analyse(board, chess.engine.Limit(depth=depth, time=position_time), multipv=board.legal_moves.count())
        lines = [line for line in lines if line.get('pv')]
        if not lines:
            raise ValueError('Engine did not return a usable analysis for this position.')
        best = lines[0]
        before = best['score'].pov(color)
        actual = next((line for line in lines if line['pv'][0] == move), None)
        if actual is None and position_time is not None:
            actual = engine.analyse(board, chess.engine.Limit(depth=depth, time=position_time), root_moves=[move])
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
                'accepted_lines': {line['pv'][0].uci(): [m.uci() for m in line['pv'][:10]]
                                   for line in lines if line['pv'][0].uci() in accepted},
                'solution': [m.uci() for m in best['pv'][:10]],
                'loss': loss, 'kind': kind, 'before': score_data(before),
                'after': score_data(after), 'color': 'white' if color else 'black',
                'opponent': game.headers.get('Black' if color else 'White', '?'),
                'date': game.headers.get('Date', '?'), 'game_url': source,
                'platform': 'Lichess' if urlparse(source).hostname == 'lichess.org' else
                            'Chess.com' if (urlparse(source).hostname or '').endswith('.chess.com') or urlparse(source).hostname == 'chess.com' else 'PGN',
                'move_number': board.fullmove_number, 'depth': depth})
        board.push(move)
        completed += 1
        if on_progress:
            on_progress(completed, total)
    return puzzles


def main():
    from puzzle_store import load_library, merge_puzzles, save_library
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('username')
    parser.add_argument('--pgn', type=Path)
    parser.add_argument('--year', type=int)
    parser.add_argument('--month', type=int)
    parser.add_argument('--source', choices=['chesscom', 'lichess'], default='chesscom')
    parser.add_argument('--max-games', type=int, default=20, help='Lichess import limit, 1–100')
    parser.add_argument('--engine')
    parser.add_argument('--depth', type=int, default=15)
    parser.add_argument('--threshold', type=int, default=150)
    args = parser.parse_args()
    if args.depth < 1 or args.threshold < 1:
        parser.error('Depth and threshold must be positive.')
    if args.pgn:
        texts = [args.pgn.read_text(encoding='utf-8-sig')]
    elif args.year and args.month:
        if args.source == 'lichess':
            texts = fetch_lichess_pgn(args.username, args.year, args.month, args.max_games)
        else:
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
