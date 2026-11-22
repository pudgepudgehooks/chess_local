from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid


PGN = '[White "Me"]\n[Black "Other"]\n\n1. e4 e5 *'


@unittest.skipUnless(importlib.util.find_spec('sqlalchemy'), 'SQLAlchemy is not installed')
class StoreTests(unittest.TestCase):
    def setUp(self):
        from beta_store import BetaStore
        self.temp = tempfile.TemporaryDirectory()
        self.store = BetaStore('sqlite:///' + str(Path(self.temp.name) / 'beta.db'))
        self.payload = {'username': 'Me', 'texts': [PGN], 'depth': 5, 'threshold': 150}
        self.puzzle = {'id': 'p1', 'fen': 'test', 'best_move': 'e2e4'}

    def tearDown(self):
        self.store.engine.dispose()
        self.temp.cleanup()

    def test_owner_isolation_reviews_and_cached_generation(self):
        jid = self.store.submit('alice', self.payload)
        job = self.store.claim()
        self.store.finish(job, [dict(self.puzzle)])
        self.assertEqual(self.store.load('bob')['puzzles'], [])
        self.assertEqual(self.store.recent_jobs('bob'), [])
        with self.assertRaises(ValueError):
            self.store.review('bob', 'p1', True, 'x')
        first = self.store.review('alice', 'p1', True, 'same-event')
        second = self.store.review('alice', 'p1', True, 'same-event')
        self.assertEqual(first['review'], second['review'])
        self.assertEqual(second['review']['attempts'], 1)
        self.assertEqual(self.store.submit('alice', self.payload), jid)
        # New analysis settings update positions without replacing review history.
        self.store.submit('alice', dict(self.payload, depth=6))
        self.store.finish(self.store.claim(), [dict(self.puzzle)])
        self.assertEqual(self.store.load('alice')['puzzles'][0]['review']['attempts'], 1)

    def test_limits_single_global_worker_and_recovery(self):
        from beta_store import jobs
        from sqlalchemy import update
        self.store.submit('alice', self.payload)
        with self.assertRaises(ValueError):
            self.store.submit('alice', dict(self.payload, depth=6))
        self.store.submit('bob', self.payload)
        original = self.store.claim()
        self.assertIsNone(self.store.claim())
        with self.store.engine.begin() as db:
            db.execute(update(jobs).where(jobs.c.id == original['id']).values(lease=0))
        recovered = self.store.claim()
        self.assertEqual(original['id'], recovered['id'])
        self.assertNotEqual(original['token'], recovered['token'])
        self.store.finish(original, [self.puzzle])
        self.assertEqual(self.store.load('alice')['puzzles'], [])
        self.store.finish(recovered, [self.puzzle])
        self.assertEqual(len(self.store.load('alice')['puzzles']), 1)
        self.assertEqual(self.store.claim()['owner'], 'bob')

    def test_daily_quota_and_failure_retry(self):
        for i in range(6):
            self.store.submit('alice', dict(self.payload, depth=i + 1))
            self.store.finish(self.store.claim(), [], error='Test failure')
        with self.assertRaises(ValueError):
            self.store.submit('alice', dict(self.payload, depth=12))

    def test_restart_retains_queued_job(self):
        from beta_store import BetaStore
        self.store.submit('alice', self.payload)
        other = BetaStore(str(self.store.engine.url))
        try:
            self.assertEqual(other.claim()['owner'], 'alice')
        finally:
            other.engine.dispose()

    def test_payload_limits_and_worker(self):
        from beta_worker import validate_payload, run_job
        payload = validate_payload('Me', [PGN], 5, 150)
        for username, texts, depth in [('Me', [PGN] * 6, 5), ('NoOne', [PGN], 5),
                                       ('Me', ['x' * (1024 * 1024 + 1)], 5), ('Me', [PGN], 30)]:
            with self.assertRaises(ValueError):
                validate_payload(username, texts, depth, 150)
        self.store.submit('alice', payload)
        with patch('beta_worker.chess.engine.SimpleEngine.popen_uci') as start, \
             patch('beta_worker.analyze_game', return_value=[self.puzzle]) as analyze:
            run_job(self.store, self.store.claim(), 'test-engine')
            self.assertEqual(analyze.call_args.kwargs['position_time'], 0.15)
        self.assertEqual(self.store.recent_jobs('alice')[0]['state'], 'done')


@unittest.skipUnless(os.environ.get('BETA_TEST_DATABASE_URL'), 'Dedicated PostgreSQL test URL not configured')
class PostgresConcurrencyTests(unittest.TestCase):
    def test_concurrent_analysis_commits_do_not_duplicate_positions(self):
        import chess
        from beta_store import BetaStore, jobs
        store = BetaStore(os.environ['BETA_TEST_DATABASE_URL'])
        owner = uuid.uuid4().hex
        pending = [dict(id=uuid.uuid4().hex, owner=owner, token=uuid.uuid4().hex) for _ in range(2)]
        try:
            with store.engine.begin() as db:
                for job in pending:
                    db.execute(jobs.insert().values(**job, state='running', fingerprint=job['id'],
                                                   payload='{}', created=time.time()))
            def finish(job):
                store.finish(job, [dict(id=job['id'], username='Me',
                    game_url='https://lichess.org/abcd1234/white', fen=chess.STARTING_FEN,
                    played='e2e4', best_move='d2d4')])
            with ThreadPoolExecutor(max_workers=2) as executor:
                list(executor.map(finish, pending))
            self.assertEqual(len(store.load(owner)['puzzles']), 1)
        finally:
            store.engine.dispose()

    def test_concurrent_reviews_are_not_lost(self):
        from beta_store import BetaStore
        store = BetaStore(os.environ['BETA_TEST_DATABASE_URL'])
        owner = uuid.uuid4().hex
        try:
            store.submit(owner, {'test': owner})
            store.finish(store.claim(), [{'id': owner}])
            with ThreadPoolExecutor(max_workers=4) as executor:
                list(executor.map(lambda i: store.review(owner, owner, True, f'review-{i}'), range(8)))
            self.assertEqual(store.load(owner)['puzzles'][0]['review']['attempts'], 8)
        finally:
            store.engine.dispose()
