"""Private online entry point. Does not load local files or expose engine paths."""
import logging
from pathlib import Path
import shutil
import streamlit as st

from beta_auth import owner_for_claims


@st.cache_resource
def services(database_url, stockfish_path):
    from beta_store import BetaStore
    from beta_worker import Worker
    store = BetaStore(database_url)
    return store, Worker(store, stockfish_path)


def main():
    st.set_page_config(page_title='Chess Trainer · Private Beta', page_icon='♟')
    try:
        settings = st.secrets['beta']
        allowed = list(settings['allowed_emails'])
        url = str(settings['database_url'])
        if not url.startswith(('postgres://', 'postgresql://', 'postgresql+psycopg://')) or not allowed:
            raise ValueError('Missing production configuration')
        if not st.secrets.get('auth'):
            raise ValueError('Missing authentication configuration')
    except (KeyError, ValueError, FileNotFoundError):
        st.error('The private beta is not configured yet. Please contact the beta owner.')
        st.stop()
    if not st.user.is_logged_in:
        st.title('Chess Trainer · Private Beta')
        st.write('Sign in with your invited Google account to generate and review your own chess puzzles.')
        if st.button('Sign in with Google'):
            st.login()
        st.stop()
    try:
        owner = owner_for_claims(dict(st.user), allowed)
    except PermissionError as exc:
        st.error(str(exc))
        if st.button('Sign out'):
            st.logout()
        st.stop()
    # Widgets from another login must not survive an identity change in the session.
    if st.session_state.get('beta_owner') != owner:
        st.session_state.clear()
        st.session_state.beta_owner = owner
    with st.sidebar:
        st.caption(f"Private beta · {st.user.email}")
        if st.button('Sign out'):
            st.logout()
    try:
        from chess_analysis import engine_path
        from beta_store import UserLibrary
        path = engine_path(settings.get('stockfish_path', '/usr/games/stockfish'))
        if not Path(path).is_file() and not shutil.which(path):
            raise ValueError('Server engine is not installed')
        store, worker = services(url, path)
    except Exception:
        logging.exception('Beta startup failed')
        st.error('The beta service is temporarily unavailable. Please contact the beta owner.')
        st.stop()
    from visualization_all import main as trainer
    trainer(UserLibrary(store, owner))


if __name__ == '__main__':
    main()
