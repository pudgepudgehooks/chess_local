from pathlib import Path
import tempfile
import time
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
import unittest

from sqlalchemy import select, update
from beta_auth import Accounts, PASSWORDS, users, sessions, attempts, validate_accounts
from beta_store import BetaStore

PASSWORD = 'a long assigned password'


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = BetaStore('sqlite:///' + str(Path(self.temp.name) / 'accounts.db'))
        self.config = {'alice': PASSWORDS.hash(PASSWORD), 'bob': PASSWORDS.hash(PASSWORD)}
        self.accounts = Accounts(self.store.engine, self.config)

    def tearDown(self):
        self.store.engine.dispose()
        self.temp.cleanup()

    def test_hashes_sessions_and_private_libraries(self):
        alice_token = self.accounts.login(' ALICE ', PASSWORD)
        bob_token = self.accounts.login('bob', PASSWORD)
        alice = self.accounts.identity(alice_token)
        bob = self.accounts.identity(bob_token)
        self.assertNotEqual(alice['id'], bob['id'])
        with self.store.engine.connect() as db:
            rows = db.execute(select(users)).mappings().all()
            self.assertTrue(all(r['password_hash'].startswith('$argon2id$') for r in rows))
            self.assertNotEqual(rows[0]['password_hash'], rows[1]['password_hash'])
            self.assertNotIn(alice_token, [r[0] for r in db.execute(select(sessions.c.token_hash))])
        self.store.submit(alice['id'], {'test': True})
        self.store.finish(self.store.claim(), [{'id': 'one'}])
        self.assertEqual(self.store.load(bob['id'])['puzzles'], [])
        with self.assertRaises(ValueError):
            self.store.review(bob['id'], 'one', True, 'guess')

    def test_unknown_user_wrong_password_and_logout(self):
        for name, password in [('alice', 'wrong'), ('unknown', PASSWORD), ('alice', 'x' * 129)]:
            with self.assertRaisesRegex(ValueError, 'Invalid username or password'):
                self.accounts.login(name, password)
        token = self.accounts.login('alice', PASSWORD)
        self.accounts.logout(token)
        self.assertIsNone(self.accounts.identity(token))
        self.assertIsNone(self.accounts.identity(None))

    def test_expiry(self):
        from beta_store import UserLibrary
        token = self.accounts.login('alice', PASSWORD)
        identity = self.accounts.identity(token)
        library = UserLibrary(self.store, identity['id'], authorize=lambda: self.accounts.identity(token) is not None)
        self.assertEqual(library.load()['puzzles'], [])
        with self.store.engine.begin() as db:
            db.execute(update(sessions).values(expires=time.time() - 1))
        self.assertIsNone(self.accounts.identity(token))
        with self.assertRaises(PermissionError):
            library.recent_jobs()
        with self.assertRaises(PermissionError):
            library.submit('Me', [], 5, 150)

    def test_admin_password_reset_revokes_sessions_and_keeps_owner(self):
        token = self.accounts.login('alice', PASSWORD)
        owner = self.accounts.identity(token)['id']
        replacement = 'another assigned password'
        updated = Accounts(self.store.engine, dict(self.config, alice=PASSWORDS.hash(replacement)))
        self.assertIsNone(updated.identity(token))
        with self.assertRaises(ValueError):
            updated.login('alice', PASSWORD)
        self.assertEqual(updated.identity(updated.login('alice', replacement))['id'], owner)
        # Reapplying a previously cached configuration must also synchronize it.
        self.accounts.sync()
        self.assertEqual(self.accounts.identity(self.accounts.login('alice', PASSWORD))['id'], owner)

    def test_removed_account_is_revoked_and_can_be_restored(self):
        token = self.accounts.login('alice', PASSWORD)
        owner = self.accounts.identity(token)['id']
        removed = Accounts(self.store.engine, {'bob': self.config['bob']})
        self.assertIsNone(removed.identity(token))
        with self.assertRaises(ValueError):
            removed.login('alice', PASSWORD)
        self.accounts.sync()
        self.assertIsNone(self.accounts.identity(token))
        self.assertEqual(self.accounts.identity(self.accounts.login('alice', PASSWORD))['id'], owner)

    def test_rate_limit_survives_new_auth_instance(self):
        for _ in range(10):
            with self.assertRaises(ValueError):
                self.accounts.login('alice', 'wrong')
        other = Accounts(self.store.engine, self.config)
        with self.assertRaisesRegex(ValueError, 'Too many attempts'):
            other.login('alice', PASSWORD)

    def test_invalid_configuration_and_plaintext_are_rejected(self):
        for config in [{}, {'alice': PASSWORD}, {'alice': 'REPLACE-ME'},
                       {'a': self.config['alice']}, {str(i) * 3: self.config['alice'] for i in range(5)}]:
            with self.subTest(config=list(config)), self.assertRaises(ValueError):
                validate_accounts(config)


@unittest.skipUnless(os.environ.get('BETA_TEST_DATABASE_URL'), 'Dedicated PostgreSQL test URL not configured')
class PostgresAccountTests(unittest.TestCase):
    def test_concurrent_login_limit_and_configuration_sync(self):
        store = BetaStore(os.environ['BETA_TEST_DATABASE_URL'])
        username = uuid.uuid4().hex
        try:
            accounts = Accounts(store.engine, {username: PASSWORDS.hash(PASSWORD)})
            def login(index):
                try:
                    return accounts.login(username, PASSWORD, f'client-{index}')
                except ValueError:
                    return None
            with ThreadPoolExecutor(max_workers=4) as executor:
                results = list(executor.map(login, range(12)))
            self.assertEqual(sum(token is not None for token in results), 10)
            token = next(token for token in results if token)
            owner = accounts.identity(token)['id']
            changed = Accounts(store.engine, {username: PASSWORDS.hash('new assigned password')})
            self.assertIsNone(changed.identity(token))
            with store.engine.connect() as db:
                self.assertEqual(db.execute(select(users.c.id).where(users.c.username == username)).scalar_one(), owner)
        finally:
            store.engine.dispose()
