# ChessLab - CSE 150B Group Project

Welcome to ChessLab. In this project, you'll implement a chess-playing AI using the search algorithms we've covered in class. Your AI will compete against your classmates' implementations in a class tournament.

## Game Rules

We're using standard chess rules with a few simplifications to keep the focus on search algorithms:

- No castling
- No en passant
- Pawn promotion is to Queen only

These omissions mean you don't have to worry about edge cases in move generation. The `Board` class handles all the legal move logic for you.

## Getting Started

### Running the GUI

From the project root:

```bash
python main.py --gui
```

Click a piece, then click a destination square. You can play:
- Human vs Human
- Human vs AI
- AI vs AI

Use the dropdown menus to select the AI algorithm and search depth.

### Running AI vs AI (Headless)

For faster iteration without the GUI:

```bash
# Your AI vs itself
python main.py --white chesslab/ai/ai.py --black chesslab/ai/ai.py --time 5

# With custom time limit and max moves
python main.py --white chesslab/ai/ai.py --black chesslab/ai/ai.py --time 2 --max-moves 100
```

## Your Task

All your work goes in `chesslab/ai/ai.py`. This is the **only file** you'll submit to Gradescope.

You need to implement:

1. **`evaluate(board)`** - Return a heuristic score from White's perspective. Positive = good for White, negative = good for Black.

2. **`choose_minimax_move(board, depth, metrics)`** - Pick a move using minimax search (no pruning). Return `(move, nodes_visited)`.

3. **`choose_alphabeta_move(board, depth, metrics)`** - Pick a move using alpha-beta pruning. Return `(move, nodes_visited)`.

4. **`choose_move(board)`** (optional but recommended) - A generator function for iterative deepening. More on this below.

A basic `choose_random_move(board)` is provided for reference.

## The Tournament

Your submissions compete against each other in a class-wide tournament. Here's what you need to know.

### Tournament Rounds

The tournament runs five rounds with increasing time limits:

| Round     | Time per Move |
|-----------|---------------|
| Sprint    | ? seconds     |
| Blitz     | ? seconds     |
| Rapid     | ? seconds    |
| Classical | ? seconds    |
| Extended  | ? seconds    |

Each team plays every other team six times per round (three games as White, three as Black).

### Scoring

- Win: 1 point
- Draw: 0.5 points
- Loss: 0 points

Final standings aggregate points across all rounds.

### Material Diff (Tiebreaker)

In the tournament results, you'll see a "Material Diff" column. This is the cumulative material difference across all your games, calculated using standard piece values (Pawn=1, Knight=3, Bishop=3, Rook=5, Queen=9).

A positive Material Diff means you ended games with more material than your opponents on average. It's used as a tiebreaker when teams have the same points - if you're winning games but doing so with more pieces on the board, that's a sign of stronger play.

### Time Limits and Forfeits

**Your AI does not receive the time limit as a parameter.** You need to design your search to return reasonable moves quickly.

If your AI doesn't return a move before time runs out, you forfeit that move (your opponent gets to move again). This is more forgiving than losing the entire game, but you're still at a disadvantage.

### Which Function Gets Called?

The tournament checks for functions in this order:

1. `choose_move(board)` - Preferred (generator or regular function)
2. `choose_alphabeta_move(board, depth, metrics)`
3. `choose_minimax_move(board, depth, metrics)`
4. `choose_random_move(board)`

The first one found is used. If you implement `choose_move`, that's what runs in the tournament.

## Iterative Deepening with Generators

Here's the key insight: with a fixed time limit and no depth parameter, you want to search as deep as possible while always having a move ready. This is where iterative deepening shines.

Python generators let you yield moves progressively. The tournament uses the **last move you yielded** when time runs out:

```python
def choose_move(board):
    legal_moves = board.legal_moves()
    if not legal_moves:
        return

    # Yield something immediately to avoid forfeit
    yield legal_moves[0]

    # Now search deeper and yield better moves
    for depth in range(1, 50):
        best_move = alphabeta_search(board, depth)
        if best_move:
            yield best_move
```

**Critical**: Yield a move early. If time expires before you yield anything, you forfeit your move. The generator pattern gives you a safety net while still allowing deeper search when time permits.

## Board API Reference

The `Board` class provides everything you need:

```python
board.turn           # 'w' or 'b' - whose turn it is
board.legal_moves()  # List of legal Move objects
board.clone()        # Deep copy of the board
board.make(move)     # Apply a move (modifies the board)
board.piece_at(r, c) # Get piece at row, col (e.g., 'wK', 'bP', or None)
board.outcome()      # None, ('checkmate', winner), or ('stalemate', None)
board.is_check(color) # Is the given color in check?
```

A `Move` object has:
```python
move.src      # (row, col) tuple - starting square
move.dst      # (row, col) tuple - ending square
move.promote  # 'Q' if pawn promotion, else None
```

Board coordinates: row 0 is Black's back rank, row 7 is White's back rank. Column 0 is the a-file, column 7 is the h-file.

## Project Structure

```
chesslab/
├── __init__.py
├── board.py         # Board representation and move generation
├── gui.py           # Tkinter interface
├── mode.py          # Game mode helpers
├── main.py          # Entry point
└── ai/
    ├── __init__.py
    ├── ai.py        # YOUR CODE GOES HERE
    └── random_agent.py
```

## Tips

1. **Start simple.** Get minimax working before adding alpha-beta. Get alpha-beta working before iterative deepening.

2. **Test locally.** Use the headless mode to run many games quickly. Don't rely on Gradescope for iteration.

3. **Evaluation matters.** A good evaluation function with shallow search often beats a bad evaluation function with deep search.

4. **Move ordering helps alpha-beta.** Try captures first, or moves that were good at shallower depths.

5. **Profile your code.** If you're only reaching depth 2 in 5 seconds, something's wrong. The provided `Counter` class in `common/profiling.py` can help track node counts.

6. **Don't import external libraries.** The tournament environment only has the standard library and the `chesslab` package. No chess libraries, nothing else. Only Numpy is allowed so only `import numpy` or `import numpy as np` are allowed.

## Submission

Upload only `ai.py` to Gradescope. The autograder tests basic functionality (does your code run? does it return legal moves?). I will try to run the tournament often to provide feedback, but the final tournament performance will be evaluated separately after the deadline.

## Questions?

Post on Piazza for coding questions, and on Discord for general (non coding related) questions, or come to office hours. Don't post your code publicly!!! Or face my wrath.

Good luck, and may the best search algorithm win.

-- Your Prof
