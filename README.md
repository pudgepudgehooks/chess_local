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

During analysis, the progress bar shows the current game, the number of your moves examined across the batch, and the completion percentage. In the online beta it refreshes automatically every three seconds, including after you leave and return. It reaches 100% only once the puzzles have been saved. Progress is based on moves examined rather than an estimate of remaining time; some positions take longer than others.

For Lichess, choose **Lichess month**, enter your Lichess username and a year/month. Public, completed standard games are downloaded newest first using UTC month boundaries; no Lichess password or API token is needed. Local imports default to 20 games (maximum 100); the online beta imports at most five. Variant and ongoing games are excluded. If Lichess rate limits a request, wait at least a minute before retrying. Existing analysis, drag-and-drop, and review scheduling work with either platform. API reference: https://lichess.org/api#tag/Games/operation/apiGamesUser

Use **Language / 语言** in the sidebar to switch between English and Simplified Chinese. The setting is kept during the session and in the page URL (`?lang=zh` or `?lang=en`). App labels, feedback, beta access messages, and draggable-board controls are translated; player names and SAN/UCI chess notation are preserved. Streamlit's built-in menus and file-picker chrome follow the framework/browser language.

Drag a piece onto its destination, or click the source and destination squares. Legal destinations are highlighted. For promotion, choose Queen, Rook, Bishop, or Knight. The piece stays on the dropped square while the server checks it. Incorrect answers show “Try again” and reset the position. Correct answers automatically play the legal engine continuation, keep the final position visible, and offer Replay solution. Castling, promotions and en passant are handled by the chess engine's board snapshots. Input is disabled during checking and after solving; use Next puzzle to continue.

Answers are entered through the board only. New puzzles store continuations for accepted alternatives too. Older puzzles without a stored line use a short Stockfish search when an engine path is configured; if no continuation is available, the accepted move stays visible with an explanatory message. Use hints, reveal the continuation, or choose Next puzzle. Correct answers are scheduled after 1, 2, 4, 8, 16, then 30 days; wrong answers after 10 minutes. Turn off the due-only filter to practice all puzzles. Only the most recent analysis status is shown. The draggable board is bundled locally and needs no CDN or extra dependencies.

`puzzles.json` beside the scripts stores puzzles and review progress. When no library exists, `mistakes.json` is imported without modifying it. Those samples have unknown ownership and are labeled; newly generated puzzles have separate source-based IDs. Back up `puzzles.json`. Concurrent writers are not supported; run one local trainer session at a time.

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
