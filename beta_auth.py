"""Administrator-assigned accounts with Argon2id hashes and revocable sessions."""
import hashlib
import re
import secrets
import time
import uuid

from argon2 import PasswordHasher, extract_parameters
from argon2.low_level import Type
from argon2.exceptions import VerificationError, InvalidHashError
from sqlalchemy import Column, Float, Integer, MetaData, String, Table, Text, select, update, delete
from beta_store import guard

metadata = MetaData()
users = Table('beta_users', metadata,
    Column('id', String(64), primary_key=True),
    Column('username', String(32), nullable=False, unique=True),
    Column('password_hash', Text, nullable=False),
    Column('created', Float, nullable=False))
sessions = Table('beta_sessions', metadata,
    Column('token_hash', String(64), primary_key=True), Column('owner', String(64), nullable=False),
    Column('expires', Float, nullable=False))
attempts = Table('beta_auth_attempts', metadata,
    Column('key', String(64), primary_key=True), Column('started', Float, nullable=False),
    Column('count', Integer, nullable=False))
player_preferences = Table('beta_player_preferences', metadata,
    Column('owner', String(64), primary_key=True),
    Column('chesscom_username', String(50), nullable=False))
INITIAL_PLAYERS = {'deer': 'timberrrrrrrr', 'bear': 'ursabearattack', 'coco': 'mimiyamg'}
board_preferences = Table('beta_board_preferences', metadata,
    Column('owner', String(64), primary_key=True), Column('palette', String(20), nullable=False))
PASSWORDS = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(32))
SESSION_SECONDS = 12 * 3600


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def normalized_username(value):
    value = value.strip().lower()
    if not re.fullmatch(r'[a-z0-9_-]{3,32}', value):
        raise ValueError('Use 3–32 letters, numbers, underscores or hyphens for your username.')
    return value


def validate_password(password):
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise ValueError('Use a password with 12–128 characters.')


def validate_accounts(configured):
    if not isinstance(configured, dict) or not 1 <= len(configured) <= 4:
        raise ValueError('Configure between one and four accounts.')
    result = {}
    for username, hashed in configured.items():
        username = normalized_username(username)
        if username in result or not isinstance(hashed, str):
            raise ValueError('Duplicate account or invalid password hash.')
        try:
            params = extract_parameters(hashed)
        except (InvalidHashError, ValueError):
            raise ValueError('Generate password hashes with account_admin.py.') from None
        if params.type != Type.ID or not 19456 <= params.memory_cost <= 65536 or not 2 <= params.time_cost <= 4 or not 1 <= params.parallelism <= 4 or params.salt_len < 16 or params.hash_len < 16:
            raise ValueError('Generate password hashes with account_admin.py.')
        result[username] = hashed
    return result


