"""Run with: python -m streamlit run visualization_all.py"""
from datetime import date
from functools import partial
import os
import logging
import chess
import chess.engine
import chess.svg
import streamlit as st
from chess_analysis import analyze_game, engine_path, fetch_chesscom_pgn, fetch_lichess_pgn, read_games, count_player_moves
from puzzle_store import is_due, load_library, merge_puzzles, record_review, save_library
from drag_board import drag_board, consume_move, playback_frames
from i18n import tr, language, language_selector, error_text, job_message

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
    for job in recent[:1]:
        st.caption(tr('{state} · {count} games analyzed', state=tr(job['state'].capitalize()), count=job['completed']))
        fraction, label = progress_display(job)
        st.progress(fraction, text=label)
        st.write(job_message(job['message']))
    if st.button(tr('Refresh puzzle library'), key='refresh_library'):
        st.rerun()

def main(repository=None, playback_engine=None):
    if repository is None:
        st.set_page_config(page_title=tr('Chess Mistake Trainer'), page_icon='♟')
        language_selector()
    st.title(tr('Chess Mistake Trainer'))
    try:
        library = repository.load() if repository else load_library()
    except Exception as exc:
        logging.exception('Puzzle library load failed')
        st.error(tr('Your puzzle library is temporarily unavailable.') if repository else tr('Cannot load puzzle library: {error}', error=error_text(exc)))
        st.stop()
    with st.sidebar:
        st.header(tr('Generate puzzles'))
        source = st.radio(tr('Game source'), ['Chess.com month', 'Lichess month', 'Upload PGN'], format_func=partial(tr, _language=language()), key='analysis_source')
        username = st.text_input(tr('Your Lichess username' if source == 'Lichess month' else
                                   'Player username in PGN' if source == 'Upload PGN' else 'Your Chess.com username'), key='analysis_username')
        executable = ''
        if repository is None:
            executable = st.text_input(tr('Stockfish executable path'), value=os.environ.get('STOCKFISH_PATH', ''), key='analysis_engine')
        uploaded = None
        if source == 'Upload PGN':
            uploaded = st.file_uploader(tr('PGN file'), type=['pgn'], key='analysis_upload')
        else:
            year = st.number_input(tr('Year'), 1900, 2200, date.today().year, key='analysis_year')
            month = st.number_input(tr('Month'), 1, 12, date.today().month, key='analysis_month')
        lichess_limit = 5
        if source == 'Lichess month':
            st.caption(tr('Lichess imports completed standard games from the selected UTC month, newest first.'))
            if repository is None:
                lichess_limit = st.number_input(tr('Maximum games to import'), 1, 100, 20, key='lichess_limit')
        depth = st.number_input(tr('Analysis depth'), 1, 12 if repository else 30, 10 if repository else 15, key='analysis_depth')
        threshold = st.number_input(tr('Minimum loss (centipawns)'), 50, 2000, 150, 50, key='analysis_threshold')
        st.caption(tr('100 centipawns = one pawn. Beta: up to five games per request, six requests per day.') if repository else tr('100 centipawns = one pawn. Analyzing all alternatives can take several minutes per game.'))
        if st.button(tr('Generate puzzles'), key='generate_puzzles'):
            try:
                if not username.strip():
                    raise ValueError('Enter your username to select your moves.')
                path = None if repository else engine_path(executable.strip() or None)
                with st.spinner(tr('Analyzing games…')):
                    if source == 'Upload PGN':
                        if uploaded is None:
                            raise ValueError('Choose a PGN file first.')
                        raw = uploaded.getvalue()
                        if repository and len(raw) > 1024 * 1024:
                            raise ValueError('Beta uploads are limited to 1 MB.')
                        texts = [raw.decode('utf-8-sig')]
                    elif source == 'Lichess month':
                        texts = fetch_lichess_pgn(username, year, month, lichess_limit)
                    else:
                        texts = [g['pgn'] for g in fetch_chesscom_pgn(username, year, month)['games'] if g.get('rules', 'chess') == 'chess']
                        if repository:
                            texts = texts[-5:]
                    if repository:
                        repository.submit(username, texts, depth, threshold)
                    else:
                        games = [game for text in texts for game in read_games(text)]
                        found = []
                        total_positions = sum(count_player_moves(game, username) for game in games)
                        completed_positions = 0
                        progress = st.progress(0, text=tr('Preparing analysis…'))
                        with chess.engine.SimpleEngine.popen_uci(path) as engine:
                            for i, game in enumerate(games):
                                def report(done, total):
                                    completed = completed_positions + done
                                    fraction = min(0.99, completed / total_positions) if total_positions else 0.0
                                    label = analysis_progress_text(i + 1, len(games), completed, total_positions, fraction)
                                    progress.progress(fraction, text=label)
                                found.extend(analyze_game(game, username, engine, depth, threshold, on_progress=report))
                                completed_positions += count_player_moves(game, username)
                        progress.progress(0.99, text=tr('Saving puzzles…'))
                        added = merge_puzzles(library, found)
                        save_library(library)
                        progress.progress(1.0, text=tr('Analysis complete · 100%'))
                st.success(tr('Analysis queued (or already analyzed). You can leave and return later.') if repository else tr('Analyzed {games} games. Added {added} puzzles.', games=len(games), added=added))
            except Exception as exc:
                logging.exception('Puzzle generation request failed')
                st.error(error_text(exc) if isinstance(exc, ValueError) else tr('Generation failed. Please try again later.') if repository else tr('Generation failed: {error}', error=error_text(exc)))
        if repository:
            job_status(repository)
    due_only = st.checkbox(tr('Only show puzzles due for review'), value=True, key='due_only')
    names = sorted({p['username'] for p in library['puzzles'] if p.get('username')})
    player = st.selectbox(tr('Puzzle owner'), ['All players'] + names, format_func=lambda value, all_label=tr('All players'): all_label if value == 'All players' else value, key='puzzle_player')
    filter_key = (due_only, player)
    if st.session_state.get('review_filter') != filter_key:
        st.session_state.review_filter = filter_key
        st.session_state.pop('active_id', None)
    active_id = st.session_state.get('active_id')
    puzzles = [p for p in library['puzzles'] if (not due_only or is_due(p) or p['id'] == active_id) and (player == 'All players' or p.get('username') == player)]
    if not puzzles:
        st.info(tr('No puzzles are due. Generate puzzles or turn off the due-only filter.'))
        return
    index = next((i for i, p in enumerate(puzzles) if p['id'] == active_id), 0)
    puzzle = puzzles[index]
    st.session_state.active_id = puzzle['id']
    board = chess.Board(puzzle['fen'])
    st.write(tr('Puzzle {index} of {total} · {side} to move', index=index + 1, total=len(puzzles), side=tr('White' if board.turn else 'Black')))
    if puzzle.get('legacy'):
        st.warning(tr('Imported sample: player ownership and game source are unknown. Regenerate games for verified personal puzzles.'))
    else:
        st.caption(tr('{username} vs {opponent} · {date} · move {number}', username=puzzle['username'], opponent=puzzle['opponent'], date=puzzle['date'], number=puzzle['move_number']))
        if puzzle.get('platform'):
            st.caption(tr('Platform: {platform}', platform=puzzle['platform']))
    key = f"{repository.owner}-{puzzle['id']}" if repository else puzzle['id']
    st.caption(tr('Drag a piece to make your move. You can also click a piece and its destination.'))
    previous = st.session_state.get('board_feedback', {})
    response = previous.get('response') if previous.get('key') == key else None
    event = drag_board(board, key=f'board-{key}', response=response)
    seen = st.session_state.setdefault('board_events', [])
    new_event = (isinstance(event, dict) and event.get('fen') == board.fen()
                 and isinstance(event.get('event_id'), str) and bool(event['event_id'])
                 and event['event_id'] not in seen)
    dragged_move = consume_move(event, board, seen)
    if new_event:
        move = dragged_move
        result = {'event_id': event['event_id'], 'status': 'incorrect', 'frames': []}
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
                    message = 'Correct! Watch the continuation.'
                    if len(result['frames']) == 1 and not chess.Board(result['frames'][0]['fen']).is_game_over():
                        message = 'Correct! No continuation is available for this position.'
            except Exception as exc:
                logging.exception('Review save failed')
                result['status'] = 'error'
                message = 'Could not save your review. Please try again.'
        result['message'] = message
        st.session_state.board_feedback = {'key': key, 'response': result}
        st.rerun()
    if response:
        if response['status'] == 'correct':
            st.success(tr(response['message']))
        # Incorrect-answer feedback lives on the board so it can clear instantly
        # when the user picks up a piece for their next attempt.
    if st.button(tr('Hint'), key=f'hint-{key}'):
        best = chess.Move.from_uci(puzzle['best_move'])
        st.info(tr('Look at the {piece} on {square}.', piece=tr(chess.piece_name(board.piece_type_at(best.from_square))), square=chess.square_name(best.from_square)))
    with st.expander(tr('Reveal solution and original mistake')):
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
        url = puzzle.get('game_url', '')
        if url.startswith(('https://', 'http://')):
            st.link_button(tr('Open original game'), url)
    review = puzzle.get('review', {})
    st.caption(tr('Saved attempts: {attempts} · Correct: {correct}', attempts=review.get('attempts', 0), correct=review.get('correct', 0)))
    if st.button(tr('Next puzzle'), key='next_puzzle'):
        ordered = puzzles[index + 1:] + puzzles[:index + 1]
        next_puzzle = next((p for p in ordered if not due_only or is_due(p)), None)
        st.session_state.active_id = next_puzzle['id'] if next_puzzle else None
        st.rerun()
if __name__ == '__main__':
    main()
