"""Disposable-data UI fixture: streamlit run tests/browser_preview.py."""
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chess
import streamlit as st
from visualization_all import main

if 'preview_library' not in st.session_state:
    st.session_state.preview_library = {'version': 1, 'puzzles': [{
        'id': 'browser-preview', 'fen': chess.STARTING_FEN, 'played': 'h2h3',
        'best_move': 'd2d4', 'accepted_moves': ['d2d4'],
        'solution': ['d2d4', 'd7d5', 'c2c4', 'e7e6'], 'legacy': True, 'loss': 300,
    }]}
with patch('visualization_all.load_library', return_value=st.session_state.preview_library), \
     patch('visualization_all.save_library'):
    main()
