"""Sidebar draft settings and the single, explicit Start reviewing action."""
from copy import deepcopy
from datetime import date
import os
import re

import chess.engine
import streamlit as st

import chess_analysis
import puzzle_store
from analysis_cache import LOCAL_POLICY, plan_analysis, coverage_records, merge_coverage
from game_dates import validate_date_range, within_dates
from i18n import tr, language, error_text


def reset_round():
    for key in ('review_cycle', 'active_id', 'board_feedback', 'library_page'):
        st.session_state.pop(key, None)


def filter_library(library, setup):
    if not setup:
        return {}
    platform = {'Chess.com month': 'Chess.com', 'Lichess month': 'Lichess'}.get(setup['source'])
    return {p['id']: p for p in library['puzzles']
            if (p.get('username') or '').strip().casefold() == setup['username'].strip().casefold()
            and (not platform or not p.get('platform') or p['platform'] == platform)
            and within_dates(p.get('date'), setup['start'], setup['end'])
            and puzzle_store.meets_review_loss(p, setup['threshold'])}


def prepare_start(library, setup, repository=None, uploaded=None, executable=None, progress_label=None):
    username, start, end = setup['username'], setup['start'], setup['end']
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,50}', username):
        raise ValueError('Enter a valid player username (letters, numbers, underscores or hyphens).')
    validate_date_range(start, end, max_days=366)
    maximum = 100 if repository else setup['import_limit']
    if setup['source'] == 'Upload PGN':
        if uploaded is None:
            if not any((p.get('username') or '').strip().casefold() == username.casefold() for p in library['puzzles']):
                raise ValueError('Choose a PGN file first.')
            texts = []
        else:
            raw = uploaded.getvalue()
            if repository and len(raw) > 1024 * 1024:
                raise ValueError('Beta uploads are limited to 1 MB.')
            texts = chess_analysis.filter_games_by_date([raw.decode('utf-8-sig')], start, end)
    elif setup['source'] == 'Lichess month':
        texts = chess_analysis.fetch_lichess_range(username, start, end, maximum)
    else:
        texts = chess_analysis.fetch_chesscom_range(username, start, end, max_games=maximum)
    if not texts:
        return dict(job_id=None, fetched=0, reused=0, selected=0, remaining=0)
    if repository:
        return repository.prepare_analysis(username, texts, setup['depth'], setup['threshold'])
    plan = plan_analysis(username, texts, library.get('analyses', []), setup['depth'],
                         setup['threshold'], LOCAL_POLICY)
    items = plan.pop('items')
    plan['job_id'] = None
    if not items:
        return plan
    path = chess_analysis.engine_path((executable or '').strip() or None)
    found, completed = [], 0
    total = sum(chess_analysis.count_player_moves(item['game'], username) for item in items)
    progress = st.progress(0, text=tr('Preparing analysis…'))
    with chess.engine.SimpleEngine.popen_uci(path) as engine:
        for index, item in enumerate(items, 1):
            def report(done, count):
                fraction = min(0.99, (completed + done) / total) if total else 0.0
                label = progress_label(index, len(items), completed + done, total, fraction) if progress_label else tr('Analyzing games…')
                progress.progress(fraction, text=label)
            found.extend(chess_analysis.analyze_game(item['game'], username, engine,
                setup['depth'], setup['threshold'], on_progress=report))
            completed += chess_analysis.count_player_moves(item['game'], username)
    working = deepcopy(library)
    puzzle_store.merge_puzzles(working, found)
    merge_coverage(working, coverage_records(username, [item['text'] for item in items],
                                            setup['depth'], setup['threshold'], LOCAL_POLICY))
    puzzle_store.save_library(working)
    library.clear()
    library.update(working)
    progress.progress(1.0, text=tr('Analysis complete · 100%'))
    return plan


