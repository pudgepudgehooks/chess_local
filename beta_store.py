"""Durable, owner-scoped beta storage. PostgreSQL in production; SQLite in tests."""
import hashlib
import json
import time
import uuid

from sqlalchemy import (Column, Float, Integer, MetaData, String, Table, Text,
                        create_engine, select, update, func)
from sqlalchemy.exc import IntegrityError
from puzzle_store import record_review

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
        with self.engine.connect() as db:
            rows = db.execute(select(puzzles.c.data).where(puzzles.c.owner == owner).order_by(puzzles.c.id))
            return {'version': 1, 'puzzles': [json.loads(r[0]) for r in rows]}

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

    def submit(self, owner, payload):
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        now = time.time()
        with self.engine.begin() as db:
            db.execute(select(guard).where(guard.c.id == 1).with_for_update()).first()
            previous = db.execute(select(jobs).where(jobs.c.owner == owner,
                jobs.c.fingerprint == fingerprint, jobs.c.state != 'failed').order_by(jobs.c.created.desc())).mappings().first()
            if previous:
                return previous['id']
            active = db.scalar(select(func.count()).select_from(jobs).where(
                jobs.c.owner == owner, jobs.c.state.in_(['queued', 'running'])))
            if active:
                raise ValueError('You already have an analysis queued or running.')
            daily = db.scalar(select(func.count()).select_from(jobs).where(jobs.c.owner == owner, jobs.c.created > now - 86400))
            if daily >= 6:
                raise ValueError('Beta limit: six analysis requests per day.')
            queued = db.scalar(select(func.count()).select_from(jobs).where(jobs.c.state.in_(['queued', 'running'])))
            if queued >= 20:
                raise ValueError('The beta analysis queue is full. Please try again later.')
            job_id = uuid.uuid4().hex
            db.execute(jobs.insert().values(id=job_id, owner=owner, fingerprint=fingerprint,
                payload=json.dumps(payload), state='queued', created=now, lease=0, completed=0, message='Waiting for analysis'))
            return job_id

    def recent_jobs(self, owner):
        with self.engine.connect() as db:
            rows = db.execute(select(jobs.c.id, jobs.c.state, jobs.c.completed, jobs.c.message).where(
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
                state='running', token=token, lease=now + 900, message='Analyzing games'))
            return dict(row, token=token)

    def progress(self, job, count):
        with self.engine.begin() as db:
            db.execute(update(jobs).where(jobs.c.id == job['id'], jobs.c.token == job['token'],
                jobs.c.state == 'running').values(completed=count))

    def finish(self, job, found, error=None):
        with self.engine.begin() as db:
            db.execute(select(guard).where(guard.c.id == 1).with_for_update()).first()
            row = db.execute(select(jobs).where(jobs.c.id == job['id'], jobs.c.token == job['token'],
                jobs.c.state == 'running').with_for_update()).first()
            if row is None:
                return
            added = 0
            if error is None:
                for puzzle in found:
                    old = db.execute(select(puzzles.c.data).where(puzzles.c.owner == job['owner'], puzzles.c.id == puzzle['id'])).first()
                    if old:
                        review = json.loads(old[0]).get('review')
                        if review is not None:
                            puzzle = dict(puzzle, review=review)
                        db.execute(update(puzzles).where(puzzles.c.owner == job['owner'], puzzles.c.id == puzzle['id']).values(data=json.dumps(puzzle)))
                    else:
                        db.execute(puzzles.insert().values(owner=job['owner'], id=puzzle['id'], data=json.dumps(puzzle)))
                        added += 1
            db.execute(update(jobs).where(jobs.c.id == job['id']).values(state='failed' if error else 'done',
                message=error or f'Added {added} puzzles. Refresh your library to review them.', payload='{}'))


class UserLibrary:
    def __init__(self, store, owner):
        self.store, self.owner = store, owner

    def load(self):
        return self.store.load(self.owner)

    def review(self, puzzle, correct, event):
        return self.store.review(self.owner, puzzle['id'], correct, event)

    def submit(self, username, texts, depth, threshold):
        from beta_worker import validate_payload
        payload = validate_payload(username, texts, depth, threshold)
        return self.store.submit(self.owner, payload)

    def recent_jobs(self):
        return self.store.recent_jobs(self.owner)
