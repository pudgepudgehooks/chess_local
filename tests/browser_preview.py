"""Disposable-data UI fixture: streamlit run tests/browser_preview.py."""
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chess
import streamlit as st
from visualization_all import main

if 'preview_library' not in st.session_state:
    examples = [
        ([], ['d2d4', 'd7d5', 'c2c4', 'e7e6']),
        (['e2e4', 'e7e5'], ['g1f3', 'b8c6', 'f1c4', 'g8f6']),
        (['d2d4', 'd7d5', 'c2c4'], ['e7e6', 'b1c3', 'g8f6', 'c1g5']),
        (['e2e4', 'c7c5', 'g1f3', 'd7d6'], ['d2d4', 'c5d4', 'f3d4']),
        (['g1f3', 'd7d5'], ['d2d4', 'g8f6', 'c2c4']),
        (['e2e4', 'e7e6', 'd2d4', 'd7d5'], ['b1c3', 'g8f6', 'c1g5']),
    ]
    puzzles = []
    for i, (opening, solution) in enumerate(examples):
        board = chess.Board()
        for uci in opening:
            board.push_uci(uci)
        puzzles.append(dict(
            id=f'browser-preview-{i}', fen=board.fen(),
            played=next(m.uci() for m in board.legal_moves if m.uci() != solution[0]),
            best_move=solution[0], accepted_moves=[solution[0]], solution=solution,
            loss=300 + i * 50, username='Preview player', opponent=f'Example opponent {i + 1}',
            date=f'2026.{8 if i < 3 else 9:02d}.{i + 1:02d}', move_number=board.fullmove_number))
    st.session_state.preview_library = {'version': 1, 'puzzles': puzzles}
with patch('visualization_all.load_library', return_value=st.session_state.preview_library), \
     patch('visualization_all.save_library'):
    main()
