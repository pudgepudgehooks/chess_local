"""Run with: python -m streamlit run visualization_all.py"""
from datetime import date
import os
import uuid
import logging

import chess
import chess.engine
import chess.svg
import streamlit as st

from chess_analysis import analyze_game, engine_path, fetch_chesscom_pgn, read_games
from puzzle_store import is_due, load_library, merge_puzzles, record_review, save_library
from drag_board import drag_board, consume_move


def evaluation(value):
    if not value:
        return 'unavailable'
    return f"mate {value['mate']}" if value.get('mate') is not None else f"{value['cp'] / 100:+.2f} pawns"


@st.fragment(run_every=3)
def job_status(repository):
    try:
        recent = repository.recent_jobs()
    except Exception:
        logging.exception('Job status unavailable')
        st.error('Analysis status is temporarily unavailable.')
        return
    for job in recent:
        st.caption(f"{job['state'].capitalize()} · {job['completed']} games analyzed")
        st.write(job['message'])
    if st.button('Refresh puzzle library'):
        st.rerun()


def main(repository=None):
    if repository is None:
        st.set_page_config(page_title='Chess Mistake Trainer', page_icon='♟')
    st.title('Chess Mistake Trainer')
    try:
        library = repository.load() if repository else load_library()
    except Exception as exc:
        logging.exception('Puzzle library load failed')
        st.error('Your puzzle library is temporarily unavailable.' if repository else f'Cannot load puzzle library: {exc}')
        st.stop()
    with st.sidebar:
        st.header('Generate puzzles')
        username = st.text_input('Your Chess.com username')
        executable = ''
        if repository is None:
            executable = st.text_input('Stockfish executable path', value=os.environ.get('STOCKFISH_PATH', ''))
        source = st.radio('Game source', ['Chess.com month', 'Upload PGN'])
        uploaded = None
        if source == 'Upload PGN':
            uploaded = st.file_uploader('PGN file', type=['pgn'])
        else:
            year = st.number_input('Year', 1900, 2200, date.today().year)
            month = st.number_input('Month', 1, 12, date.today().month)
        depth = st.number_input('Analysis depth', 1, 12 if repository else 30, 10 if repository else 15)
        threshold = st.number_input('Minimum loss (centipawns)', 50, 2000, 150, 50)
        st.caption('100 centipawns = one pawn. Beta: up to five games per request, six requests per day.' if repository else
                   '100 centipawns = one pawn. Analyzing all alternatives can take several minutes per game.')
        if st.button('Generate puzzles'):
            try:
                if not username.strip():
                    raise ValueError('Enter your username to select your moves.')
                path = None if repository else engine_path(executable.strip() or None)
                with st.spinner('Analyzing games…'):
                    if source == 'Upload PGN':
                        if uploaded is None:
                            raise ValueError('Choose a PGN file first.')
                        raw = uploaded.getvalue()
                        if repository and len(raw) > 1024 * 1024:
                            raise ValueError('Beta uploads are limited to 1 MB.')
                        texts = [raw.decode('utf-8-sig')]
                    else:
                        texts = [g['pgn'] for g in fetch_chesscom_pgn(username, year, month)['games']
                                 if g.get('rules', 'chess') == 'chess']
                        if repository:
                            texts = texts[-5:]
                    if repository:
                        repository.submit(username, texts, depth, threshold)
                    else:
                        games = [game for text in texts for game in read_games(text)]
                        found = []
                        progress = st.progress(0)
                        with chess.engine.SimpleEngine.popen_uci(path) as engine:
                            for i, game in enumerate(games):
                                found.extend(analyze_game(game, username, engine, depth, threshold))
                                progress.progress((i + 1) / len(games))
                        added = merge_puzzles(library, found)
                        save_library(library)
                st.success('Analysis queued (or already analyzed). You can leave and return later.' if repository else
                           f'Analyzed {len(games)} games. Added {added} puzzles.')
            except Exception as exc:
                logging.exception('Puzzle generation request failed')
                st.error(str(exc) if isinstance(exc, ValueError) else
                         'Generation failed. Please try again later.' if repository else f'Generation failed: {exc}')
        if repository:
            job_status(repository)
    due_only = st.checkbox('Only show puzzles due for review', value=True)
    names = sorted({p['username'] for p in library['puzzles'] if p.get('username')})
    player = st.selectbox('Puzzle owner', ['All players'] + names)
    filter_key = (due_only, player)
    if st.session_state.get('review_filter') != filter_key:
        st.session_state.review_filter = filter_key
        st.session_state.pop('active_id', None)
    active_id = st.session_state.get('active_id')
    puzzles = [p for p in library['puzzles'] if (not due_only or is_due(p) or p['id'] == active_id)
               and (player == 'All players' or p.get('username') == player)]
    if not puzzles:
        st.info('No puzzles are due. Generate puzzles or turn off the due-only filter.')
        return
    index = next((i for i, p in enumerate(puzzles) if p['id'] == active_id), 0)
    puzzle = puzzles[index]
    st.session_state.active_id = puzzle['id']
    board = chess.Board(puzzle['fen'])
    st.write(f"Puzzle {index + 1} of {len(puzzles)} · {'White' if board.turn else 'Black'} to move")
    if puzzle.get('legacy'):
        st.warning('Imported sample: player ownership and game source are unknown. Regenerate games for verified personal puzzles.')
    else:
        st.caption(f"{puzzle['username']} vs {puzzle['opponent']} · {puzzle['date']} · move {puzzle['move_number']}")
    key = f'{repository.owner}-{puzzle["id"]}' if repository else puzzle['id']
    st.caption('Drag a piece to make your move. You can also click a piece and its destination.')
    event = drag_board(board, key=f'board-{key}')
    seen = st.session_state.setdefault('board_events', [])
    dragged_move = consume_move(event, board, seen)
    with st.form(f'answer-{key}'):
        guess = st.text_input('Your move (SAN or UCI, e.g. Nf3, e2e4, or e7e8q)')
        submitted = st.form_submit_button('Check move')
    if submitted or dragged_move is not None:
        move = dragged_move
    if submitted:
        try:
            move = board.parse_san(guess.strip())
        except ValueError:
            try:
                move = board.parse_uci(guess.strip().lower())
            except ValueError:
                move = None
    if submitted or dragged_move is not None:
        if move is None:
            st.error('Enter a legal move. Include the promotion piece when promoting.')
        else:
            correct = move.uci() in puzzle.get('accepted_moves', [puzzle['best_move']])
            try:
                if repository:
                    event_id = event['event_id'] if dragged_move is not None and not submitted else uuid.uuid4().hex
                    puzzle.update(repository.review(puzzle, correct, event_id))
                else:
                    record_review(puzzle, correct)
                    save_library(library)
                if correct:
                    st.success('Correct! Review saved. Choose Next puzzle when ready.')
                else:
                    st.error('That move loses more than the accepted alternatives. Try again.')
            except Exception as exc:
                logging.exception('Review save failed')
                st.error('Could not save your review. Please try again.' if repository else f'Could not save review: {exc}')
    if st.button('Hint', key=f'hint-{key}'):
        best = chess.Move.from_uci(puzzle['best_move'])
        st.info(f'Look at the {chess.piece_name(board.piece_type_at(best.from_square))} on {chess.square_name(best.from_square)}.')
    with st.expander('Reveal solution and original mistake'):
        st.write(f"Your game move: **{board.san(chess.Move.from_uci(puzzle['played']))}**")
        line_board = board.copy()
        line = []
        for uci in puzzle.get('solution', [puzzle['best_move']]):
            move = chess.Move.from_uci(uci)
            line.append(line_board.san(move))
            line_board.push(move)
        st.write('Engine continuation: ' + ' → '.join(line))
        st.caption(f"Your evaluation: {evaluation(puzzle.get('before'))} → {evaluation(puzzle.get('after'))}.")
        if puzzle.get('loss') is not None:
            st.write(f"Evaluation lost: {puzzle['loss'] / 100:.2f} pawns")
        else:
            st.write(puzzle.get('kind', '').replace('_', ' ').capitalize())
        url = puzzle.get('game_url', '')
        if url.startswith(('https://', 'http://')):
            st.link_button('Open original game', url)
    review = puzzle.get('review', {})
    st.caption(f"Saved attempts: {review.get('attempts', 0)} · Correct: {review.get('correct', 0)}")
    if st.button('Next puzzle'):
        ordered = puzzles[index + 1:] + puzzles[:index + 1]
        next_puzzle = next((p for p in ordered if not due_only or is_due(p)), None)
        st.session_state.active_id = next_puzzle['id'] if next_puzzle else None
        st.rerun()


if __name__ == '__main__':
    main()
