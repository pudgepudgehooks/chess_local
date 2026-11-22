"""Set up existing saved-puzzle rounds without invoking external game services."""
from datetime import date
from game_dates import game_date


def prepare_library(library):
    for puzzle in library['puzzles']:
        if not puzzle.get('username'):
            puzzle['username'] = 'Me'
        if game_date(puzzle.get('date')) is None:
            puzzle['date'] = '2026.08.01'
    return library


def seed_review(app, library, username=None, start=None, end=None, threshold=0, due_only=True, owner='local'):
    app.default_timeout = 30
    prepare_library(library)
    username = username or library['puzzles'][0]['username']
    dates = [game_date(p['date']) for p in library['puzzles'] if p['username'] == username]
    app.session_state.review_setup = dict(owner=owner, source='Upload PGN', username=username,
        start=start or min(dates), end=end or max(dates), threshold=threshold, due_only=due_only,
        depth=15 if owner == 'local' else 10, import_limit=100)
    return app


def choose_review(app, username, start, end, threshold=0, due_only=False, source='Upload PGN'):
    app.radio(key='analysis_source').set_value(source).run()
    app.text_input(key='analysis_username').set_value(username)
    app.date_input(key='analysis_start_date').set_value(start)
    app.date_input(key='analysis_end_date').set_value(end)
    app.number_input(key='analysis_threshold').set_value(threshold)
    app.checkbox(key='due_only').set_value(due_only)
    app.run()
    app.button(key='start_review').click().run()
    return app
