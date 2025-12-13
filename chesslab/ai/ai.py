"""
Core AI routines for ChessLab.

All of the student work for this assignment lives in this file. Implement the
functions below so that:
  * `evaluate` returns a heuristic score for the given board state.
  * `choose_minimax_move` picks a move via minimax search (no pruning).
  * `choose_alphabeta_move` picks a move via minimax with alpha-beta pruning.

The helper `choose_random_move` is provided for you.
"""

from __future__ import annotations

import random
from typing import Optional, Tuple

from ..common.profiling import Counter

MoveType = Tuple[Tuple[int, int], Tuple[int, int], Optional[str]]

class ExportMove:
    """Move-like object compatible with both `.promote` and `.promotion`."""

    __slots__ = ("src", "dst", "promote", "promotion")

    def __init__(self, src, dst, promo: Optional[str] = None):
        self.src = src
        self.dst = dst
        self.promote = promo
        self.promotion = promo

    def __iter__(self):
        # Board.make(move) does: (src, dst, promo) = move
        return iter((self.src, self.dst, self.promote))

    def __repr__(self):
        p = ("," + self.promote) if self.promote else ""
        return f"Move({self.src}->{self.dst}{p})"

def _promo_of(move) -> Optional[str]:
    return getattr(move, "promotion", getattr(move, "promote", None))

def _export(move):
    if move is None:
        return None
    if hasattr(move, "promotion"):
        return move
    return ExportMove(move.src, move.dst, _promo_of(move))


def choose_random_move(board):
    """Return a uniformly random legal move or None if no moves exist."""
    legal = board.legal_moves()
    return random.choice(legal) if legal else None

# Evaluation
_PIECE_VALUE = {"P": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 0}
_MATE = 100_000
_INF = 10**18

# Piece-square tables:
_PST = {
    "P": [
        [0,   0,  0,  0,  0,  0,  0,  0],
        [5,  10, 10,-20,-20, 10, 10,  5],
        [5,  -5,-10,  0,  0,-10, -5,  5],
        [0,   0,  0, 20, 20,  0,  0,  0],
        [5,   5, 10, 25, 25, 10,  5,  5],
        [10, 10, 20, 30, 30, 20, 10, 10],
        [50, 50, 50, 50, 50, 50, 50, 50],
        [0,   0,  0,  0,  0,  0,  0,  0],
    ],
    "N": [
        [-50,-40,-30,-30,-30,-30,-40,-50],
        [-40,-20,  0,  0,  0,  0,-20,-40],
        [-30,  0, 10, 15, 15, 10,  0,-30],
        [-30,  5, 15, 20, 20, 15,  5,-30],
        [-30,  0, 15, 20, 20, 15,  0,-30],
        [-30,  5, 10, 15, 15, 10,  5,-30],
        [-40,-20,  0,  5,  5,  0,-20,-40],
        [-50,-40,-30,-30,-30,-30,-40,-50],
    ],
    "B": [
        [-20,-10,-10,-10,-10,-10,-10,-20],
        [-10,  0,  0,  0,  0,  0,  0,-10],
        [-10,  0,  5, 10, 10,  5,  0,-10],
        [-10,  5,  5, 10, 10,  5,  5,-10],
        [-10,  0, 10, 10, 10, 10,  0,-10],
        [-10, 10, 10, 10, 10, 10, 10,-10],
        [-10,  5,  0,  0,  0,  0,  5,-10],
        [-20,-10,-10,-10,-10,-10,-10,-20],
    ],
    "R": [
        [0,  0,  0,  5,  5,  0,  0,  0],
        [-5, 0,  0,  0,  0,  0,  0, -5],
        [-5, 0,  0,  0,  0,  0,  0, -5],
        [-5, 0,  0,  0,  0,  0,  0, -5],
        [-5, 0,  0,  0,  0,  0,  0, -5],
        [-5, 0,  0,  0,  0,  0,  0, -5],
        [5, 10, 10, 10, 10, 10, 10,  5],
        [0,  0,  0,  0,  0,  0,  0,  0],
    ],
    "Q": [
        [-20,-10,-10, -5, -5,-10,-10,-20],
        [-10,  0,  0,  0,  0,  0,  0,-10],
        [-10,  0,  5,  5,  5,  5,  0,-10],
        [-5,   0,  5,  5,  5,  5,  0, -5],
        [0,    0,  5,  5,  5,  5,  0, -5],
        [-10,  5,  5,  5,  5,  5,  0,-10],
        [-10,  0,  5,  0,  0,  0,  0,-10],
        [-20,-10,-10, -5, -5,-10,-10,-20],
    ],
    "K": [
        [20, 30, 10,  0,  0, 10, 30, 20],
        [20, 20,  0,  0,  0,  0, 20, 20],
        [-10,-20,-20,-20,-20,-20,-20,-10],
        [-20,-30,-30,-40,-40,-30,-30,-20],
        [-30,-40,-40,-50,-50,-40,-40,-30],
        [-30,-40,-40,-50,-50,-40,-40,-30],
        [-30,-40,-40,-50,-50,-40,-40,-30],
        [-30,-40,-40,-50,-50,-40,-40,-30],
    ],
}

