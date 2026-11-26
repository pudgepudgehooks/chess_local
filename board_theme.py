"""Board palettes shared by practice and saved-position previews."""

BOARD_COLORS = {
    'square light': '#ffce9e',
    'square dark': '#d18b47',
    'square light lastmove': '#cdd16a',
    'square dark lastmove': '#aaa23b',
    'margin': '#212121',
    'coord': '#e5e5e5',
}

PALETTES = {
    'Brown': ('#ffce9e', '#d18b47'),
    'Green': ('#eeeed2', '#769656'),
    'Blue': ('#dee3e6', '#8ca2ad'),
    'Purple': ('#efedf6', '#9a8eb8'),
}


def board_colors(palette='Brown'):
    light, dark = PALETTES.get(palette, PALETTES['Brown'])
    return dict(BOARD_COLORS, **{'square light': light, 'square dark': dark})


def current_board_colors():
    import streamlit as st
    return board_colors(st.session_state.get('board_palette', 'Brown'))
