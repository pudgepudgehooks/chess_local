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

from beta_auth import owner_for_claims

PGN = '[White "Me"]\n[Black "Other"]\n\n1. e4 e5 *'


class AuthTests(unittest.TestCase):
    def claims(self, **extra):
        return dict(is_logged_in=True, email='Friend@example.com', email_verified=True,
                    iss='https://accounts.google.com', sub='123', exp=time.time() + 3600, **extra)

    def test_invited_identity_is_stable(self):
        claims = self.claims()
        owner = owner_for_claims(claims, ['friend@example.com'])
        self.assertEqual(len(owner), 64)
        claims['email'] = 'renamed@example.com'
        self.assertEqual(owner_for_claims(claims, ['renamed@example.com']), owner)

    def test_rejects_uninvited_unverified_logged_out_expired(self):
        claims = self.claims()
        with self.assertRaises(PermissionError):
            owner_for_claims(claims, [])
        with self.assertRaises(PermissionError):
            owner_for_claims(claims, ['someoneelse@example.com'])
        for key, value in [('is_logged_in', False), ('email_verified', False), ('email_verified', 'true'),
                           ('sub', ''), ('iss', ''), ('exp', time.time() - 1)]:
            with self.subTest(key=key, value=value), self.assertRaises(PermissionError):
                owner_for_claims(dict(claims, **{key: value}), ['friend@example.com'])


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