def evaluate(board):
    """Heuristic evaluation from White's perspective (positive = good for White)."""
    score = 0
    for r in range(8):
        for c in range(8):
            pc = board.piece_at(r, c)
            if not pc:
                continue
            color, kind = pc[0], pc[1]
            base = _PIECE_VALUE[kind]
            pst = _PST[kind]
            if color == "w":
                score += base + pst[7 - r][c]
            else:
                score -= base + pst[r][c]
    if board.is_check("b"):
        score += 30
    if board.is_check("w"):
        score -= 30

    return score

def _terminal_score(board) -> int:
    """Board has no legal moves. Return checkmate/stalemate score."""
    if board.is_check(board.turn):
        winner = board.enemy(board.turn)
        return _MATE if winner == "w" else -_MATE
    return 0

def _has_any_legal_move(board) -> bool:
    """Early-exit legal-move existence check (faster than building full legal_moves())."""
    # Mirrors Board.legal_moves() filtering logic, but stops on the first legal move.
    for mv in board.generate_pseudo_legal():
        b2 = board.clone()
        b2.make(mv)
        king_pos = b2.kings_pos(b2.enemy(b2.turn))
        if king_pos and (not b2.is_square_attacked(king_pos, b2.turn)):
            return True
    return False

def _order_moves(board, moves):
    """Cheap move ordering: promotions > captures (by captured value) > others."""
    def key(mv):
        promo = _promo_of(mv)
        tgt = board.piece_at(mv.dst[0], mv.dst[1])
        cap = _PIECE_VALUE[tgt[1]] if tgt else 0
        return (1 if promo else 0, cap)
    return sorted(moves, key=key, reverse=True)

def _with_pv_hint(moves, pv_hint):
    if pv_hint is None:
        return moves
    src, dst, promo = pv_hint
    for i, mv in enumerate(moves):
        if mv.src == src and mv.dst == dst and _promo_of(mv) == promo:
            if i == 0:
                return moves
            return [moves[i]] + moves[:i] + moves[i + 1 :]
    return moves

def _minimax_value(board, depth, nodes):
    nodes[0] += 1

    if depth <= 0:
        # Avoid expensive full legal move generation most of the time.
        if not _has_any_legal_move(board):
            return _terminal_score(board)
        return evaluate(board)

    moves = board.legal_moves()
    if not moves:
        return _terminal_score(board)

    if board.turn == "w":
        best = -_INF
        for mv in moves:
            b2 = board.clone()
            b2.make(mv)
            best = max(best, _minimax_value(b2, depth - 1, nodes))
        return best
    else:
        best = _INF
        for mv in moves:
            b2 = board.clone()
            b2.make(mv)
            best = min(best, _minimax_value(b2, depth - 1, nodes))
        return best
     
