"""In-app guide to generating and reviewing personal chess puzzles."""
import streamlit as st
from i18n import tr


def help_button():
    """Shared header entry point on both the sign-in and trainer screens."""
    st.html('''<style>
    .st-key-help_page{position:fixed;top:3.75rem;right:3.5rem;width:2.5rem;z-index:1000002}
    .st-key-help_page button{width:2.5rem;height:2.5rem;padding:0;border-radius:0.5rem}
    @supports(position-anchor:--chess-toolbar-actions){
      .st-key-help_page{position-anchor:--chess-toolbar-actions;top:calc(anchor(center,1.625rem) - 1.25rem);left:calc(anchor(left) + 3rem);right:auto}
    }
    </style>''')
    if st.button('', icon=':material/help_outline:', key='help_page', type='tertiary', help=tr('How it works')):
        st.query_params['page'] = 'help'
    return st.query_params.get('page') == 'help'


SECTIONS = [
    ('Browse your mistake library', [
        'Open Mistake library after Start reviewing to browse starting-board previews from your applied selection. Cards show game details, losses, attempt counts, and review status. Use the numbered page links or Previous and Next above or below the cards to browse more results. The current page is highlighted.',
        'Click Review this puzzle to open that position in Practice with a fresh board. The selected puzzle starts a new cycle, followed by the other matching puzzles. Browsing previews does not count as an attempt or change saved progress. Turn off due-only to choose puzzles scheduled for later.',
    ]),
    ('Start a review', [
        'After signing in, choose Chess.com, Lichess, or Upload PGN in the left sidebar. Enter the chess username, start and end dates, choose Low or High for Mistake size, then click Start reviewing. The optional due-only filter is under Advanced settings. The dates include both endpoints and can cover up to 366 days.',
        'Low uses a minimum loss of 150 centipawns; High uses 300. To choose another value, open Advanced settings and enable Use custom minimum loss. That value overrides Low and High for both analysis and review. Turn it off to use Low or High again. 100 centipawns equals one pawn; a custom value of 0 includes saved mate-related mistakes without a numeric loss.',
        'Start reviewing checks completed analysis for each fetched game. It reuses a game when an earlier search used the same or a lower loss threshold and the same or a higher depth. New or changed games, lower thresholds, and higher depths require analysis. Games with no mistakes are tracked too.',
    ]),
    ('Apply sidebar settings', [
        'The chess username is separate from your app login. Your review shows that player within the selected dates and game source. Uploaded PGNs may contain games from either platform. Undated puzzles stay saved but are not selected by a date range.',
        'Sidebar edits are drafts until Start reviewing is clicked. Changing a date or loss value does not interrupt the active puzzle. The main area shows your applied selection; Practice, Mistake library, and shuffled restarts all use it.',
        'If the same games were analyzed at 100, starting at 200 filters their saved mistakes without rerunning Stockfish. Starting at 50 needs analysis to find previously unsaved smaller mistakes. Older libraries may need one analysis before their coverage is known; existing puzzles and review history are kept.',
        'Only show puzzles due for review is in Advanced settings and is off by default. Enabling it hides puzzles scheduled for later. To revisit them now, turn it off and click Start reviewing. Browsing saved positions or stepping through a continuation does not add attempts.',
    ]),
    ('Answer a puzzle on the board', [
        'Drag a piece to its destination. For promotion, choose the new piece. Your piece stays on its destination while the answer is checked. The app accepts the saved best move and accepted alternatives.',
        'You do not have to find the engine\'s single top choice. During analysis, moves evaluated within 30 centipawns (0.3 pawns) of the best move are saved as acceptable alternatives. This tolerance is set by the app, with no extra setting to choose. It is separate from Minimum loss, which decides which game mistakes become puzzles.',
        'An accepted alternative counts as correct and receives the same review schedule as the best move. Feedback identifies it as a good alternative and shows the engine\'s top choice. The continuation follows your move. This is based on engine evaluation, not a judgment of how easy a move is for a human to play.',
        'Mate positions use a separate rule: an alternative must have the same engine mate score as the best move. Older puzzles may only have the best move saved; missing alternatives require a fresh analysis and are not added just by reviewing the puzzle.',
        'An incorrect move stays on the board with a red cross. Click the red retry button below the board to restore the original position and clear the feedback before trying again. Resetting does not record another attempt. After a correct answer, the piece stays where you moved it with a green check. Click Forward or Back to move through the continuation one step at a time. Back can return to the original position. Nothing plays automatically, and navigating the line does not record more attempts.',
        'Hint highlights the piece to move on the board. The highlight clears when you make a move. Reveal solution and original mistake shows your original move, the engine line, and the evaluation change. Open original game is available when a game link was saved. Click Next puzzle when ready to continue.',
    ]),
    ('Finish a cycle or take a break', [
        'Each new review starts in a shuffled order and visits each puzzle in your applied selection once. After the last puzzle, click Next puzzle to take a rest or repeat the round in shuffled order. To review other dates or settings, edit the sidebar and click Start reviewing.',
        'Starting over repeats the same round in a randomized order, including puzzles scheduled for later. Saved review progress is kept. It repeats all puzzles in that round, not only those answered incorrectly.',
    ]),
    ('Understand review scheduling', [
        'A correct answer schedules the puzzle after 1 day, then 2, 4, 8, 16, and up to 30 days as your correct streak grows. An incorrect answer resets the streak and schedules it after 10 minutes.',
        'If you answer incorrectly and then retry correctly, the correct answer replaces the 10-minute schedule with a 1-day review. A due time is not a reminder: there is no automatic pop-up, and missed puzzles are not added back into the current cycle. Start a new due-only cycle to pick up puzzles that have become due.',
    ]),
    ('Switch languages', [
        'Click the language icon in the upper-right corner to switch between English and Simplified Chinese. Your selected filters and current review cycle stay in place. Chess move notation and player usernames stay unchanged.',
    ]),
]


