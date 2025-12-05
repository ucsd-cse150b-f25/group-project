import argparse

def run_headless(white_ai_path, black_ai_path, time_limit, max_moves):
    """Run AI vs AI match without GUI."""
    import time
    import importlib.util
    import inspect
    from chesslab.board import Board
    from chesslab.ai import random_agent

    def load_ai_module(path):
        if path is None:
            return None
        import importlib.util
        # Set up package context for relative imports
        spec = importlib.util.spec_from_file_location(
            "chesslab.ai.custom_ai",
            path,
            submodule_search_locations=[]
        )
        module = importlib.util.module_from_spec(spec)
        module.__package__ = "chesslab.ai"
        spec.loader.exec_module(module)
        return module

    def is_generator_function(func):
        return inspect.isgeneratorfunction(func)

    def get_ai_function(module):
        if module is None:
            return None, None
        if hasattr(module, 'choose_move'):
            return module.choose_move, 'IDS' if is_generator_function(module.choose_move) else 'Function'
        if hasattr(module, 'choose_alphabeta_move'):
            return module.choose_alphabeta_move, 'AlphaBeta'
        if hasattr(module, 'choose_minimax_move'):
            return module.choose_minimax_move, 'Minimax'
        if hasattr(module, 'choose_random_move'):
            return module.choose_random_move, 'Random'
        return None, None

    def _run_generator_in_process(ai_func, board, result_queue):
        """Worker function for generator AI - runs in separate process."""
        try:
            gen = ai_func(board)
            for move in gen:
                if move is not None:
                    result_queue.put(('move', (move.src, move.dst, getattr(move, 'promotion', None))))
            result_queue.put(('done', None))
        except Exception as e:
            result_queue.put(('error', f"{type(e).__name__}: {str(e)}"))

    def _run_function_in_process(ai_func, board, result_queue, kwargs):
        """Worker function for regular AI - runs in separate process."""
        try:
            ret = ai_func(board, **kwargs)
            if isinstance(ret, tuple):
                move = ret[0]
            else:
                move = ret
            if move is not None:
                result_queue.put(('result', (move.src, move.dst, getattr(move, 'promotion', None))))
            else:
                result_queue.put(('result', None))
        except Exception as e:
            result_queue.put(('error', f"{type(e).__name__}: {str(e)}"))

    def run_generator_with_timeout(ai_func, board, timeout):
        """Run a generator AI with timeout using multiprocessing."""
        import multiprocessing
        from chesslab.board import Move

        result_queue = multiprocessing.Queue()
        process = multiprocessing.Process(
            target=_run_generator_in_process,
            args=(ai_func, board, result_queue)
        )

        start_time = time.time()
        process.start()

        last_move = None
        moves_yielded = 0
        error = None
        completed = False

        deadline = start_time + timeout
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            try:
                msg_type, value = result_queue.get(timeout=min(0.1, remaining))
                if msg_type == 'move':
                    src, dst, promotion = value
                    last_move = Move(src, dst, promotion)
                    moves_yielded += 1
                elif msg_type == 'done':
                    completed = True
                    break
                elif msg_type == 'error':
                    error = value
                    break
            except:
                if not process.is_alive():
                    break

        elapsed = time.time() - start_time

        if process.is_alive():
            process.terminate()
            process.join(timeout=0.5)
            if process.is_alive():
                process.kill()

        return last_move, moves_yielded, elapsed, completed, error

    def run_function_with_timeout(ai_func, board, timeout, **kwargs):
        """Run a function AI with timeout using multiprocessing."""
        import multiprocessing
        from chesslab.board import Move

        result_queue = multiprocessing.Queue()
        process = multiprocessing.Process(
            target=_run_function_in_process,
            args=(ai_func, board, result_queue, kwargs)
        )

        start_time = time.time()
        process.start()
        process.join(timeout=timeout)
        elapsed = time.time() - start_time

        move = None
        error = None
        completed = False

        if process.is_alive():
            process.terminate()
            process.join(timeout=0.5)
            if process.is_alive():
                process.kill()
            return None, elapsed, False, "Timeout"

        # Process finished, get result
        try:
            if not result_queue.empty():
                msg_type, value = result_queue.get_nowait()
                if msg_type == 'result':
                    if value is not None:
                        src, dst, promotion = value
                        move = Move(src, dst, promotion)
                    completed = True
                elif msg_type == 'error':
                    error = value
                    completed = True
        except:
            pass

        return move, elapsed, completed, error

    # Load AI modules
    white_module = load_ai_module(white_ai_path)
    black_module = load_ai_module(black_ai_path)

    white_func, white_type = get_ai_function(white_module)
    black_func, black_type = get_ai_function(black_module)

    if white_func is None:
        white_func = random_agent.choose_move
        white_type = 'Random'
    if black_func is None:
        black_func = random_agent.choose_move
        black_type = 'Random'

    print(f"White: {white_ai_path or 'Random'} ({white_type})")
    print(f"Black: {black_ai_path or 'Random'} ({black_type})")
    print(f"Time limit: {time_limit}s per move")
    print(f"Max moves: {max_moves}")
    print("-" * 50)

    board = Board()
    move_count = 0

    while move_count < max_moves:
        outcome = board.outcome()
        if outcome:
            kind, winner = outcome
            if kind == 'checkmate':
                print(f"\nCheckmate! {'White' if winner == 'w' else 'Black'} wins.")
            else:
                print(f"\nStalemate!")
            break

        current_color = board.turn
        color_name = 'White' if current_color == 'w' else 'Black'
        ai_func = white_func if current_color == 'w' else black_func
        ai_type = white_type if current_color == 'w' else black_type

        move = None
        forfeit = False

        if ai_type == 'IDS':
            move, moves_yielded, elapsed, completed, error = run_generator_with_timeout(ai_func, board, time_limit)
            if move is None and not completed:
                forfeit = True
        elif ai_type in ('AlphaBeta', 'Minimax'):
            move, elapsed, completed, error = run_function_with_timeout(ai_func, board.clone(), time_limit, depth=3, metrics={})
            if isinstance(move, tuple):
                move = move[0]
            if move is None and not completed:
                forfeit = True
        else:
            move, elapsed, completed, error = run_function_with_timeout(ai_func, board.clone(), time_limit)
            if move is None and not completed:
                forfeit = True

        if forfeit:
            # Forfeit the move (skip turn), not the game
            print(f"Move {move_count + 1}: {color_name} forfeits move (timeout)")
            board.turn = board.enemy(board.turn)
            move_count += 1
            continue

        if move is None:
            winner = 'Black' if current_color == 'w' else 'White'
            print(f"\n{color_name} returned no move. {winner} wins!")
            break

        board.make(move)
        move_count += 1
        print(f"Move {move_count}: {color_name} {move} ({ai_type}, {elapsed:.2f}s)")

    if move_count >= max_moves:
        print(f"\nDraw by move limit ({max_moves} moves).")

    print("-" * 50)
    print("Game complete.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='ChessLab - Chess AI Testing Environment')
    parser.add_argument('--white', type=str, default=None,
                        help='Path to ai.py file for White player')
    parser.add_argument('--black', type=str, default=None,
                        help='Path to ai.py file for Black player')
    parser.add_argument('--gui', action='store_true',
                        help='Launch GUI (required if using --white/--black with GUI)')
    parser.add_argument('--time', type=float, default=5.0,
                        help='Time limit per move in seconds (default: 5.0)')
    parser.add_argument('--max-moves', type=int, default=200,
                        help='Maximum moves before draw (default: 200)')
    args = parser.parse_args()

    if args.gui or (args.white is None and args.black is None):
        # Launch GUI
        from chesslab.gui import main
        main(white_ai=args.white, black_ai=args.black, time_limit=args.time)
    else:
        # Run headless AI vs AI
        run_headless(args.white, args.black, args.time, args.max_moves)
