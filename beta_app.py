"""Private beta with administrator-assigned username/password accounts."""
import logging
from pathlib import Path
import shutil
import streamlit as st
from i18n import tr, language_selector, error_text


@st.cache_resource
def database(url):
    from beta_store import BetaStore
    return BetaStore(url)


@st.cache_resource
def account_service(url, configured):
    from beta_auth import Accounts
    return Accounts(database(url).engine, dict(configured))


@st.cache_resource
def services(url, stockfish_path):
    from beta_worker import Worker
    store = database(url)
    return store, Worker(store, stockfish_path)


def clear_private_state():
    for key in list(st.session_state):
        if key != 'ui_language':
            del st.session_state[key]


def account_screen(accounts):
    st.title(tr('Chess Trainer · Private Beta'))
    st.write(tr('Sign in with the username and password assigned by your group owner.'))
    with st.form('account_login', clear_on_submit=True):
        username = st.text_input(tr('Username'), max_chars=32, key='account_username')
        password = st.text_input(tr('Password'), type='password', max_chars=128, key='account_password')
        submitted = st.form_submit_button(tr('Sign in'))
    st.caption(tr('Need an account or forgot your password? Contact your group owner.'))
    if submitted:
        try:
            token = accounts.login(username, password, st.context.ip_address or 'unknown')
            clear_private_state()
            st.session_state.account_token = token
            st.rerun()
        except ValueError as exc:
            st.error(error_text(exc))
        except Exception:
            logging.error('Account login unavailable', exc_info=False)
            st.error(tr('Account service is temporarily unavailable. Please try again later.'))


def main():
    st.set_page_config(page_title=tr('Chess Trainer · Private Beta'), page_icon='♟')
    language_selector()
    try:
        settings = st.secrets['beta']
        url = str(settings['database_url'])
        configured = {name: entry['password_hash'] for name, entry in settings['accounts'].items()}
        from beta_auth import validate_accounts
        configured = validate_accounts(configured)
        if not url.startswith(('postgres://', 'postgresql://', 'postgresql+psycopg://')):
            raise ValueError('Invalid production database URL')
    except (KeyError, ValueError, TypeError, AttributeError, FileNotFoundError):
        st.error(tr('The private beta is not configured yet. Please contact the beta owner.'))
        st.stop()
    try:
        accounts = account_service(url, tuple(sorted(configured.items())))
        accounts.sync()
        identity = accounts.identity(st.session_state.get('account_token'))
    except Exception:
        logging.error('Account database unavailable', exc_info=False)
        st.error(tr('Account service is temporarily unavailable. Please try again later.'))
        st.stop()
    if identity is None:
        if st.session_state.get('account_token'):
            clear_private_state()
            st.info(tr('Your session expired. Please sign in again.'))
        account_screen(accounts)
        st.stop()
    owner = identity['id']
    if st.session_state.get('beta_owner') != owner:
        token = st.session_state.account_token
        clear_private_state()
        st.session_state.account_token = token
        st.session_state.beta_owner = owner
    with st.sidebar:
        st.caption(tr('Signed in as {username}', username=identity['username']))
        st.caption(tr('Signed in for up to 12 hours. A full page refresh requires signing in again.'))
        if st.button(tr('Sign out'), key='beta_logout'):
            accounts.logout(st.session_state.account_token)
            clear_private_state()
            st.rerun()
    try:
        from chess_analysis import engine_path
        from beta_store import UserLibrary
        path = engine_path(settings.get('stockfish_path', '/usr/games/stockfish'))
        if not Path(path).is_file() and not shutil.which(path):
            raise ValueError('Server engine is not installed')
        store, worker = services(url, path)
    except Exception:
        logging.exception('Beta startup failed')
        st.error(tr('The beta service is temporarily unavailable. Please contact the beta owner.'))
        st.stop()
    from visualization_all import main as trainer
    token = st.session_state.account_token
    def authorized():
        current = accounts.identity(token)
        return current is not None and current['id'] == owner
    trainer(UserLibrary(store, owner, authorize=authorized), playback_engine=path)


if __name__ == '__main__':
    main()
