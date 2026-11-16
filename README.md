# Chess Mistake Trainer

Generate puzzles from your own moves in Chess.com archives or uploaded PGNs, then practice with saved review progress. Requires Python 3.10+ and a separately installed Stockfish executable.

## Start (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:STOCKFISH_PATH = 'C:\path\to\stockfish.exe'
python -m streamlit run visualization_all.py
```

If dependencies have already been installed locally in `.deps`, start directly with `python run_trainer.py`.

You can also enter the engine path in the app. Enter your username as it appears in PGN player headers (case does not matter). Choose a Chess.com month or upload a PGN with one or several games. Only standard chess and your moves are analyzed. Repeat generation for more months; existing puzzles and progress are preserved.

## Command line

```powershell
python chess_analysis.py ursabearattack --year 2026 --month 6
python chess_analysis.py ursabearattack --pgn games.pgn --depth 15 --threshold 150
```

Use `--engine 'C:\path\to\stockfish.exe'` instead of the environment variable if preferred. Threshold is in centipawns (100 = one pawn). Mate allowed and forced mate missed are tracked separately. Analysis ranks every legal first move to accept alternatives within 30 centipawns of the best move; this can be slow at depth 15. Mate alternatives must have the same mate score. Engine evaluations are depth-limited estimates. Not every evaluation drop will be a clean tactical puzzle.

## Review and storage

Drag a piece onto its destination, or click the source and destination squares. Legal destinations are highlighted. For promotion, choose Queen, Rook, Bishop, or Knight. Illegal drops return to the starting position. The board faces the side to move and works with mouse or touch. Castling is entered by moving the king to its destination; en passant works normally. The original position stays available for retries after each answer.

Typed SAN (`Nf3`, `O-O`) and UCI (`g1f3`, promotion `e7e8q`) remain available. Use hints, reveal the continuation, or choose Next puzzle. Correct answers are scheduled after 1, 2, 4, 8, 16, then 30 days; wrong answers after 10 minutes. Turn off the due-only filter to practice all puzzles. The draggable board is bundled locally and needs no CDN or extra dependencies.

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