def choose_minimax_move(board, depth=2, metrics=None):
    """Return (best_move, nodes_visited) using minimax (no pruning)."""
    if metrics is None:
        metrics = {}

    legal = board.legal_moves()
    if not legal:
        metrics["nodes"] = 0
        return None, 0

    nodes = [0]
    best_move = None

    if board.turn == "w":
        best_val = -_INF
        for mv in legal:
            b2 = board.clone()
            b2.make(mv)
            v = _minimax_value(b2, depth - 1, nodes)
            if best_move is None or v > best_val:
                best_val = v
                best_move = mv
    else:
        best_val = _INF
        for mv in legal:
            b2 = board.clone()
            b2.make(mv)
            v = _minimax_value(b2, depth - 1, nodes)
            if best_move is None or v < best_val:
                best_val = v
                best_move = mv

    metrics["nodes"] = nodes[0]
    return _export(best_move), nodes[0]

def _alphabeta_value(board, depth, alpha, beta, nodes):
    nodes[0] += 1

    if depth <= 0:
        if not _has_any_legal_move(board):
            return _terminal_score(board)
        return evaluate(board)

    moves = board.legal_moves()
    if not moves:
        return _terminal_score(board)

    moves = _order_moves(board, moves)

    if board.turn == "w":
        v = -_INF
        for mv in moves:
            b2 = board.clone()
            b2.make(mv)
            v = max(v, _alphabeta_value(b2, depth - 1, alpha, beta, nodes))
            alpha = max(alpha, v)
            if alpha >= beta:
                break
        return v
    else:
        v = _INF
        for mv in moves:
            b2 = board.clone()
            b2.make(mv)
            v = min(v, _alphabeta_value(b2, depth - 1, alpha, beta, nodes))
            beta = min(beta, v)
            if alpha >= beta:
                break
        return v
     
def _alphabeta_root(board, depth, pv_hint=None):
    legal = board.legal_moves()
    if not legal:
        return None, 0, 0

    nodes = [0]
    moves = _order_moves(board, legal)
    moves = _with_pv_hint(moves, pv_hint)

    best_move = None
    if board.turn == "w":
        best_val = -_INF
        alpha, beta = -_INF, _INF
        for mv in moves:
            b2 = board.clone()
            b2.make(mv)
            v = _alphabeta_value(b2, depth - 1, alpha, beta, nodes)
            if best_move is None or v > best_val:
                best_val = v
                best_move = mv
            alpha = max(alpha, best_val)
    else:
        best_val = _INF
        alpha, beta = -_INF, _INF
        for mv in moves:
            b2 = board.clone()
            b2.make(mv)
            v = _alphabeta_value(b2, depth - 1, alpha, beta, nodes)
            if best_move is None or v < best_val:
                best_val = v
                best_move = mv
            beta = min(beta, best_val)

    return best_move, best_val, nodes[0]


def choose_alphabeta_move(board, depth=3, metrics=None):
   """Return (best_move, nodes_visited) using alpha-beta pruning."""
    if metrics is None:
        metrics = {}
    best_move, _best_val, nodes = _alphabeta_root(board, depth, pv_hint=None)
    metrics["nodes"] = nodes
    return _export(best_move), nodes


def choose_move(board):
   """Iterative deepening alpha-beta. Yields moves progressively."""
    legal = board.legal_moves()
    if not legal:
        return

    quick = _order_moves(board, legal)[0]
    out = _export(quick)
    yield out

    pv_hint = (out.src, out.dst, _promo_of(out))

        best, _v, _nodes = _alphabeta_root(board, depth, pv_hint=pv_hint)
        if best is None:
            continue
        out = _export(best)
        yield out
        pv_hint = (out.src, out.dst, _promo_of(out))
