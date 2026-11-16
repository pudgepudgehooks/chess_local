"""Optional API: python -m uvicorn wrapped_stockfish:app"""
from contextlib import asynccontextmanager
from threading import Lock
import chess
import chess.engine
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from chess_analysis import engine_path


@asynccontextmanager
async def lifespan(app):
    with chess.engine.SimpleEngine.popen_uci(engine_path()) as engine:
        app.state.engine = engine
        app.state.lock = Lock()
        yield


app = FastAPI(lifespan=lifespan)


class Position(BaseModel):
    fen: str


@app.post('/analyze')
def analyze(position: Position):
    try:
        board = chess.Board(position.fen)
        if not board.is_valid():
            raise ValueError('Invalid chess position')
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if board.is_game_over():
        return {'best_move': None, 'game_over': True}
    with app.state.lock:
        result = app.state.engine.play(board, chess.engine.Limit(time=0.1))
    return {'best_move': result.move.uci(), 'game_over': False}