def show_guide(online=False, show_title=True):
    if show_title:
        st.header(tr('How it works'))
    st.write(tr('Turn mistakes from your own games into puzzles, then practice them with saved review progress.'))
    for title, paragraphs in SECTIONS:
        st.subheader(tr(title))
        for paragraph in paragraphs:
            if online and title == 'Start a review' and paragraph == paragraphs[0]:
                st.write(tr('Your saved Chess.com username is used automatically. Choose dates and mistake size, then click Start reviewing. To save a different default, open Account. For a temporary Chess.com, Lichess, or PGN player, enable Use a different player for this review in Advanced settings. The temporary choice applies to the selected round and resets after Start reviewing; your next start uses the saved default.'))
                continue
            st.write(tr(paragraph))
    if online:
        st.subheader(tr('Online beta and your saved library'))
        st.write(tr('Sign in with the username and password assigned by the app administrator. Each app account has its own saved puzzle library and review history. Entering a chess username chooses which player to analyze; it does not verify that you own that chess account.'))
        st.write(tr('The beta fetches up to 100 recent games and analyzes at most five uncovered games per start, with no daily analysis quota. Already covered games are skipped. If fetched games remain, click Start reviewing again for the next batch. A wide range does not guarantee every game has been fetched; narrow the dates to reach older games.'))
        st.write(tr('If analysis is needed, the review opens automatically after it finishes and saves successfully. Fully covered games open without a new analysis job. Failed analysis is not marked reusable, and the previous applied selection remains available. Repeated analysis updates existing puzzles without adding copies or replacing review history.'))
        st.write(tr('Refreshing the page keeps you signed in while your session is valid. Sessions expire after 12 hours. Signing out, a password reset, or account removal ends the session. Your saved puzzles and review history remain.'))
    else:
        st.subheader(tr('Local setup and storage'))
        st.write(tr('For local analysis, set Stockfish executable path under Advanced settings. Fully covered games do not need Stockfish again. Maximum games to fetch limits each web import; local analysis runs while the app is open.'))
        st.write(tr('The local app saves puzzles, completed-analysis records, and review history in puzzles.json. Older undated or unowned samples remain saved, but cannot be matched to a specific player and date range. Back up the file to keep your local progress.'))
