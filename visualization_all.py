"""Run with: python -m streamlit run visualization_all.py"""
import logging
import random
import uuid
import chess
import streamlit as st
from chess_analysis import engine_path
from puzzle_store import is_due, load_library, record_review, save_library
from drag_board import drag_board, consume_move, playback_frames, prepare_board
from i18n import tr, language, language_selector, error_text, job_message
from trainer_guide import show_guide, help_button
from mistake_library import show_library
from review_setup import setup_sidebar, filter_library, reset_round

def evaluation(value):
    if not value:
        return tr('unavailable')
    return tr('mate {mate}', mate=value['mate']) if value.get('mate') is not None else tr('{cp} pawns', cp=f"{value['cp'] / 100:+.2f}")


def analysis_progress_text(game, games, done, total, fraction):
    return tr('Game {game}/{games} · Your moves analyzed: {done}/{total} · {percent}%',
              game=game, games=games, done=done, total=total, percent=int(fraction * 100))


def progress_display(job):
    """Never advertise 100% until the puzzles have committed successfully."""
    if job['state'] == 'done':
        return 1.0, tr('Analysis complete · 100%')
    total = job.get('positions_total') or 0
    done = job.get('positions_done') or 0
    fraction = min(0.99, max(0, done / total)) if total else 0.0
    if job['state'] == 'queued':
        return 0.0, tr('Queued · Waiting for the engine')
    if job['state'] == 'failed':
        return fraction, tr('Analysis stopped before completion')
    if total and done >= total:
        return fraction, tr('Saving puzzles…')
    if not job.get('game_index'):
        return fraction, tr('Preparing analysis…')
    return fraction, analysis_progress_text(job['game_index'], job['games_total'], done, total, fraction)

@st.fragment(run_every=3)
def job_status(repository):
    try:
        recent = repository.recent_jobs()
    except Exception:
        logging.exception('Job status unavailable')
        st.error(tr('Analysis status is temporarily unavailable.'))
        return
    tracked = st.session_state.get('analysis_status_job')
    selected = next((job for job in recent
                     if tracked == (repository.owner, job.get('id'))), None)
    if selected is None:
        selected = next((job for job in recent if job['state'] in ('queued', 'running')), None)
        if selected is not None:
            st.session_state.analysis_status_job = (repository.owner, selected['id'])
    if selected is not None and selected['state'] == 'done':
        completed = (repository.owner, selected['id'])
        if st.session_state.get('analysis_library_loaded_job') != completed:
            # The worker commits puzzles before marking the job done. Refresh the
            # whole app once so its library, filters, and preview grid reload too.
            st.session_state.analysis_library_loaded_job = completed
            pending = st.session_state.pop('pending_review_setup', None)
            if pending and pending['owner'] == repository.owner:
                st.session_state.review_setup = pending
                st.session_state.review_plan = st.session_state.pop('pending_review_plan', {})
                st.session_state.next_main_tab = 'Practice'
            reset_round()
            st.rerun()
    if selected is not None and selected['state'] == 'failed' and st.session_state.get('pending_review_setup'):
        st.session_state.pop('pending_review_setup', None)
        st.session_state.pop('pending_review_plan', None)
        st.session_state.review_start_error = selected['message']
        st.rerun()
    for job in [selected] if selected is not None and selected['state'] != 'done' else []:
        st.caption(tr('{state} · {count} games analyzed', state=tr(job['state'].capitalize()), count=job['completed']))
        fraction, label = progress_display(job)
        st.progress(fraction, text=label)
        st.write(job_message(job['message']))

TAB_NAMES = ['Practice', 'Mistake library']
SHOW_MISTAKE_LIBRARY = False


def remember_main_tab():
    st.session_state.main_tab_name = next(
        (name for name in TAB_NAMES if tr(name) == st.session_state.main_tab), 'Practice')


