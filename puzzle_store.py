"""Puzzle persistence and review scheduling for one local app session."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
import chess

ROOT = Path(__file__).resolve().parent
LIBRARY_PATH = ROOT / 'puzzles.json'


def puzzle_month(puzzle):
    """Group saved puzzles by game month, including PGNs with an unknown day."""
    value = puzzle.get('date')
    match = re.fullmatch(r'([0-9]{4})([.-])([0-9]{2})(?:\2(?:[0-9]{2}|\?\?))?', value.strip()) if isinstance(value, str) else None
    if not match or int(match[1]) == 0 or not 1 <= int(match[3]) <= 12:
        return 'Unknown date'
    return f'{match[1]}-{match[3]}'


def meets_review_loss(puzzle, minimum):
    """A positive review threshold requires a recorded numeric centipawn loss."""
    if minimum == 0:
        return True
    loss = puzzle.get('loss')
    return isinstance(loss, (int, float)) and not isinstance(loss, bool) and loss >= minimum


def puzzle_key(puzzle):
    """Identify a player's game position independently of analysis settings/IDs."""
    try:
        position = chess.Board(puzzle['fen']).fen()
        played = chess.Move.from_uci(puzzle['played'].strip().lower()).uci()
    except (KeyError, TypeError, ValueError, AttributeError):
        return ('id', puzzle['id'])
    player = (puzzle.get('username') or '').strip().casefold()
    source = puzzle.get('game_url') or ''
    try:
        url = urlsplit(source)
        host = (url.hostname or '').removeprefix('www.').lower()
        path = url.path.strip('/')
        if host == 'chess.com':
            match = re.fullmatch(r'(?:game/(live|daily)|(live|daily)/game)/([0-9]+)', path)
            if match:
                path = f'game/{match[1] or match[2]}/{match[3]}'
        elif host == 'lichess.org':
            match = re.fullmatch(r'([A-Za-z0-9]{8})(?:[A-Za-z0-9]{4})?(?:/(?:white|black))?', path)
            if match:
                path = match[1]
        game = ('url', host, path) if host and path else None
    except ValueError:
        game = None
    if game is None:
        # PGNs without a game link still carry player/date/position metadata.
        game = ('pgn', (puzzle.get('date') or '').replace('.', '-'),
                (puzzle.get('opponent') or '').strip().casefold())
    return (player, game, position, played)


def combine_reviews(first, second):
    """Keep duplicate copies of a review once; retain distinct recorded attempts."""
    if not first or not second or first == second:
        return dict(first or second or {})
    latest = max([first, second], key=lambda review: review.get('last_review', ''))
    return dict(latest, attempts=first.get('attempts', 0) + second.get('attempts', 0),
                correct=first.get('correct', 0) + second.get('correct', 0))


def deduplicate_puzzles(items):
    """Retain stable existing IDs, returning aliases for redundant stored rows."""
    result, by_id, by_key, aliases = [], {}, {}, {}
    for puzzle in items:
        key = puzzle_key(puzzle)
        existing = by_id.get(puzzle['id']) or by_key.get(key)
        if existing is None:
            result.append(puzzle)
            existing = puzzle
        else:
            canonical_id = existing['id']
            review = combine_reviews(existing.get('review'), puzzle.get('review'))
            existing.update(puzzle)
            existing['id'] = canonical_id
            if review:
                existing['review'] = review
            if puzzle['id'] != canonical_id:
                aliases[puzzle['id']] = canonical_id
        by_id[puzzle['id']] = existing
        by_key[key] = existing
    return result, aliases


def load_library(path=LIBRARY_PATH):
    path = Path(path)
    if path.exists():
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or not isinstance(data.get('puzzles'), list):
            raise ValueError('Invalid puzzle library: expected a puzzles list.')
        data['puzzles'], _ = deduplicate_puzzles(data['puzzles'])
        return data
    data = {'version': 1, 'puzzles': []}
    legacy = path.parent / 'mistakes.json'
    if legacy.exists():
        for old in json.loads(legacy.read_text(encoding='utf-8')):
            puzzle = dict(old)
            puzzle['id'] = hashlib.sha256((old['fen'] + old['played']).encode()).hexdigest()[:24]
            puzzle['legacy'] = True
            puzzle['best_move'] = puzzle.get('best_move', puzzle.get('best'))
            puzzle['accepted_moves'] = [puzzle['best_move']]
            data['puzzles'].append(puzzle)
    data['puzzles'], _ = deduplicate_puzzles(data['puzzles'])
    return data


def save_library(data, path=LIBRARY_PATH):
    data['puzzles'], _ = deduplicate_puzzles(data['puzzles'])
    path = Path(path)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
    temporary.replace(path)


def merge_puzzles(library, puzzles):
    library['puzzles'], _ = deduplicate_puzzles(library['puzzles'])
    existing = {p['id']: p for p in library['puzzles']}
    by_key = {puzzle_key(p): p for p in library['puzzles']}
    added = 0
    for puzzle in puzzles:
        key = puzzle_key(puzzle)
        previous = existing.get(puzzle['id']) or by_key.get(key)
        if previous is not None:
            review, canonical_id = previous.get('review'), previous['id']
            previous.update(puzzle)
            previous['id'] = canonical_id
            if review is not None:
                previous['review'] = review
            existing[puzzle['id']] = previous
            by_key[key] = previous
        else:
            library['puzzles'].append(puzzle)
            existing[puzzle['id']] = puzzle
            by_key[key] = puzzle
            added += 1
    return added


def record_review(puzzle, correct, now=None):
    now = now or datetime.now(timezone.utc)
    review = puzzle.setdefault('review', {})
    review['attempts'] = review.get('attempts', 0) + 1
    review['correct'] = review.get('correct', 0) + int(correct)
    review['streak'] = review.get('streak', 0) + 1 if correct else 0
    days = min(30, 2 ** min(review['streak'] - 1, 5)) if correct else 0
    review['last_review'] = now.isoformat()
    review['next_review'] = (now + (timedelta(days=days) if correct else timedelta(minutes=10))).isoformat()


def is_due(puzzle, now=None):
    due = puzzle.get('review', {}).get('next_review')
    return not due or datetime.fromisoformat(due) <= (now or datetime.now(timezone.utc))
