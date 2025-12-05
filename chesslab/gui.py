
import tkinter as tk
from tkinter import ttk
import time
import inspect
import importlib.util
import os
from .board import Board, WHITE, BLACK
from .ai import random_agent, minimax_ai, alphabeta_ai, ai
from .mode import is_ai_turn, is_human_turn
from .common.profiling import Timer

UNICODE={'wK':'\u2654','wQ':'\u2655','wR':'\u2656','wB':'\u2657','wN':'\u2658','wP':'\u2659',
         'bK':'\u265A','bQ':'\u265B','bR':'\u265C','bB':'\u265D','bN':'\u265E','bP':'\u265F'}
CELL=80


def is_generator_function(func):
    return inspect.isgeneratorfunction(func)


def load_ai_module(path):
    """Load an AI module from a file path."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"AI file not found: {path}")
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


def get_ai_function(module):
    """Get the best available AI function from a module, returns (func, ai_type)."""
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
                # Convert move to serializable format
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
    """
    Run a generator AI with timeout using multiprocessing.
    Returns (move, moves_yielded, elapsed, completed, error).
    """
    import multiprocessing
    from .board import Move

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
    """
    Run a function AI with timeout using multiprocessing.
    Returns (move, elapsed, completed, error).
    """
    import multiprocessing
    from .board import Move

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


class App:
    def __init__(self, root, white_ai_path=None, black_ai_path=None, time_limit=None):
        self.root=root; self.root.title('ChessLab')
        self.board=Board(); self.selected=None
        self.status=tk.StringVar(value='New game. White moves.')
        self.mode=tk.StringVar(value='Human vs AI')
        self.ai=tk.StringVar(value='AlphaBeta'); self.depth=tk.IntVar(value=3)
        self.time_limit=tk.DoubleVar(value=time_limit if time_limit is not None else 5.0)
        self.info=tk.StringVar(value='Ready.')
        self.human_side='w'
        self.ai_busy=False
        self.ai_after_id=None
        self.paused=False
        self.stopped=False
        self.started=False

        # Custom AI modules for white and black
        self.white_ai_module = None
        self.black_ai_module = None
        self.white_ai_func = None
        self.black_ai_func = None
        self.white_ai_type = None
        self.black_ai_type = None

        # Load custom AI files if provided
        if white_ai_path or black_ai_path:
            self.mode.set('AI vs AI')
            if white_ai_path:
                try:
                    self.white_ai_module = load_ai_module(white_ai_path)
                    self.white_ai_func, self.white_ai_type = get_ai_function(self.white_ai_module)
                except Exception as e:
                    self.info.set(f"White AI load error: {e}")
            if black_ai_path:
                try:
                    self.black_ai_module = load_ai_module(black_ai_path)
                    self.black_ai_func, self.black_ai_type = get_ai_function(self.black_ai_module)
                except Exception as e:
                    self.info.set(f"Black AI load error: {e}")

        # Check default ai.py for choose_move
        self.default_ai_func, self.default_ai_type = get_ai_function(ai)

        top=ttk.Frame(root, padding=6); top.pack(fill='x')
        ttk.Button(top,text='New',command=self.new).pack(side='left',padx=4)
        self.start_btn=ttk.Button(top,text='Start',command=self.toggle_start); self.start_btn.pack(side='left',padx=4)
        ttk.Button(top,text='Stop',command=self.stop_ai).pack(side='left',padx=4)
        ttk.Label(top,text='Mode:').pack(side='left'); ttk.Combobox(top,textvariable=self.mode,values=['Human vs Human','Human vs AI','AI vs AI'],state='readonly',width=16).pack(side='left',padx=6)
        ttk.Label(top,text='AI:').pack(side='left'); ttk.Combobox(top,textvariable=self.ai,values=['Random','Minimax','AlphaBeta'],state='readonly',width=10).pack(side='left',padx=6)
        ttk.Label(top,text='Depth:').pack(side='left'); ttk.Spinbox(top,from_=1,to=6,textvariable=self.depth,width=4).pack(side='left',padx=6)
        ttk.Label(top,text='Time(s):').pack(side='left'); ttk.Spinbox(top,from_=0.5,to=60,increment=0.5,textvariable=self.time_limit,width=5).pack(side='left',padx=6)
        ttk.Label(top,textvariable=self.status).pack(side='right')
        self.canvas=tk.Canvas(root,width=8*CELL,height=8*CELL,bg='white'); self.canvas.pack(padx=8,pady=8)
        self.canvas.bind('<Button-1>', self.onclick)
        bottom=ttk.Frame(root,padding=6); bottom.pack(fill='x'); ttk.Label(bottom,textvariable=self.info).pack(side='left')
        self.draw()

    def new(self):
        self.board=Board(); self.selected=None; self.status.set('New game. White moves.'); self.info.set('Ready.');
        if self.ai_after_id is not None:
            try: self.root.after_cancel(self.ai_after_id)
            except Exception: pass
            self.ai_after_id=None
        self.ai_busy=False
        self.paused=False; self.stopped=False; self.started=False
        self.start_btn.configure(text='Start')
        self.draw()

    def draw(self):
        self.canvas.delete('all')
        for r in range(8):
            for c in range(8):
                x0,y0=c*CELL,r*CELL; x1,y1=x0+CELL,y0+CELL
                fill='#eee' if (r+c)%2==0 else '#88a'
                self.canvas.create_rectangle(x0,y0,x1,y1,fill=fill,outline='')
                pc=self.board.board[r][c]
                if pc: self.canvas.create_text((x0+x1)//2,(y0+y1)//2,text=UNICODE[pc],font=('Segoe UI Symbol',36))
        if self.selected:
            r,c=self.selected; self.canvas.create_rectangle(c*CELL,r*CELL,c*CELL+CELL,r*CELL+CELL,outline='yellow',width=3)

    def onclick(self,e):
        if not self.can_human_act():
            self.selected=None
            return
        c,r=e.x//CELL,e.y//CELL
        if self.selected is None:
            pc=self.board.piece_at(r,c)
            if pc and ((pc[0]=='w' and self.board.turn==WHITE) or (pc[0]=='b' and self.board.turn==BLACK)):
                self.selected=(r,c); self.draw()
        else:
            from .board import Move
            if not self.can_human_act():
                self.selected=None; self.draw(); return
            # Find the matching legal move (which includes promotion info if applicable)
            legal = self.board.legal_moves()
            matching = [m for m in legal if m.src == self.selected and m.dst == (r,c)]
            if matching:
                # Use the legal move (auto-promote to Queen if it's a promotion move)
                mv = matching[0]
                self.board.make(mv); self.selected=None; self.after_move()
            else:
                self.selected=None; self.draw()

    def game_over(self):
        return self.board.outcome() is not None

    def can_human_act(self):
        return self.started and (not self.game_over()) and (not self.paused) and (not self.stopped) and (not self.ai_busy) and is_human_turn(self.mode.get(), self.board.turn, self.human_side)

    def toggle_start(self):
        if self.game_over(): return
        if not self.started:
            # Start the game
            self.started=True; self.paused=False; self.stopped=False
            self.status.set('Started. ' + ('White' if self.board.turn=='w' else 'Black') + ' to move.')
            self.start_btn.configure(text='Pause')
            self.ai_after_id = self.root.after(50, self.maybe_ai_move)
        elif self.paused:
            # Resume
            self.paused=False; self.stopped=False
            self.status.set('Resumed.')
            if self.ai_after_id is not None:
                try: self.root.after_cancel(self.ai_after_id)
                except Exception: pass
                self.ai_after_id=None
            self.start_btn.configure(text='Pause')
            self.ai_after_id = self.root.after(50, self.maybe_ai_move)
        else:
            # Pause
            self.paused=True
            self.status.set('Paused.')
            self.start_btn.configure(text='Resume')

    def stop_ai(self):
        self.stopped=True; self.paused=False
        if self.ai_after_id is not None:
            try: self.root.after_cancel(self.ai_after_id)
            except Exception: pass
            self.ai_after_id=None
        self.status.set('Stopped.')

    def after_move(self):
        oc=self.board.outcome()
        if oc:
            kind,winner=oc
            self.status.set('Checkmate. '+('White' if winner=='w' else 'Black')+' wins.' if kind=='checkmate' else 'Stalemate.')
        else:
            self.status.set(('White' if self.board.turn=='w' else 'Black')+' to move.');
            if not self.paused and not self.stopped:
                if self.ai_after_id is not None:
                    try: self.root.after_cancel(self.ai_after_id)
                    except Exception: pass
                    self.ai_after_id=None
                self.ai_after_id = self.root.after(50,self.maybe_ai_move)
        self.draw()

    def get_ai_for_turn(self):
        """Get the AI function and type for the current turn."""
        current_color = self.board.turn
        if current_color == 'w' and self.white_ai_func:
            return self.white_ai_func, self.white_ai_type
        if current_color == 'b' and self.black_ai_func:
            return self.black_ai_func, self.black_ai_type
        # Fall back to default ai.py if choose_move is implemented
        if self.default_ai_func and self.default_ai_type:
            try:
                # Test if it raises NotImplementedError
                test_gen = self.default_ai_func(self.board.clone())
                if is_generator_function(self.default_ai_func):
                    next(test_gen)
                return self.default_ai_func, self.default_ai_type
            except NotImplementedError:
                pass
            except StopIteration:
                return self.default_ai_func, self.default_ai_type
            except:
                pass
        return None, None

    def maybe_ai_move(self):
        if not self.started: return
        if self.board.outcome(): return
        if self.paused or self.stopped: return
        if not is_ai_turn(self.mode.get(), self.board.turn, 'b'): return
        if self.ai_busy: return
        self.ai_busy=True

        current_color = self.board.turn
        color_name = 'White' if current_color == 'w' else 'Black'
        depth=int(self.depth.get())
        timeout=float(self.time_limit.get())
        algo=self.ai.get()
        move=None
        metrics={}
        ai_type_used = algo
        forfeit = False

        try:
            # Check for custom AI or IDS-capable default AI
            ai_func, ai_type = self.get_ai_for_turn()

            if ai_func and ai_type:
                ai_type_used = ai_type
                with Timer('ai_ms', metrics):
                    if ai_type == 'IDS':
                        move, moves_yielded, elapsed, completed, error = run_generator_with_timeout(ai_func, self.board, timeout)
                        metrics['moves_yielded'] = moves_yielded
                        if move is None and not completed:
                            forfeit = True
                    elif ai_type in ('AlphaBeta', 'Minimax'):
                        move, elapsed, completed, error = run_function_with_timeout(
                            ai_func, self.board.clone(), timeout, depth=depth, metrics=metrics
                        )
                        if isinstance(move, tuple):
                            move = move[0]
                        if move is None and not completed:
                            forfeit = True
                    elif ai_type == 'Function':
                        move, elapsed, completed, error = run_function_with_timeout(
                            ai_func, self.board.clone(), timeout
                        )
                        if move is None and not completed:
                            forfeit = True
                    else:  # Random
                        move, elapsed, completed, error = run_function_with_timeout(
                            ai_func, self.board.clone(), timeout
                        )
            else:
                # Use dropdown selection (legacy behavior) with timeout
                with Timer('ai_ms', metrics):
                    try:
                        if algo=='Random':
                            move, elapsed, completed, error = run_function_with_timeout(
                                random_agent.choose_move, self.board.clone(), timeout
                            )
                            if move is None and not completed:
                                forfeit = True
                        elif algo=='Minimax':
                            move, elapsed, completed, error = run_function_with_timeout(
                                minimax_ai.choose_move, self.board.clone(), timeout, depth=depth, metrics=metrics
                            )
                            if isinstance(move, tuple):
                                metrics['nodes'] = move[1] if len(move) > 1 else 0
                                move = move[0]
                            if move is None and not completed:
                                forfeit = True
                        else:
                            move, elapsed, completed, error = run_function_with_timeout(
                                alphabeta_ai.choose_move, self.board.clone(), timeout, depth=depth, metrics=metrics
                            )
                            if isinstance(move, tuple):
                                metrics['nodes'] = move[1] if len(move) > 1 else 0
                                move = move[0]
                            if move is None and not completed:
                                forfeit = True
                    except NotImplementedError as e:
                        self.info.set(f"{algo} not implemented - using Random")
                        move = random_agent.choose_move(self.board)

            if forfeit:
                # Forfeit the move (skip turn), not the game
                self.board.turn = self.board.enemy(self.board.turn)
                self.status.set(f'{color_name} forfeits move (timeout). ' + ('White' if self.board.turn=='w' else 'Black') + ' to move.')
                self.info.set(f"{color_name} AI ({ai_type_used}) timed out - move forfeited")
                self.after_move()
                return

            if move:
                self.board.make(move)
                info_str = f"AI {ai_type_used}"
                if ai_type_used in ('AlphaBeta', 'Minimax'):
                    info_str += f" d={depth}"
                if 'moves_yielded' in metrics:
                    info_str += f" yields={metrics['moves_yielded']}"
                info_str += f" time={metrics.get('ai_ms',0):.1f}ms"
                if 'nodes' in metrics:
                    info_str += f" nodes={metrics['nodes']}"
                self.info.set(info_str)
                self.after_move()
            else:
                # No move returned - forfeit the move (skip turn)
                self.board.turn = self.board.enemy(self.board.turn)
                self.info.set(f"{color_name} AI ({ai_type_used}) returned no move - move forfeited")
                self.after_move()
        finally:
            self.ai_busy=False


def main(white_ai=None, black_ai=None, time_limit=None):
    root=tk.Tk()
    App(root, white_ai_path=white_ai, black_ai_path=black_ai, time_limit=time_limit)
    root.mainloop()

if __name__=='__main__': main()
