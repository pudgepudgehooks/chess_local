"""Persist revocable login tokens across refreshes in a host-only HTTPS cookie."""
from pathlib import Path
import secrets

import streamlit as st
from streamlit.components.v1 import declare_component
from beta_auth import SESSION_SECONDS, digest

COOKIE_NAME = '__Host-chess_beta_session'
_cookie = declare_component('beta_session_cookie', path=str(Path(__file__).parent / 'session_component'))


def request_token():
    if st.session_state.get('_ignore_browser_session'):
        return None
    return st.context.cookies.get(COOKIE_NAME)


def remember(token):
    st.session_state._ignore_browser_session = False
    st.session_state._session_cookie_token_hash = digest(token)
    st.session_state._session_cookie_command = dict(id=secrets.token_hex(16), token=token, max_age=SESSION_SECONDS)


def ensure(token):
    """Backfill cookies for valid logins that predate this feature, once per token."""
    if st.session_state.get('_session_cookie_token_hash') == digest(token):
        return
    if request_token() == token:
        st.session_state._session_cookie_token_hash = digest(token)
    else:
        remember(token)


def forget():
    # The current WebSocket still has the cookie from its initial request.
    st.session_state._ignore_browser_session = True
    st.session_state.pop('_session_cookie_token_hash', None)
    st.session_state._session_cookie_command = dict(id=secrets.token_hex(16), token='', max_age=0)


def sync():
    command = st.session_state.get('_session_cookie_command')
    if not command:
        return
    result = _cookie(command=command, key='session-cookie', default=None)
    if isinstance(result, dict) and result.get('id') == command['id']:
        st.session_state.pop('_session_cookie_command', None)
        if not result.get('stored') and command['token']:
            from i18n import tr
            st.warning(tr('Your browser blocked the sign-in cookie. Allow cookies for this app to stay signed in after refreshing.'))
