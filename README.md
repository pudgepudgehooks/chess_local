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

After signing in, configure everything in the left sidebar: game source, chess username, inclusive start/end dates, **Mistake size: Low (150 centipawns) or High (300 centipawns)**, and due-only preference. To override the preset, enable **Use custom minimum loss** and enter **Minimum loss (centipawns)** under **Advanced settings**. The custom value takes precedence for analysis and review until the override is turned off. Analysis depth and local Stockfish settings are also under Advanced settings. Click **Start reviewing** to apply the selection. The main area contains **Practice**, **Mistake library**, and **How it works**, without selection widgets. Until Start is clicked, sidebar changes are drafts and do not interrupt the current puzzle or change the browsed library. Settings are selected again after a fresh sign-in.

Start checks completed analysis for each fetched game. A completed search at loss 100 and depth 10 can be reused at loss 200 and depth 10; choosing loss 50 or depth 12 requires another search. Records are kept as separate threshold/depth pairs, so two different searches cannot imply coverage they did not provide. New or changed games need analysis. Games that produced zero mistakes are tracked as complete too. Existing libraries without these records conservatively analyze a game once, preserving puzzles and review history. The online records are private to each app account and commit atomically with successful puzzles; failed or interrupted work never marks a game complete. Local records are saved with puzzles.json.

The beta fetches up to 100 recent games, skips covered games, and submits all uncovered fetched games per Start, with no daily analysis quota. Fully cached starts do not queue an analysis job. The ten-minute analysis deadline still applies; narrow the date range if a large selection times out. The import cap does not prove an entire wide date range was fetched: select narrower dates to reach older games. Lichess imports completed standard games in UTC; Chess.com standard-game archives and uploaded PGNs also support inclusive dates. Ranges are limited to 366 days. Unknown dates are excluded. If no PGN is uploaded but that player has saved puzzles, Start can review the matching saved positions without analyzing additional games.

When new analysis is needed, its progress bar reaches 100% only after successful saving. The beta polls every three seconds and opens the selected review automatically when ready. There is no Generate or Update library button. Fully covered starts open immediately. A failed new request leaves the previous applied selection intact. Past completion messages remain hidden on a fresh login.

Use **Language / 语言** to switch between English and Simplified Chinese. Applied settings, draft inputs, and the current round are preserved. The How it works guide explains the current flow in both languages. Chess notation and usernames remain unchanged.

Drag a piece onto its destination. Promotion offers Queen, Rook, Bishop, or Knight. The piece stays on the dropped square while the server checks it. Incorrect answers reset the position, and the feedback clears when another attempt begins. Correct answers stay visible; **Forward** and **Back** below the brown board navigate the legal continuation one move at a time, including back to the original position. There is no automatic playback and no extra review attempt for navigating. Castling, en passant, captures and promotion are represented by legal board snapshots. Use Hint, reveal the original mistake and solution, or click Next puzzle.

The **Mistake library** offers paginated starting-board previews, game details, losses, and review status for the last applied selection. **Review this puzzle** opens a fresh board in Practice and starts a round from that puzzle. Browsing does not record attempts. Each cycle visits its selected puzzles once; after the last puzzle, choose a rest or a shuffled repeat. To change dates or other filters, adjust the sidebar and click Start reviewing. Review history stays saved.

A correct answer schedules review after 1, 2, 4, 8, 16, then up to 30 days. A wrong answer resets the streak and schedules it after 10 minutes. Retrying correctly replaces that with a 1-day review. Due times are scheduling rules, not pop-up reminders or automatic additions to an active round. To revisit scheduled puzzles now, turn off due-only and click Start. A minimum loss of 0 includes saved mate-related positions without a numeric loss.

Repeated analysis updates matching puzzles without adding copies or replacing their review history. Duplicate detection normalizes game links, player names, positions, and the original move; distinct linked games stay separate. Historical duplicates are consolidated within each account and recorded review events are retained. Local files are deduplicated on load/save. Back up puzzles.json for local use; concurrent local file writers are not supported. The online beta uses PostgreSQL for private libraries and coverage records. No Secrets changes are needed for this update; the new coverage table is created automatically.

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
