"""Private beta with administrator-assigned username/password accounts."""
import logging
from pathlib import Path
import shutil
import streamlit as st
from i18n import tr, language_selector, error_text
import browser_session


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
        if key not in ('ui_language', 'sound_enabled', '_session_cookie_command', '_session_cookie_token_hash', '_ignore_browser_session'):
            del st.session_state[key]


def account_screen(accounts):
    from trainer_guide import help_button, show_guide
    if help_button():
        st.title(tr('How it works'))
        if st.button(tr('Back to sign in'), icon=':material/arrow_back:', key='back_to_signin'):
            st.query_params.pop('page', None)
            st.rerun()
        show_guide(online=True, show_title=False)
        return
    st.title(tr('Chess Trainer · Private Beta'))
    st.write(tr('Sign in with the username and password assigned by your group owner.'))
    st.html('''<style>
    :is(.st-key-account_username,.st-key-account_password) [data-testid="InputInstructions"] > span:first-child{display:none}
    :is(.st-key-account_username,.st-key-account_password) [data-testid="InputInstructions"] > span:nth-child(2)::before{display:none}
    </style>''')
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
            browser_session.remember(token)
            st.rerun()
        except ValueError as exc:
            st.error(error_text(exc))
        except Exception:
            logging.error('Account login unavailable', exc_info=False)
            st.error(tr('Account service is temporarily unavailable. Please try again later.'))


def account_menu(username, sign_out, default_player=None, save_player=None, palette='Brown', save_palette=None):
    st.html('''<style>
    [data-testid="stToolbarActions"]{padding-inline-start:16rem}
    .st-key-account_menu{position:fixed;top:3.75rem;right:9rem;width:7rem;z-index:1000002}
    .st-key-account_menu [data-testid="stPopoverButton"]{height:2.5rem;padding:0.25rem 0.5rem;border:0;background:transparent}
    @supports(position-anchor:--chess-toolbar-actions){
      .st-key-account_menu{position-anchor:--chess-toolbar-actions;top:calc(anchor(center,1.625rem) - 1.25rem);left:calc(anchor(left) + 9rem);right:auto}
    }
    </style>''')
    with st.popover(tr('Account'), key='account_menu'):
        st.write(tr('Signed in as {username}', username=username))
        if default_player is not None:
            st.caption(tr('Default Chess.com username: {username}', username=default_player or tr('Not set')))
            with st.form('save_player_default'):
                player = st.text_input(tr('Default Chess.com username'), value=default_player,
                    key='account_player_username', help=tr('Saving changes the default for future reviews.'))
                submitted = st.form_submit_button(tr('Save default username'))
            if submitted and save_player is not None:
                try:
                    save_player(player)
                    st.session_state.player_default_saved = True
                    st.rerun()
                except ValueError as exc:
                    st.error(error_text(exc))
                except Exception:
                    logging.error('Player preference save failed', exc_info=False)
                    st.error(tr('Could not save your default username. Please try again.'))
            if st.session_state.pop('player_default_saved', False):
                st.success(tr('Default username saved. Your current review is unchanged.'))
        if save_palette is not None:
            from board_theme import PALETTES
            with st.form('save_board_color'):
                selected_palette = st.selectbox(tr('Board color'), list(PALETTES),
                    index=list(PALETTES).index(palette), format_func=tr, key='account_board_palette')
                save_color = st.form_submit_button(tr('Save board color'))
            if save_color:
                try:
                    save_palette(selected_palette)
                    st.rerun()
                except ValueError as exc:
                    st.error(error_text(exc))
                except Exception:
                    logging.error('Board preference save failed', exc_info=False)
                    st.error(tr('Could not save your board color. Please try again.'))
        if st.button(tr('Sign out'), key='beta_logout'):
            sign_out()


def main():
    language_selector()
    st.set_page_config(page_title=tr('Chess Trainer · Private Beta'), page_icon='♟')
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
        token = st.session_state.get('account_token') or browser_session.request_token()
        identity = accounts.identity(token)
        default_player = accounts.player_username(token) if identity is not None else None
        palette = accounts.board_palette(token) if identity is not None else 'Brown'
    except Exception:
        logging.error('Account database unavailable', exc_info=False)
        st.error(tr('Account service is temporarily unavailable. Please try again later.'))
        st.stop()
    if identity is None:
        if token:
            clear_private_state()
            browser_session.forget()
            st.info(tr('Your session expired. Please sign in again.'))
        browser_session.sync()
        account_screen(accounts)
        st.stop()
    owner = identity['id']
    st.session_state.account_token = token
    if st.session_state.get('beta_owner') != owner:
        token = st.session_state.account_token
        clear_private_state()
        st.session_state.account_token = token
        st.session_state.beta_owner = owner
    browser_session.ensure(token)
    browser_session.sync()
    st.session_state.board_palette = palette
    def sign_out():
        accounts.logout(st.session_state.account_token)
        clear_private_state()
        browser_session.forget()
        st.rerun()
    account_menu(identity['username'], sign_out, default_player,
                 lambda player: accounts.save_player_username(token, player), palette,
                 lambda color: accounts.save_board_palette(token, color))
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
    trainer(UserLibrary(store, owner, authorize=authorized, default_username=default_player), playback_engine=path)


if __name__ == '__main__':
    main()
