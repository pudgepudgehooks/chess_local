"""Puzzle persistence and review scheduling for one local app session."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIBRARY_PATH = ROOT / 'puzzles.json'


def load_library(path=LIBRARY_PATH):
    path = Path(path)
    if path.exists():
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or not isinstance(data.get('puzzles'), list):
            raise ValueError('Invalid puzzle library: expected a puzzles list.')
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
    return data


def save_library(data, path=LIBRARY_PATH):
    path = Path(path)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
    temporary.replace(path)


def merge_puzzles(library, puzzles):
    existing = {p['id']: p for p in library['puzzles']}
    added = 0
    for puzzle in puzzles:
        if puzzle['id'] in existing:
            review = existing[puzzle['id']].get('review')
            existing[puzzle['id']].update(puzzle)
            if review is not None:
                existing[puzzle['id']]['review'] = review
        else:
            library['puzzles'].append(puzzle)
            existing[puzzle['id']] = puzzle
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
