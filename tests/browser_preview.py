"""Disposable-data UI fixture: streamlit run tests/browser_preview.py."""
from pathlib import Path
import sys
from unittest.mock import patch
from datetime import date
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chess
import chess.pgn
import streamlit as st
from visualization_all import main
from chess_analysis import filter_games_by_date
from analysis_cache import coverage_records, LOCAL_POLICY

if 'preview_library' not in st.session_state:
    examples = [
        ([], ['d2d4', 'd7d5', 'c2c4', 'e7e6']),
        (['e2e4', 'e7e5'], ['g1f3', 'b8c6', 'f1c4', 'g8f6']),
        (['d2d4', 'd7d5', 'c2c4'], ['e7e6', 'b1c3', 'g8f6', 'c1g5']),
        (['e2e4', 'c7c5', 'g1f3', 'd7d6'], ['d2d4', 'c5d4', 'f3d4']),
        (['g1f3', 'd7d5'], ['d2d4', 'g8f6', 'c2c4']),
        (['e2e4', 'e7e6', 'd2d4', 'd7d5'], ['b1c3', 'g8f6', 'c1g5']),
    ]
    puzzles, texts = [], []
    for i, (opening, solution) in enumerate(examples):
        board = chess.Board()
        for uci in opening:
            board.push_uci(uci)
        played = next(m.uci() for m in board.legal_moves if m.uci() != solution[0])
        game = chess.pgn.Game()
        game.headers.update(White='PreviewPlayer' if board.turn else f'ExampleOpponent{i + 1}',
                            Black=f'ExampleOpponent{i + 1}' if board.turn else 'PreviewPlayer',
                            Date=f'2026.{8 if i < 3 else 9:02d}.{i + 1:02d}',
                            Site=f'https://example.com/game/{i}')
        node = game
        for uci in opening + [played]:
            node = node.add_variation(chess.Move.from_uci(uci))
        texts.append(game.accept(chess.pgn.StringExporter(headers=True, variations=False, comments=False)))
        puzzles.append(dict(
            id=f'browser-preview-{i}', fen=board.fen(),
            played=played,
            best_move=solution[0], accepted_moves=[solution[0]], solution=solution,
            loss=300 + i * 50, username='PreviewPlayer', opponent=f'Example opponent {i + 1}',
            game_url=f'https://example.com/game/{i}',
            date=f'2026.{8 if i < 3 else 9:02d}.{i + 1:02d}', move_number=board.fullmove_number))
    st.session_state.preview_texts = texts
    st.session_state.preview_library = {'version': 1, 'puzzles': puzzles,
        'analyses': coverage_records('PreviewPlayer', texts, 30, 100, LOCAL_POLICY)}
    st.session_state.analysis_username = 'PreviewPlayer'
    st.session_state.analysis_start_date = date(2026, 8, 1)
    st.session_state.analysis_end_date = date(2026, 9, 30)
    st.session_state.due_only = False


def fetch_preview(username, start, end, *args, **kwargs):
    return filter_games_by_date(st.session_state.preview_texts, start, end)


with patch('visualization_all.load_library', return_value=st.session_state.preview_library), \
     patch('visualization_all.save_library'), patch('puzzle_store.save_library'), \
     patch('chess_analysis.fetch_chesscom_range', side_effect=fetch_preview), \
     patch('chess_analysis.fetch_lichess_range', side_effect=fetch_preview):
    main()
