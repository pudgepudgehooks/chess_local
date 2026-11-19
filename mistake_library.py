"""Paginated previews of the authenticated user's filtered puzzle library."""
from datetime import datetime, timezone
import math

import chess
import chess.svg
import streamlit as st

from i18n import tr
from puzzle_store import is_due
from board_theme import BOARD_COLORS

PAGE_SIZE = 12


def show_library(puzzles):
    """Return the selected puzzle ID; browsing never records a review."""
    st.header(tr('Mistake library'))
    st.caption(tr('Browse starting positions and choose a puzzle to practice. The filters above apply here too; turn off due-only to see puzzles scheduled for later.'))
    if not puzzles:
        st.info(tr('No saved puzzles match the current filters. Try another month, lower the review loss, or turn off due-only.'))
        return None
    counts = st.columns(3)
    counts[0].metric(tr('Matching puzzles'), len(puzzles))
    counts[1].metric(tr('Due now'), sum(is_due(p) for p in puzzles))
    counts[2].metric(tr('Previously attempted'), sum(bool(p.get('review', {}).get('attempts')) for p in puzzles))
    pages = math.ceil(len(puzzles) / PAGE_SIZE)
    if st.session_state.get('library_page', 1) > pages:
        st.session_state.library_page = pages
    page = st.number_input(tr('Library page'), min_value=1, max_value=pages,
                           value=1, step=1, key='library_page')
    start = (page - 1) * PAGE_SIZE
    st.caption(tr('Showing {first}–{last} of {total} puzzles', first=start + 1,
                  last=min(start + PAGE_SIZE, len(puzzles)), total=len(puzzles)))
    for row in range(start, min(start + PAGE_SIZE, len(puzzles)), 3):
        for column, puzzle in zip(st.columns(3), puzzles[row:row + 3]):
            with column, st.container(border=True):
                valid = True
                try:
                    board = chess.Board(puzzle['fen'])
                    st.image(chess.svg.board(board, orientation=board.turn, size=240, colors=BOARD_COLORS),
                             width='stretch')
                    st.caption(tr('{side} to move', side=tr('White' if board.turn else 'Black')))
                except (ValueError, KeyError):
                    valid = False
                    st.warning(tr('Board preview unavailable.'))
                st.caption(tr('{player} vs {opponent}', player=puzzle.get('username') or tr('Unknown player'),
                              opponent=puzzle.get('opponent') or tr('Unknown opponent')))
                st.caption(tr('Game date: {date}', date=puzzle.get('date') or tr('Unknown date')))
                loss = puzzle.get('loss')
                st.caption(tr('Loss: {loss} centipawns', loss=loss) if loss is not None
                           else tr(puzzle['kind']) if puzzle.get('kind') else tr('Loss unavailable'))
                review = puzzle.get('review', {})
                status = 'Not attempted' if not review.get('attempts') else 'Due now' if is_due(puzzle) else 'Scheduled for later'
                st.write(tr(status))
                st.caption(tr('Saved attempts: {attempts} · Correct: {correct}',
                              attempts=review.get('attempts', 0), correct=review.get('correct', 0)))
                if review.get('next_review'):
                    when = datetime.fromisoformat(review['next_review']).astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
                    st.caption(tr('Next review: {when}', when=when))
                if st.button(tr('Review this puzzle'), key=f"open-puzzle-{puzzle['id']}",
                             disabled=not valid, width='stretch'):
                    return puzzle['id']
    return None
