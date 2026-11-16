"""One bounded worker per app process; PostgreSQL coordinates durable jobs."""
from itertools import islice
import logging
import re
import threading
import time

import chess.engine
from chess_analysis import analyze_game, read_games

LOG = logging.getLogger(__name__)
MAX_BYTES = 1024 * 1024
MAX_GAMES = 5


def validate_payload(username, texts, depth, threshold):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,50}', username.strip()):
        raise ValueError('Enter a valid player username (letters, numbers, underscores or hyphens).')
    if not 1 <= int(depth) <= 12 or not 50 <= int(threshold) <= 2000:
        raise ValueError('Analysis settings exceed beta limits.')
    if sum(len(text.encode('utf-8')) for text in texts) > MAX_BYTES:
        raise ValueError('Beta uploads are limited to 1 MB.')
    games = [game for text in texts for game in islice(read_games(text), MAX_GAMES + 1)]
    if not games:
        raise ValueError('No games found in this import.')
    if len(games) > MAX_GAMES:
        raise ValueError('Import at most five games per request.')
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
        with chess.engine.SimpleEngine.popen_uci(path, timeout=10) as engine:
            engine.configure({'Threads': 1, 'Hash': 32})
            for count, game in enumerate((g for t in payload['texts'] for g in read_games(t)), 1):
                found.extend(analyze_game(game, payload['username'], engine, payload['depth'],
                    payload['threshold'], position_time=0.15, deadline=deadline))
                store.progress(job, count)
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
