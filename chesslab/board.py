
from copy import deepcopy  # Used only for START_POS initialization
WHITE, BLACK='w','b'
PIECE_OFFSETS={'N':[(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)],
'B':[(-1,-1),(-1,1),(1,-1),(1,1)],
'R':[(-1,0),(1,0),(0,-1),(0,1)],
'Q':[(-1,-1),(-1,1),(1,-1),(1,1),(-1,0),(1,0),(0,-1),(0,1)],
'K':[(-1,-1),(-1,1),(1,-1),(1,1),(-1,0),(1,0),(0,-1),(0,1)]}
START_POS=[
['bR','bN','bB','bQ','bK','bB','bN','bR'],
['bP','bP','bP','bP','bP','bP','bP','bP'],
[None]*8,[None]*8,[None]*8,[None]*8,
['wP','wP','wP','wP','wP','wP','wP','wP'],
['wR','wN','wB','wQ','wK','wB','wN','wR'],
]
class Move:
    __slots__=('src','dst','promote')
    def __init__(self, src,dst,promote=None): self.src=src; self.dst=dst; self.promote=promote
    def __iter__(self): return iter((self.src,self.dst,self.promote))
    def __repr__(self): return f"Move({self.src}->{self.dst}{','+self.promote if self.promote else ''})"
class Board:
    def __init__(self): self.board=deepcopy(START_POS); self.turn=WHITE; self.history=[]
    def clone(self):
        b=Board.__new__(Board); b.board=[row[:] for row in self.board]; b.turn=self.turn; b.history=list(self.history); return b
    def piece_at(self,r,c): return self.board[r][c]
    def set_piece(self,r,c,pc): self.board[r][c]=pc
    def kings_pos(self,color):
        for r in range(8):
            for c in range(8):
                if self.board[r][c]==color+'K': return (r,c)
        return None
    def in_bounds(self,r,c): return 0<=r<8 and 0<=c<8
    def enemy(self,color): return BLACK if color==WHITE else WHITE
    def generate_pseudo_legal(self):
        color=self.turn; moves=[]
        for r in range(8):
            for c in range(8):
                pc=self.board[r][c]
                if not pc or pc[0]!=color: continue
                k=pc[1]
                if k=='P':
                    d=-1 if color==WHITE else 1; start=6 if color==WHITE else 1
                    nr=r+d
                    if self.in_bounds(nr,c) and self.board[nr][c] is None:
                        moves.append(Move((r,c),(nr,c),'Q' if nr in (0,7) else None))
                        nr2=r+2*d
                        if r==start and self.board[nr2][c] is None:
                            moves.append(Move((r,c),(nr2,c)))
                    for dc in (-1,1):
                        nc=c+dc
                        if self.in_bounds(nr,nc) and self.board[nr][nc] and self.board[nr][nc][0]!=color:
                            moves.append(Move((r,c),(nr,nc),'Q' if nr in (0,7) else None))
                elif k=='N':
                    for dr,dc in PIECE_OFFSETS['N']:
                        nr,nc=r+dr,c+dc
                        if not self.in_bounds(nr,nc): continue
                        tgt=self.board[nr][nc]
                        if tgt is None or tgt[0]!=color: moves.append(Move((r,c),(nr,nc)))
                elif k in 'BRQ':
                    dirs=PIECE_OFFSETS['B'] if k=='B' else PIECE_OFFSETS['R'] if k=='R' else PIECE_OFFSETS['Q']
                    for dr,dc in dirs:
                        nr,nc=r+dr,c+dc
                        while self.in_bounds(nr,nc):
                            tgt=self.board[nr][nc]
                            if tgt is None: moves.append(Move((r,c),(nr,nc)))
                            else:
                                if tgt[0]!=color: moves.append(Move((r,c),(nr,nc)))
                                break
                            nr+=dr; nc+=dc
                else:
                    for dr,dc in PIECE_OFFSETS['K']:
                        nr,nc=r+dr,c+dc
                        if not self.in_bounds(nr,nc): continue
                        tgt=self.board[nr][nc]
                        if tgt is None or tgt[0]!=color: moves.append(Move((r,c),(nr,nc)))
        return moves
    def is_square_attacked(self, square, by_color):
        rK,cK=square
        for dr,dc in PIECE_OFFSETS['N']:
            nr,nc=rK+dr,cK+dc
            if self.in_bounds(nr,nc) and self.board[nr][nc]==by_color+'N': return True
        for dr,dc in PIECE_OFFSETS['B']:
            nr,nc=rK+dr,cK+dc
            while self.in_bounds(nr,nc):
                pc=self.board[nr][nc]
                if pc:
                    if pc[0]==by_color and pc[1] in 'BQ': return True
                    break
                nr+=dr; nc+=dc
        for dr,dc in PIECE_OFFSETS['R']:
            nr,nc=rK+dr,cK+dc
            while self.in_bounds(nr,nc):
                pc=self.board[nr][nc]
                if pc:
                    if pc[0]==by_color and pc[1] in 'RQ': return True
                    break
                nr+=dr; nc+=dc
        for dr,dc in PIECE_OFFSETS['K']:
            nr,nc=rK+dr,cK+dc
            if self.in_bounds(nr,nc) and self.board[nr][nc]==by_color+'K': return True
        d=1 if by_color==WHITE else -1
        for dc in (-1,1):
            nr,nc=rK+d,cK+dc
            if self.in_bounds(nr,nc) and self.board[nr][nc]==by_color+'P': return True
        return False
    def make(self, move):
        (r1,c1),(r2,c2),promo=move
        pc=self.board[r1][c1]; self.board[r1][c1]=None; self.board[r2][c2]=pc
        if promo: self.board[r2][c2]=pc[0]+promo
        self.turn=self.enemy(self.turn)
    def legal_moves(self):
        legal=[]
        for mv in self.generate_pseudo_legal():
            b2=self.clone(); b2.make(mv)
            kpos=b2.kings_pos(b2.enemy(b2.turn))
            if kpos and not b2.is_square_attacked(kpos, b2.turn): legal.append(mv)
        return legal
    def is_check(self, color):
        kpos=self.kings_pos(color)
        return self.is_square_attacked(kpos, self.enemy(color)) if kpos else False
    def outcome(self):
        moves=self.legal_moves()
        if moves: return None
        if self.is_check(self.turn): return ('checkmate', self.enemy(self.turn))
        return ('stalemate', None)
