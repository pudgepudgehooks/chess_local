"""Durable, owner-scoped beta storage. PostgreSQL in production; SQLite in tests."""
import hashlib
import json
import time
import uuid

from sqlalchemy import (Column, Float, Integer, MetaData, String, Table, Text,
                        create_engine, select, update, delete, func)
from sqlalchemy.exc import IntegrityError
from puzzle_store import record_review, deduplicate_puzzles, merge_puzzles
from analysis_cache import BETA_POLICY, plan_analysis, coverage_records

meta = MetaData()
puzzles = Table('beta_puzzles', meta,
    Column('owner', String(64), primary_key=True), Column('id', String(64), primary_key=True),
    Column('data', Text, nullable=False))
events = Table('beta_reviews', meta,
    Column('owner', String(64), primary_key=True), Column('event', String(100), primary_key=True),
    Column('puzzle_id', String(64), nullable=False), Column('created', Float, nullable=False))
jobs = Table('beta_jobs', meta,
    Column('id', String(64), primary_key=True), Column('owner', String(64), nullable=False),
    Column('fingerprint', String(64), nullable=False), Column('payload', Text, nullable=False),
    Column('state', String(16), nullable=False), Column('created', Float, nullable=False),
    Column('lease', Float, nullable=False, default=0), Column('token', String(64)),
    Column('completed', Integer, nullable=False, default=0), Column('message', Text, nullable=False, default=''))
guard = Table('beta_queue_guard', meta, Column('id', Integer, primary_key=True))
job_progress = Table('beta_job_progress', meta,
    Column('job_id', String(64), primary_key=True),
    Column('games_total', Integer, nullable=False), Column('game_index', Integer, nullable=False),
    Column('positions_done', Integer, nullable=False), Column('positions_total', Integer, nullable=False))
analyses = Table('beta_game_analyses', meta,
    Column('owner', String(64), primary_key=True), Column('game_key', String(64), primary_key=True),
    Column('policy', String(40), primary_key=True), Column('depth', Integer, primary_key=True),
    Column('threshold', Integer, primary_key=True), Column('player', String(50), nullable=False),
    Column('completed_at', String(64), nullable=False))