def setup_sidebar(library, repository=None, progress_label=None):
    owner = repository.owner if repository else 'local'
    with st.sidebar:
        st.header(tr('Review setup'))
        source = st.radio(tr('Game source'), ['Chess.com month', 'Lichess month', 'Upload PGN'],
            format_func=lambda value, lang=language(): tr({'Chess.com month': 'Chess.com', 'Lichess month': 'Lichess'}.get(value, value), _language=lang), key='analysis_source')
        username = st.text_input(tr('Your Lichess username' if source == 'Lichess month' else
            'Player username in PGN' if source == 'Upload PGN' else 'Your Chess.com username'), key='analysis_username',
            help=tr('This is the chess username whose mistakes you want to review, not your app login.'))
        start = st.date_input(tr('Start date'), value=date.today().replace(day=1), min_value=date(1900, 1, 1),
                             max_value=date(2200, 12, 31), format='YYYY-MM-DD', key='analysis_start_date')
        end = st.date_input(tr('End date'), value=date.today(), min_value=date(1900, 1, 1),
                           max_value=date(2200, 12, 31), format='YYYY-MM-DD', key='analysis_end_date',
                           help=tr('Both dates are included. Sidebar edits apply only when you click Start reviewing.'))
        valid = True
        try:
            validate_date_range(start, end, max_days=366)
        except ValueError as exc:
            valid = False
            st.error(error_text(exc))
        threshold = st.number_input(tr('Minimum loss (centipawns)'), 0, 2000, 150, 50, key='analysis_threshold',
            help=tr('Used for both analysis and this review. 100 centipawns is one pawn; 0 includes saved mate-related mistakes without a numeric loss.'))
        due_only = st.checkbox(tr('Only show puzzles due for review'), value=True, key='due_only')
        uploaded = st.file_uploader(tr('PGN file'), type=['pgn'], key='analysis_upload') if source == 'Upload PGN' else None
        if source == 'Upload PGN' and uploaded is None:
            st.caption(tr('Upload the PGN to find new mistakes. Without a file, only matching saved puzzles can be reviewed.'))
        executable = ''
        with st.expander(tr('Advanced settings')):
            depth = st.number_input(tr('Analysis depth'), 1, 12 if repository else 30, 10 if repository else 15, key='analysis_depth')
            if repository:
                import_limit = 100
            else:
                executable = st.text_input(tr('Stockfish executable path'), value=os.environ.get('STOCKFISH_PATH', ''), key='analysis_engine')
                import_limit = st.number_input(tr('Maximum games to fetch'), 1, 100, 100, key='analysis_import_limit')
        if repository:
            st.caption(tr('Fetches up to 100 recent games. Each start analyzes at most five uncovered games; no daily analysis quota. Cached games do not need Stockfish again.'))
        pending = st.session_state.get('pending_review_setup')
        if st.button(tr('Start reviewing'), key='start_review', disabled=not valid or bool(pending), width='stretch'):
            st.session_state.pop('review_start_error', None)
            snapshot = dict(owner=owner, source=source, username=username.strip(), start=start, end=end,
                            threshold=int(threshold), depth=int(depth), due_only=due_only, import_limit=import_limit)
            try:
                with st.spinner(tr('Preparing your review…')):
                    plan = prepare_start(library, snapshot, repository, uploaded, executable, progress_label)
                if plan['job_id']:
                    st.session_state.pending_review_setup = snapshot
                    st.session_state.pending_review_plan = plan
                    st.session_state.analysis_status_job = (owner, plan['job_id'])
                    st.session_state.pop('analysis_library_loaded_job', None)
                else:
                    st.session_state.review_setup = snapshot
                    st.session_state.review_plan = plan
                    st.session_state.pop('analysis_status_job', None)
                    reset_round()
                    st.session_state.next_main_tab = 'Practice'
                st.rerun()
            except Exception as exc:
                import logging
                logging.exception('Start review failed')
                st.error(error_text(exc) if isinstance(exc, ValueError) else tr('Could not prepare your review. Please try again.'))
    return st.session_state.get('review_setup')
