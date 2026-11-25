"""Normalize clipboard formatting without changing visible username separators."""
import re
import unicodedata


def normalize_player_username(value):
    if not isinstance(value, str):
        raise ValueError('Enter a valid player username (letters, numbers, underscores or hyphens).')
    value = unicodedata.normalize('NFKC', value)
    value = ''.join(char for char in value if unicodedata.category(char) != 'Cf').strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,50}', value):
        raise ValueError('Enter a valid player username (letters, numbers, underscores or hyphens).')
    return value