class BetaStore:
    def __init__(self, url):
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql+psycopg://', 1)
        elif url.startswith('postgresql://'):
            url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
        self.engine = create_engine(url, pool_pre_ping=True)
        meta.create_all(self.engine)
        try:
            with self.engine.begin() as db:
                db.execute(guard.insert().values(id=1))
        except IntegrityError:
            pass

    def load(self, owner):
        with self.engine.begin() as db:
            db.execute(select(guard).where(guard.c.id == 1).with_for_update()).first()
            return self._load_library(db, owner)

    def _load_library(self, db, owner):
        """Compact historical duplicate rows under the review/generation lock."""
        rows = db.execute(select(puzzles.c.data).where(puzzles.c.owner == owner).order_by(puzzles.c.id))
        unique, aliases = deduplicate_puzzles([json.loads(r[0]) for r in rows])
        if aliases:
            for puzzle in unique:
                db.execute(update(puzzles).where(puzzles.c.owner == owner, puzzles.c.id == puzzle['id'])
                           .values(data=json.dumps(puzzle)))
            for duplicate, canonical in aliases.items():
                db.execute(update(events).where(events.c.owner == owner, events.c.puzzle_id == duplicate)
                           .values(puzzle_id=canonical))
                db.execute(delete(puzzles).where(puzzles.c.owner == owner, puzzles.c.id == duplicate))
        return {'version': 1, 'puzzles': unique}

    def review(self, owner, puzzle_id, correct, event):
        with self.engine.begin() as db:
            # Serialize reviews and generation commits to avoid lost review updates.
            db.execute(select(guard).where(guard.c.id == 1).with_for_update()).first()
            row = db.execute(select(puzzles.c.data).where(
                puzzles.c.owner == owner, puzzles.c.id == puzzle_id).with_for_update()).first()
            if row is None:
                raise ValueError('Puzzle not found in your library.')
            previous = db.execute(select(events.c.event).where(events.c.owner == owner, events.c.event == event)).first()
            if previous:
                return json.loads(row[0])
            puzzle = json.loads(row[0])
            record_review(puzzle, correct)
            db.execute(events.insert().values(owner=owner, event=event, puzzle_id=puzzle_id, created=time.time()))
            db.execute(update(puzzles).where(puzzles.c.owner == owner, puzzles.c.id == puzzle_id).values(data=json.dumps(puzzle)))
            return puzzle

    def coverage(self, owner):
        with self.engine.connect() as db:
            return [dict(row) for row in db.execute(select(analyses).where(analyses.c.owner == owner)).mappings()]

    def prepare_analysis(self, owner, username, texts, depth, threshold):
        from beta_worker import validate_payload
        payload = validate_payload(username, texts, depth, threshold, max_games=100)
        username = payload['username']
        plan = plan_analysis(username, texts, self.coverage(owner), depth, threshold, BETA_POLICY, limit=5)
        selected = [item['text'] for item in plan.pop('items')]
        plan['job_id'] = self.submit(owner, dict(payload, texts=selected), allow_completed=False) if selected else None
        return plan

    def submit(self, owner, payload, allow_completed=True):
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        now = time.time()
        with self.engine.begin() as db:
            db.execute(select(guard).where(guard.c.id == 1).with_for_update()).first()
            reusable = jobs.c.state != 'failed' if allow_completed else jobs.c.state.in_(['queued', 'running'])
            previous = db.execute(select(jobs).where(jobs.c.owner == owner,
                jobs.c.fingerprint == fingerprint, reusable).order_by(jobs.c.created.desc())).mappings().first()
            if previous:
                return previous['id']
            active = db.scalar(select(func.count()).select_from(jobs).where(
                jobs.c.owner == owner, jobs.c.state.in_(['queued', 'running'])))
            if active:
                raise ValueError('You already have an analysis queued or running.')
            queued = db.scalar(select(func.count()).select_from(jobs).where(jobs.c.state.in_(['queued', 'running'])))
            if queued >= 20:
                raise ValueError('The beta analysis queue is full. Please try again later.')
            job_id = uuid.uuid4().hex
            db.execute(jobs.insert().values(id=job_id, owner=owner, fingerprint=fingerprint,
                payload=json.dumps(payload), state='queued', created=now, lease=0, completed=0, message='Waiting for analysis'))
            return job_id

    def recent_jobs(self, owner):
        with self.engine.connect() as db:
            rows = db.execute(select(jobs.c.id, jobs.c.state, jobs.c.completed, jobs.c.message,
                job_progress.c.games_total, job_progress.c.game_index,
                job_progress.c.positions_done, job_progress.c.positions_total).select_from(
                jobs.outerjoin(job_progress, jobs.c.id == job_progress.c.job_id)).where(
                jobs.c.owner == owner).order_by(jobs.c.created.desc()).limit(5))
            return [dict(r._mapping) for r in rows]

    def claim(self):
        now = time.time()
        with self.engine.begin() as db:
            db.execute(select(guard).where(guard.c.id == 1).with_for_update()).first()
            db.execute(update(jobs).where(jobs.c.state == 'running', jobs.c.lease < now).values(state='queued'))
            if db.scalar(select(func.count()).select_from(jobs).where(jobs.c.state == 'running')):
                return None
            row = db.execute(select(jobs).where(jobs.c.state == 'queued').order_by(jobs.c.created).limit(1)).mappings().first()
            if not row:
                return None
            token = uuid.uuid4().hex
            db.execute(update(jobs).where(jobs.c.id == row['id']).values(
                state='running', token=token, lease=now + 900, message='Analyzing games', completed=0))
            db.execute(job_progress.delete().where(job_progress.c.job_id == row['id']))
            return dict(row, token=token)

    def progress(self, job, count, *, games_total=None, game_index=None, positions_done=None, positions_total=None):
        with self.engine.begin() as db:
            result = db.execute(update(jobs).where(jobs.c.id == job['id'], jobs.c.token == job['token'],
                jobs.c.state == 'running').values(completed=count))
            if not result.rowcount or games_total is None:
                return
            details = dict(games_total=games_total, game_index=game_index,
                           positions_done=positions_done, positions_total=positions_total)
            previous = db.execute(select(job_progress.c.job_id).where(job_progress.c.job_id == job['id'])).first()
            if previous:
                db.execute(update(job_progress).where(job_progress.c.job_id == job['id']).values(**details))
            else:
                db.execute(job_progress.insert().values(job_id=job['id'], **details))

    def finish(self, job, found, error=None):
        with self.engine.begin() as db:
            db.execute(select(guard).where(guard.c.id == 1).with_for_update()).first()
            row = db.execute(select(jobs).where(jobs.c.id == job['id'], jobs.c.token == job['token'],
                jobs.c.state == 'running').with_for_update()).first()
            if row is None:
                return
            added = 0
            if error is None:
                library = self._load_library(db, job['owner'])
                before = {p['id']: json.dumps(p) for p in library['puzzles']}
                added = merge_puzzles(library, found)
                for puzzle in library['puzzles']:
                    data = json.dumps(puzzle)
                    if puzzle['id'] in before:
                        if before[puzzle['id']] != data:
                            db.execute(update(puzzles).where(puzzles.c.owner == job['owner'], puzzles.c.id == puzzle['id']).values(data=data))
                    else:
                        db.execute(puzzles.insert().values(owner=job['owner'], id=puzzle['id'], data=data))
                payload = json.loads(row._mapping['payload'])
                if all(key in payload for key in ('username', 'texts', 'depth', 'threshold')):
                    for record in coverage_records(**payload, policy=BETA_POLICY):
                        identity = [analyses.c.owner == job['owner'], analyses.c.game_key == record['game_key'],
                                    analyses.c.policy == record['policy'], analyses.c.depth == record['depth'],
                                    analyses.c.threshold == record['threshold']]
                        if not db.execute(select(analyses.c.game_key).where(*identity)).first():
                            db.execute(analyses.insert().values(owner=job['owner'], **record))
            db.execute(update(jobs).where(jobs.c.id == job['id']).values(state='failed' if error else 'done',
                message=error or f'Added {added} puzzles. Your library is up to date.', payload='{}'))


class UserLibrary:
    def __init__(self, store, owner, authorize=None, default_username=None):
        self.store, self.owner = store, owner
        self.authorize = authorize
        self.default_username = default_username

    def _check_access(self):
        if self.authorize is not None and not self.authorize():
            raise PermissionError('Your session expired. Please sign in again.')

    def load(self):
        self._check_access()
        return self.store.load(self.owner)

    def review(self, puzzle, correct, event):
        self._check_access()
        return self.store.review(self.owner, puzzle['id'], correct, event)

    def submit(self, username, texts, depth, threshold):
        self._check_access()
        from beta_worker import validate_payload
        payload = validate_payload(username, texts, depth, threshold)
        return self.store.submit(self.owner, payload)

    def prepare_analysis(self, username, texts, depth, threshold):
        self._check_access()
        return self.store.prepare_analysis(self.owner, username, texts, depth, threshold)

    def recent_jobs(self):
        self._check_access()
        return self.store.recent_jobs(self.owner)
