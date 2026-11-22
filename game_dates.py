"""Calendar-date handling shared by imports and saved-puzzle filters."""
from datetime import date


def game_date(value):
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip().replace('.', '-'))
    except ValueError:
        return None


def validate_date_range(start, end, max_days=None):
    if not isinstance(start, date) or not isinstance(end, date):
        raise ValueError('Choose both a start date and an end date.')
    if start > end:
        raise ValueError('Start date must be on or before end date.')
    if max_days is not None and (end - start).days + 1 > max_days:
        raise ValueError('Choose an analysis date range of at most 366 days.')


def within_dates(value, start, end):
    played = game_date(value)
    return played is not None and start <= played <= end