def main(repository=None, playback_engine=None):
    if repository is None:
        language_selector()
        st.set_page_config(page_title=tr('Chess Mistake Trainer'), page_icon='♟')
    guide_page = help_button()
    st.title(tr('How it works' if guide_page else 'Chess Mistake Trainer'))
    if guide_page:
        if st.button(tr('Back to puzzles'), icon=':material/arrow_back:', key='back_to_puzzles'):
            st.query_params.pop('page', None)
            st.rerun()
        trainer(repository, playback_engine, None, None, guide_page=True)
        return
    name = st.session_state.pop('next_main_tab', st.session_state.get('main_tab_name', 'Practice'))
    if not SHOW_MISTAKE_LIBRARY:
        name = 'Practice'
    st.session_state.main_tab_name = name
    st.session_state.main_tab = tr(name)
    if SHOW_MISTAKE_LIBRARY:
        review_tab, library_tab = st.tabs([tr(name) for name in TAB_NAMES],
            key='main_tab', on_change=remember_main_tab)
    else:
        review_tab, library_tab = st.container(), None
    trainer(repository, playback_engine, review_tab, library_tab)


def trainer(repository, playback_engine, review_tab, library_tab, guide_page=False):
    try:
        library = repository.load() if repository else load_library()
    except Exception as exc:
        logging.exception('Puzzle library load failed')
        st.error(tr('Your puzzle library is temporarily unavailable.') if repository else tr('Cannot load puzzle library: {error}', error=error_text(exc)))
        st.stop()
    owner = repository.owner if repository else 'local'
    for key in ('review_setup', 'pending_review_setup'):
        if st.session_state.get(key, {}).get('owner', owner) != owner:
            st.session_state.pop(key, None)
            reset_round()
    setup = setup_sidebar(library, repository, analysis_progress_text)
    if repository:
        with st.sidebar:
            job_status(repository)
    if guide_page:
        show_guide(online=repository is not None, show_title=False)
        return
    if st.session_state.get('review_start_error'):
        st.error(job_message(st.session_state.review_start_error))
    if st.session_state.get('pending_review_setup'):
        with review_tab:
            st.info(tr('Analyzing your selected games. Your review will open automatically when ready.'))
        if library_tab is not None:
            with library_tab:
                st.info(tr('Preparing your selected library. Please wait for analysis to finish.'))
        return
    if setup is None:
        if library_tab is not None:
            with library_tab:
                st.info(tr('Click Start reviewing in the sidebar to choose which saved puzzles to browse.'))
        return
    plan = st.session_state.get('review_plan', {})
    if st.session_state.get('review_cycle', {}).get('state') not in ('complete', 'rest'):
        with review_tab:
            if plan.get('remaining'):
                st.info(tr('{count} more fetched games still need analysis. Click Start reviewing again to process the next batch.', count=plan['remaining']))
            if plan and not plan.get('fetched'):
                st.info(tr('No games were returned for analysis. Showing any matching saved puzzles.'))
    available = filter_library(library, setup)
    due_only = setup['due_only']
    if library_tab is not None:
        with library_tab:
            candidates = [p for p in available.values() if not due_only or is_due(p)]
            selected = show_library(candidates)
            if selected is not None:
                ids = [p['id'] for p in candidates]
                index = ids.index(selected)
                st.session_state.review_cycle = {'ids': ids[index:] + ids[:index], 'index': 0,
                                                 'state': 'active', 'token': uuid.uuid4().hex}
                st.session_state.active_id = selected
                st.session_state.pop('board_feedback', None)
                st.session_state.next_main_tab = 'Practice'
                st.rerun()
    with review_tab:
        practice_puzzles(library, repository, playback_engine, list(library['puzzles']), available, due_only)


