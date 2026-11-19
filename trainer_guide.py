"""In-app guide to generating and reviewing personal chess puzzles."""
import streamlit as st
from i18n import tr


SECTIONS = [
    ('Browse your mistake library', [
        'Open Mistake library to browse small boards showing each puzzle before your answer. Cards show the game date, opponent, loss, attempts, and review status. Use Library page to browse more results; the player, month, review loss, and due-only filters above apply to both tabs.',
        'Click Review this puzzle to open that position in Practice with a fresh board. The selected puzzle starts a new cycle, followed by the other matching puzzles. Browsing previews does not count as an attempt or change saved progress. Turn off due-only to choose puzzles scheduled for later.',
    ]),
    ('Generate puzzles from your games', [
        'In the sidebar, choose Chess.com month, Lichess month, or Upload PGN. Enter the chess username whose moves you want analyzed, then select a year and month or upload a PGN file. The engine looks for mistakes made by that player.',
        'Minimum loss (centipawns) controls which evaluation drops are saved during analysis. 100 centipawns equals one pawn; 150 means 1.5 pawns and 300 means 3 pawns. Mate-related mistakes are tracked separately. Analysis depth controls how deeply the engine searches; higher settings take longer.',
        'Click Generate puzzles and watch the progress bar. It reaches 100% after puzzles are saved. Generating another month adds puzzles to your library and keeps existing review history.',
    ]),
    ('Choose which saved mistakes to review', [
        'Puzzle owner means the Chess.com or Lichess username whose mistakes generated the puzzles. It is separate from your app login. All players includes every chess username in your saved library.',
        'Saved game month filters by when a game was played. Choose a year-month such as 2026-08, All months, or Unknown date for undated puzzles. Switching months keeps your saved puzzles and review history.',
        'Minimum review loss (centipawns) filters puzzles already saved. Set 300 to show recorded losses of at least 300, or 0 to show all losses, including mate-related puzzles without a numeric loss. Lowering this filter restores hidden puzzles; it does not change the analysis setting or delete anything.',
        'Only show puzzles due for review hides puzzles scheduled for later. Turn it off to revisit them now. Owner, month, minimum review loss, and due-only filters work together. Changing a filter starts a fresh review cycle.',
    ]),
    ('Answer a puzzle on the board', [
        'Drag a piece to its destination. For promotion, choose the new piece. Your piece stays on its destination while the answer is checked. The app accepts the saved best move and accepted alternatives.',
        'An incorrect answer resets the board so you can try again. The error clears when you begin another attempt. A correct answer automatically plays the saved continuation when available; Replay solution plays it again without recording another attempt.',
        'Hint points to the piece to move. Reveal solution and original mistake shows your original move, the engine line, and the evaluation change. Open original game is available when a game link was saved. Click Next puzzle when ready to continue.',
    ]),
    ('Finish a cycle or take a break', [
        'A cycle visits each puzzle in the selected queue once. After the last puzzle, click Next puzzle to choose Take a rest or Start over with shuffled puzzles. You can also select another month to review.',
        'Starting over repeats the same round in a randomized order, including puzzles scheduled for later. Saved review progress is kept. It repeats all puzzles in that round, not only those answered incorrectly.',
    ]),
    ('Understand review scheduling', [
        'A correct answer schedules the puzzle after 1 day, then 2, 4, 8, 16, and up to 30 days as your correct streak grows. An incorrect answer resets the streak and schedules it after 10 minutes.',
        'If you answer incorrectly and then retry correctly, the correct answer replaces the 10-minute schedule with a 1-day review. A due time is not a reminder: there is no automatic pop-up, and missed puzzles are not added back into the current cycle. Start a new due-only cycle to pick up puzzles that have become due.',
    ]),
    ('Switch languages', [
        'Use Language / 语言 in the sidebar to switch between English and Simplified Chinese. Your selected filters and current review cycle stay in place. Chess move notation and player usernames stay unchanged.',
    ]),
]


def show_guide(online=False):
    st.header(tr('How it works'))
    st.write(tr('Turn mistakes from your own games into puzzles, then practice them with saved review progress.'))
    for title, paragraphs in SECTIONS:
        st.subheader(tr(title))
        for paragraph in paragraphs:
            st.write(tr(paragraph))
    if online:
        st.subheader(tr('Online beta and your saved library'))
        st.write(tr('Sign in with the username and password assigned by the app administrator. Each app account has its own saved puzzle library and review history. Entering a chess username chooses which player to analyze; it does not verify that you own that chess account.'))
        st.write(tr('The beta analyzes up to five games per request, with up to six requests per day. Selecting a month does not analyze every game in that month. Lichess imports public, completed standard games, newest first, using UTC month boundaries.'))
        st.write(tr('Analysis runs in the background. After it finishes, click Update puzzle library to load the new puzzles and start a new cycle with your current filters. This does not reanalyze games or delete puzzles. Old completion messages stay hidden when you sign in.'))
        st.write(tr('You can stay signed in for up to 12 hours. A full browser refresh requires signing in again, but your saved puzzles and review history remain.'))
    else:
        st.subheader(tr('Local setup and storage'))
        st.write(tr('Set Stockfish executable path to the Stockfish program on your computer. Local analysis runs while this app is open. Lichess imports up to the Maximum games to import setting; Chess.com imports standard games from the selected month.'))
        st.write(tr('The local app saves puzzles and review history in puzzles.json. Imported samples may have an unknown owner or date. Back up that file to keep your local progress.'))
