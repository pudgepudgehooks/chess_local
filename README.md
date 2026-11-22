# Chess Mistake Trainer

## Private online beta

The online entry point is **beta_app.py**, with administrator-assigned usernames/passwords for up to four people, private PostgreSQL puzzle libraries, and bounded background Stockfish analysis. There is no self-registration or Google login. Generate account hashes with `python account_admin.py USERNAME`, then paste the generated sections into Streamlit Secrets. Follow [DEPLOYMENT.md](DEPLOYMENT.md). The local trainer below remains available for personal use and is not the entry point to publish.

Generate puzzles from your own moves in Chess.com archives, Lichess history, or uploaded PGNs, then practice with saved review progress. Requires Python 3.10+ and a separately installed Stockfish executable.

## Start (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:STOCKFISH_PATH = 'C:\path\to\stockfish.exe'
python -m streamlit run visualization_all.py
```

If dependencies have already been installed locally in `.deps`, start directly with `python run_trainer.py`.

You can also enter the engine path in the app. Enter your username as it appears in PGN player headers (case does not matter). Choose a Chess.com or Lichess month, or upload a PGN with one or several games. Only standard chess and your moves are analyzed. Repeat generation for more months; existing puzzles and progress are preserved.

## Command line

```powershell
python chess_analysis.py ursabearattack --year 2026 --month 6
python chess_analysis.py ursabearattack --pgn games.pgn --depth 15 --threshold 150
python chess_analysis.py YOUR_LICHESS_USERNAME --source lichess --year 2026 --month 10 --max-games 20
```

Use `--engine 'C:\path\to\stockfish.exe'` instead of the environment variable if preferred. Threshold is in centipawns (100 = one pawn). Mate allowed and forced mate missed are tracked separately. Analysis ranks every legal first move to accept alternatives within 30 centipawns of the best move; this can be slow at depth 15. Mate alternatives must have the same mate score. Engine evaluations are depth-limited estimates. Not every evaluation drop will be a clean tactical puzzle.

## Review and storage

Open the **How it works** tab beside **Practice** for an English or Simplified Chinese guide to generating puzzles, saved-library filters, board controls, review cycles, review scheduling, and the relevant local or online setup. Your practice queue and filters stay in place while using the guide.

The **Mistake library** tab shows a paginated grid of starting-board previews, with game dates, opponents, losses, attempt counts, and review status. Shared filters above the tabs apply to both Practice and the library; turn off due-only to browse scheduled puzzles too. Choose **Review this puzzle** to switch to Practice with a fresh board and start a round from that puzzle, followed by the other matching puzzles. Browsing does not record attempts. Previews show no solution moves, and the online library only loads the signed-in account's saved puzzles.

During analysis, the progress bar shows the current game, the number of your moves examined across the batch, and the completion percentage. In the online beta it refreshes automatically every three seconds, including after you leave and return. It reaches 100% only once the puzzles have been saved. Progress is based on moves examined rather than an estimate of remaining time; some positions take longer than others.

For Lichess, choose **Lichess month**, enter your Lichess username and a year/month. Public, completed standard games are downloaded newest first using UTC month boundaries; no Lichess password or API token is needed. Local imports default to 20 games (maximum 100); the online beta imports at most five. Variant and ongoing games are excluded. If Lichess rate limits a request, wait at least a minute before retrying. Existing analysis, drag-and-drop, and review scheduling work with either platform. API reference: https://lichess.org/api#tag/Games/operation/apiGamesUser

Use **Language / 语言** in the sidebar to switch between English and Simplified Chinese. The setting is kept during the session and in the page URL (`?lang=zh` or `?lang=en`). App labels, feedback, beta access messages, and draggable-board controls are translated; player names and SAN/UCI chess notation are preserved. Streamlit's built-in menus and file-picker chrome follow the framework/browser language.

Drag a piece onto its destination, or click the source and destination squares. Legal destinations are highlighted. For promotion, choose Queen, Rook, Bishop, or Knight. The piece stays on the dropped square while the server checks it. Incorrect answers show “Try again” and reset the position. Correct answers automatically play the legal engine continuation, keep the final position visible, and offer Replay solution. Castling, promotions and en passant are handled by the chess engine's board snapshots. Input is disabled during checking and after solving; use Next puzzle to continue.

Answers are entered through the board only. New puzzles store continuations for accepted alternatives too. Older puzzles without a stored line use a short Stockfish search when an engine path is configured; if no continuation is available, the accepted move stays visible with an explanatory message. Use hints, reveal the continuation, or choose Next puzzle. Correct answers are scheduled after 1, 2, 4, 8, 16, then 30 days; wrong answers after 10 minutes. Turn off the due-only filter to practice all puzzles. Past analysis completion messages stay hidden on login. The current session shows progress for analysis you start or resume watching, followed by its completion result. The draggable board is bundled locally and needs no CDN or extra dependencies.

`puzzles.json` beside the scripts stores puzzles and review progress. When no library exists, `mistakes.json` is imported without modifying it. Those samples have unknown ownership and are labeled; newly generated puzzles have separate source-based IDs. Back up `puzzles.json`. Concurrent writers are not supported; run one local trainer session at a time.

Each review cycle visits the selected puzzles once. After the last puzzle, choose **Take a rest** or **Start over with shuffled puzzles**. Starting over repeats the same puzzles in a new random order, including puzzles scheduled for later review, without clearing saved progress. The board starts fresh for each round. Changing the owner or due-only filter begins a new cycle. **Generate puzzles** now handles saving and refreshing the library: after an online analysis commits, the progress monitor reloads the app once and starts a fresh cycle using the current filters. There is no separate update button. Historical completion messages stay hidden on login.

Repeated analysis updates existing puzzles without adding copies or replacing their review history. Duplicate detection uses the player, game link, starting position, and original move, and normalizes common Chess.com/Lichess link variations. PGNs without a game link use the available player, date, opponent, position, and original move. Distinct linked games remain separate. Older duplicate rows are consolidated within each account, preserving review records and reattaching recorded review events; local libraries are deduplicated when loaded and saved.

Use **Saved game month** to review one month, such as `2026-08`, or choose **All months**. Months come from the saved game's date, not the date you generated the puzzles. Undated samples and PGNs with an unknown month appear under **Unknown date**. Changing the month starts a new cycle limited to that month; shuffled restarts stay within it. Switching months keeps all saved puzzles and review history. Turn off the due-only filter to revisit a month's puzzles before their next scheduled review.

Use **Minimum review loss (centipawns)** to filter the saved library independently of the analysis threshold. Set it to `300` to practice only recorded losses of at least 300 centipawns; smaller mistakes stay saved and reappear if you lower the filter. The month, owner, and due-only filters still apply, and shuffled restarts use only the matching round. The default `0` shows all saved losses, including mate-related or old puzzles without a numeric loss. Positive thresholds exclude those puzzles because they have no centipawn value. Changing the review threshold starts a fresh cycle without changing review history or analysis settings.

Old visualization entry points launch the same draggable trainer. The trainer does not need the optional API.

## Optional API

```powershell
python -m pip install -r requirements-api.txt
python -m uvicorn wrapped_stockfish:app
```

Set `STOCKFISH_PATH` before starting. `POST /analyze` takes a JSON body with a `fen` string. See `/docs` for the request schema.

## Tests

```powershell
python -m unittest discover -s tests -v
```

Tests use a fake engine and temporary storage; no network or Stockfish download is required.