def practice_puzzles(library, repository, playback_engine, owned, available, due_only):
    cycle = st.session_state.get('review_cycle')
    if cycle is None:
        ids = [pid for pid, p in available.items() if not due_only or is_due(p)]
        random.shuffle(ids)
        cycle = {'ids': ids,
                 'index': 0, 'state': 'active', 'token': uuid.uuid4().hex}
        st.session_state.review_cycle = cycle
    puzzles = [available[pid] for pid in cycle['ids'] if pid in available]
    if not puzzles:
        if not available:
            st.info(tr('No puzzles match your applied settings. Adjust the sidebar and click Start reviewing again.'))
        else:
            st.info(tr('No puzzles are due. Turn off due-only in the sidebar and click Start reviewing to revisit saved puzzles.'))
        # An initially empty library may receive new puzzles on a later rerun.
        st.session_state.pop('review_cycle', None)
        return
    if cycle['state'] in ('complete', 'rest'):
        st.session_state.active_id = None
        st.success(tr('Cycle complete! Take a rest or practice your mistakes again.'))
        st.caption(tr('Or choose another date range in the sidebar and click Start reviewing.'))
        if st.button(tr('Previous'), key='previous_puzzle'):
            cycle['state'] = 'active'
            cycle['index'] = len(puzzles) - 1
            st.session_state.pop('board_feedback', None)
            st.rerun()
        if cycle['state'] == 'rest':
            st.info(tr('Enjoy your break. Your progress is saved. Start over whenever you are ready.'))
        elif st.button(tr('Take a rest'), key='rest_cycle'):
            cycle['state'] = 'rest'
            st.rerun()
        if st.button(tr('Start over with shuffled puzzles'), key='restart_cycle'):
            previous_order = [p['id'] for p in puzzles]
            order = previous_order.copy()
            random.shuffle(order)
            if len(order) > 1 and order == previous_order:
                order = order[1:] + order[:1]
            st.session_state.review_cycle = {'ids': order, 'index': 0, 'state': 'active',
                                             'token': uuid.uuid4().hex}
            st.session_state.pop('board_feedback', None)
            st.rerun()
        return
    index = min(cycle['index'], len(puzzles) - 1)
    puzzle = puzzles[index]
    # Prepare a bounded look-ahead without running Stockfish or saving reviews.
    # These cached legal positions are reused when Next puzzle is clicked.
    for upcoming in puzzles[index:index + 4]:
        prepare_board(upcoming['fen'])
    st.session_state.active_id = puzzle['id']
    board = chess.Board(puzzle['fen'])
    st.write(tr('Puzzle {index} of {total} · {side} to move', index=index + 1, total=len(puzzles), side=tr('White' if board.turn else 'Black')))
    if puzzle.get('legacy'):
        st.warning(tr('Imported sample: player ownership and game source are unknown. Regenerate games for verified personal puzzles.'))
    key = f"{repository.owner}-{puzzle['id']}" if repository else puzzle['id']
    previous = st.session_state.get('board_feedback', {})
    response = previous.get('response') if previous.get('key') == key else None
    st.html('''<style>
    .st-key-practice_board,.st-key-practice_solution{width:100%;max-width:460px}
    .st-key-practice_board iframe{display:block}
    [data-testid="stVerticalBlock"]:has(> [data-testid="stLayoutWrapper"] > .st-key-practice_board){gap:0.35rem}
    </style>''')
    with st.container(key='practice_board'):
        event = drag_board(board, key=f"board-{cycle['token']}", response=response,
                           context_id=key, hint_square=puzzle['best_move'][:2], game_url=puzzle.get('game_url', ''),
                           opponent_move=puzzle.get('opponent_move'))
    seen = st.session_state.setdefault('board_events', [])
    new_event = (isinstance(event, dict) and event.get('fen') == board.fen()
                 and event.get('context_id', key) == key
                 and isinstance(event.get('event_id'), str) and bool(event['event_id'])
                 and event['event_id'] not in seen)
    dragged_move = consume_move(event, board, seen) if new_event else None
    if new_event:
        move = dragged_move
        result = {'event_id': event['event_id'], 'status': 'incorrect', 'frames': [],
                  'uci': move.uci() if move is not None else None}
        if move is not None:
            attempted_board = board.copy()
            attempted_board.push(move)
            result['attempt_fen'] = attempted_board.fen()
        message = 'The answer is incorrect, please try again'
        if move is None:
            result['status'] = 'incorrect'
        else:
            correct = move.uci() in puzzle.get('accepted_moves', [puzzle['best_move']])
            try:
                if repository:
                    puzzle.update(repository.review(puzzle, correct, event['event_id']))
                else:
                    record_review(puzzle, correct)
                    save_library(library)
                if correct:
                    result['status'] = 'correct'
                    try:
                        executable = playback_engine
                        if not executable:
                            try:
                                executable = engine_path(st.session_state.get('analysis_engine') or None)
                            except ValueError:
                                executable = None
                        result['frames'] = playback_frames(board, move, puzzle, executable)
                    except Exception:
                        logging.exception('Solution continuation unavailable')
                        result['frames'] = playback_frames(board, move, puzzle)
                    message = 'Correct! Use Forward and Back to review the continuation.'
                    if len(result['frames']) == 1 and not chess.Board(result['frames'][0]['fen']).is_game_over():
                        message = 'Correct! No continuation is available for this position.'
                    if move.uci() != puzzle['best_move']:
                        result['message_values'] = {'move': board.san(chess.Move.from_uci(puzzle['best_move']))}
                        message = ('Good move! This is an acceptable alternative. The engine\'s top choice is {move}. '
                                   'Use Forward and Back to review the continuation.')
                        if len(result['frames']) == 1 and not chess.Board(result['frames'][0]['fen']).is_game_over():
                            message = ('Good move! This is an acceptable alternative. The engine\'s top choice is {move}. '
                                       'No continuation is available for this position.')
            except Exception as exc:
                logging.exception('Review save failed')
                result['status'] = 'error'
                message = 'Could not save your review. Please try again.'
        result['message'] = message
        result['repeat_game_mistake'] = result['status'] == 'incorrect' and move is not None and move.uci() == puzzle['played']
        st.session_state.board_feedback = {'key': key, 'response': result}
        st.rerun()
    if response:
        if response['status'] == 'correct' and response['message'] != 'Correct! Use Forward and Back to review the continuation.':
            st.success(tr(response['message'], **response.get('message_values', {})))
        # Incorrect-answer feedback clears locally when Retry resets the board.
    with st.container(key='practice_solution'), st.expander(tr('Reveal solution and original mistake')):
        st.write(tr('Your game move: **{move}**', move=board.san(chess.Move.from_uci(puzzle['played']))))
        line_board = board.copy()
        line = []
        for uci in puzzle.get('solution', [puzzle['best_move']]):
            move = chess.Move.from_uci(uci)
            line.append(line_board.san(move))
            line_board.push(move)
        st.write(tr('Engine continuation: ') + ' → '.join(line))
        st.caption(tr('Your evaluation: {before} → {after}.', before=evaluation(puzzle.get('before')), after=evaluation(puzzle.get('after'))))
        if puzzle.get('loss') is not None:
            st.write(tr('Evaluation lost: {loss} pawns', loss=f"{puzzle['loss'] / 100:.2f}"))
        else:
            kind = puzzle.get('kind', '')
            st.write(tr(kind) if kind else tr(''))
    def next_puzzle():
        cycle['index'] = index + 1
        if cycle['index'] >= len(puzzles):
            cycle['state'] = 'complete'
        st.session_state.pop('board_feedback', None)
    def previous_puzzle():
        cycle['index'] = max(0, index - 1)
        st.session_state.pop('board_feedback', None)
    with st.container(horizontal=True, gap='small', width=460):
        st.button(tr('Previous'), key='previous_puzzle', disabled=index == 0, on_click=previous_puzzle)
        st.button(tr('Next'), key='next_puzzle', on_click=next_puzzle)
if __name__ == '__main__':
    main()
