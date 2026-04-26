import chess

def is_duck_legal(board, move, duck_square):
    """Checks if a move is blocked by the duck."""
    if move not in board.generate_pseudo_legal_moves():
        return False

    if duck_square is None:
            return True
        
    if move.to_square == duck_square:
        return False

    piece = board.piece_at(move.from_square)
    if piece and piece.piece_type != chess.KNIGHT:
        path = get_path(move.from_square, move.to_square)
        if duck_square in path:
            return False
            
    return True

def get_path(start, end):
    """Returns a list of squares between start and end (exclusive)."""
    diff_file = chess.square_file(end) - chess.square_file(start)
    diff_rank = chess.square_rank(end) - chess.square_rank(start)
    
    step_f = 0 if diff_file == 0 else (1 if diff_file > 0 else -1)
    step_r = 0 if diff_rank == 0 else (1 if diff_rank > 0 else -1)
    
    path = []
    curr_f, curr_r = chess.square_file(start) + step_f, chess.square_rank(start) + step_r

    max_steps = 8
    steps = 0
    while (curr_f, curr_r) != (chess.square_file(end), chess.square_rank(end)) and steps < max_steps:
        path.append(chess.square(curr_f, curr_r))
        curr_f += step_f
        curr_r += step_r
        steps += 1
    return path

def is_fowled(board, duck_square):
    """Checks if the player to move has absolutely no legal moves."""
    for move in board.generate_pseudo_legal_moves():
        if is_duck_legal(board, move, duck_square):
            return False
    return True

def check_kings_alive(board):
        """Returns True if both kings are on the board, False otherwise."""
        white_king = board.king(chess.WHITE)
        black_king = board.king(chess.BLACK)
        
        if white_king is None:
            print("BLACK WINS! White King captured.")
            return False
        if black_king is None:
            print("WHITE WINS! Black King captured.")
            return False
            
        return True