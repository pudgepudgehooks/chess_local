"""One bounded worker per app process; PostgreSQL coordinates durable jobs."""
from itertools import islice
import logging
import re
import threading
import time

import chess.engine
from chess_analysis import analyze_game, read_games, count_player_moves

LOG = logging.getLogger(__name__)
MAX_BYTES = 1024 * 1024
MAX_GAMES = 5


def validate_payload(username, texts, depth, threshold, max_games=MAX_GAMES):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,50}', username.strip()):
        raise ValueError('Enter a valid player username (letters, numbers, underscores or hyphens).')
    if not 1 <= int(depth) <= 12 or not 0 <= int(threshold) <= 2000:
        raise ValueError('Analysis settings exceed beta limits.')
    if sum(len(text.encode('utf-8')) for text in texts) > MAX_BYTES:
        raise ValueError('Beta uploads are limited to 1 MB.')
    games = [game for text in texts for game in islice(read_games(text), max_games + 1)]
    if not games:
        raise ValueError('No games found in this import.')
    if len(games) > max_games:
        raise ValueError('Import at most five games per request.' if max_games == MAX_GAMES else
                         'Import at most 100 games when preparing a review.')
    name = username.strip().casefold()
    for game in games:
        if name not in [game.headers.get(c, '').casefold() for c in ['White', 'Black']]:
            raise ValueError('Every imported game must include your specified username.')
        board = game.board()
        if board.chess960 or type(board) is not chess.Board or not board.is_valid():
            raise ValueError('Only valid standard chess games are supported.')
        if sum(1 for _ in islice(game.mainline_moves(), 401)) > 400:
            raise ValueError('Beta games are limited to 400 half-moves.')
    return {'username': username.strip(), 'texts': texts, 'depth': int(depth), 'threshold': int(threshold)}


def run_job(store, job, path):
    import json
    try:
        payload = validate_payload(**json.loads(job['payload']))
        deadline = time.monotonic() + 600
        found = []
        games = [g for text in payload['texts'] for g in read_games(text)]
        totals = [count_player_moves(game, payload['username']) for game in games]
        total_positions = sum(totals)
        store.progress(job, 0, games_total=len(games), game_index=0,
                       positions_done=0, positions_total=total_positions)
        completed_positions = 0
        last_write = 0
        with chess.engine.SimpleEngine.popen_uci(path, timeout=10) as engine:
            engine.configure({'Threads': 1, 'Hash': 32})
            for count, game in enumerate(games, 1):
                def report(done, total):
                    nonlocal last_write
                    now = time.monotonic()
                    # Persist often enough for the UI without a DB write for every fast search.
                    if done == 0 or done == total or now - last_write >= 1:
                        store.progress(job, count if done == total else count - 1,
                            games_total=len(games), game_index=count,
                            positions_done=completed_positions + done, positions_total=total_positions)
                        last_write = now
                found.extend(analyze_game(game, payload['username'], engine, payload['depth'],
                    payload['threshold'], position_time=0.15, deadline=deadline, on_progress=report))
                completed_positions += totals[count - 1]
                store.progress(job, count, games_total=len(games), game_index=count,
                               positions_done=completed_positions, positions_total=total_positions)
        store.finish(job, found)
    except Exception:
        LOG.exception('Analysis job %s failed', job['id'])
        store.finish(job, [], error='Analysis failed or reached its time limit. Please try fewer games. Contact the beta owner if it repeats.')


class Worker:
    def __init__(self, store, path):
        self.store, self.path = store, path
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, name='chess-beta-worker', daemon=True)
        self.thread.start()

    def run(self):
        while not self.stop.is_set():
            try:
                job = self.store.claim()
                if job:
                    run_job(self.store, job, self.path)
                    continue
            except Exception:
                LOG.exception('Beta worker database operation failed')
            self.stop.wait(3)