class Accounts:
    def __init__(self, engine, configured_accounts):
        self.engine = engine
        self.configured = validate_accounts(configured_accounts)
        metadata.create_all(engine)
        self.sync()

    def sync(self):
        """Apply administrator edits without changing stable account/puzzle IDs."""
        with self.engine.begin() as db:
            self._lock(db)
            disabled = select(users.c.id).where(users.c.username.not_in(list(self.configured)))
            db.execute(delete(sessions).where(sessions.c.owner.in_(disabled)))
            for username, password_hash in self.configured.items():
                row = db.execute(select(users).where(users.c.username == username)).mappings().first()
                owner = row['id'] if row else uuid.uuid4().hex
                if row is None:
                    db.execute(users.insert().values(id=owner, username=username,
                        password_hash=password_hash, created=time.time()))
                elif row['password_hash'] != password_hash:
                    db.execute(update(users).where(users.c.id == row['id']).values(password_hash=password_hash))
                    db.execute(delete(sessions).where(sessions.c.owner == row['id']))
                if username in INITIAL_PLAYERS and not db.execute(select(player_preferences.c.owner).where(player_preferences.c.owner == owner)).first():
                    db.execute(player_preferences.insert().values(owner=owner, chesscom_username=INITIAL_PLAYERS[username]))

    def _lock(self, db):
        db.execute(select(guard).where(guard.c.id == 1).with_for_update()).first()

    def _attempt(self, username, client):
        """Durable limits across browser sessions and process restarts."""
        now = time.time()
        window = 900
        limits = [('login:global', 100), (f'login:client:{client}', 30), (f'login:user:{username}', 10)]
        with self.engine.begin() as db:
            self._lock(db)
            db.execute(delete(attempts).where(attempts.c.started < now - 3600))
            for key, limit in limits:
                key = digest(key)
                row = db.execute(select(attempts).where(attempts.c.key == key)).mappings().first()
                if row and row['started'] > now - window:
                    if row['count'] >= limit:
                        raise ValueError('Too many attempts. Please try again later.')
                    db.execute(update(attempts).where(attempts.c.key == key).values(count=row['count'] + 1))
                elif row:
                    db.execute(update(attempts).where(attempts.c.key == key).values(started=now, count=1))
                else:
                    db.execute(attempts.insert().values(key=key, started=now, count=1))

    def login(self, username, password, client='unknown'):
        username = username.strip().lower()[:128]
        self._attempt(username, client)
        with self.engine.connect() as db:
            row = db.execute(select(users).where(users.c.username == username)).mappings().first()
        if username not in self.configured or (row and row['password_hash'] != self.configured[username]):
            row = None
        try:
            if not isinstance(password, str) or len(password) > 128:
                raise ValueError()
            PASSWORDS.verify(row['password_hash'] if row else DUMMY_HASH, password)
            if row is None:
                raise ValueError()
        except (VerificationError, InvalidHashError, ValueError):
            raise ValueError('Invalid username or password.') from None
        token = secrets.token_urlsafe(32)
        with self.engine.begin() as db:
            self._lock(db)
            current = db.execute(select(users.c.password_hash).where(users.c.id == row['id'])).first()
            if not current or current[0] != row['password_hash']:
                raise ValueError('Invalid username or password.')
            db.execute(delete(sessions).where(sessions.c.expires <= time.time()))
            db.execute(sessions.insert().values(token_hash=digest(token), owner=row['id'], expires=time.time() + SESSION_SECONDS))
        return token

    def identity(self, token):
        if not isinstance(token, str) or not 20 <= len(token) <= 128:
            return None
        with self.engine.connect() as db:
            row = db.execute(select(users.c.id, users.c.username).join(sessions, users.c.id == sessions.c.owner).where(
                sessions.c.token_hash == digest(token), sessions.c.expires > time.time())).mappings().first()
            return dict(row) if row and row['username'] in self.configured else None

    def logout(self, token):
        with self.engine.begin() as db:
            db.execute(delete(sessions).where(sessions.c.token_hash == digest(token)))

    def player_username(self, token):
        identity = self.identity(token)
        if identity is None:
            raise ValueError('Your session expired. Please sign in again.')
        with self.engine.connect() as db:
            return db.execute(select(player_preferences.c.chesscom_username).where(
                player_preferences.c.owner == identity['id'])).scalar_one_or_none() or ''

    def save_player_username(self, token, username):
        from player_names import normalize_player_username
        if not isinstance(token, str) or not 20 <= len(token) <= 128:
            raise ValueError('Your session expired. Please sign in again.')
        username = normalize_player_username(username)
        with self.engine.begin() as db:
            self._lock(db)
            row = db.execute(select(users.c.id, users.c.username).join(sessions, users.c.id == sessions.c.owner).where(
                sessions.c.token_hash == digest(token), sessions.c.expires > time.time())).mappings().first()
            if row is None or row['username'] not in self.configured:
                raise ValueError('Your session expired. Please sign in again.')
            owner = row['id']
            if db.execute(select(player_preferences.c.owner).where(player_preferences.c.owner == owner)).first():
                db.execute(update(player_preferences).where(player_preferences.c.owner == owner).values(chesscom_username=username))
            else:
                db.execute(player_preferences.insert().values(owner=owner, chesscom_username=username))
        return username

    def board_palette(self, token):
        identity = self.identity(token)
        if identity is None:
            raise ValueError('Your session expired. Please sign in again.')
        with self.engine.connect() as db:
            return db.execute(select(board_preferences.c.palette).where(
                board_preferences.c.owner == identity['id'])).scalar_one_or_none() or 'Brown'

    def save_board_palette(self, token, palette):
        from board_theme import PALETTES
        if palette not in PALETTES:
            raise ValueError('Choose a valid board color.')
        if not isinstance(token, str) or not 20 <= len(token) <= 128:
            raise ValueError('Your session expired. Please sign in again.')
        with self.engine.begin() as db:
            self._lock(db)
            row = db.execute(select(users.c.id, users.c.username).join(sessions, users.c.id == sessions.c.owner).where(
                sessions.c.token_hash == digest(token), sessions.c.expires > time.time())).mappings().first()
            if row is None or row['username'] not in self.configured:
                raise ValueError('Your session expired. Please sign in again.')
            if db.execute(select(board_preferences.c.owner).where(board_preferences.c.owner == row['id'])).first():
                db.execute(update(board_preferences).where(board_preferences.c.owner == row['id']).values(palette=palette))
            else:
                db.execute(board_preferences.insert().values(owner=row['id'], palette=palette))
        return palette
