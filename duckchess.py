import pyffish
import chess
import chess.engine

def evaluate_move(variant, fen, move_uci):
    # Start the Fairy Stockfish binary
    # Ensure you have the 'fairy-stockfish' executable in your path
    engine = chess.engine.SimpleEngine.popen_uci("./fairy-stockfish")
    
    # Configure for Duck Chess
    engine.configure({"UCI_Variant": variant})
    
    board = chess.Board(fen, chess960=False) # Use variant-specific board if available
    # Or simply:
    # engine.send_command(f"position fen {fen} moves {move_uci}")
    
    # Get evaluation
    info = engine.analyse(board, chess.engine.Limit(depth=8))
    score = info["score"].relative.score(mate_score=10000)
    
    engine.quit()
    return score


# print(dir(pyffish))
# exit()

for variant in pyffish.variants():
    if variant == "duck":
        print(f"FOUND: {variant}")

start = pyffish.start_fen("duck")
# print(start)
# print(type(start)) # --> str

# print(len(pyffish.legal_moves("duck", start, []))) --> 640
# print(len(pyffish.legal_moves("chess", pyffish.start_fen("chess"), []))) --> 20

variant = "duck"
curr_fen = pyffish.start_fen(variant)
num_moves = 0
while True:
    moves = pyffish.legal_moves(variant, curr_fen, [])
    
    if not moves:
        print("Game Over: No more legal moves.")
        result = pyffish.game_result(variant, curr_fen, [])
        print(f"Result: {result}")
        break

    # take the first move every time, to test
    if len(moves) > 3:
        chosen_move = moves[3]
    elif len(moves) > 2:
        chosen_move = moves[2]
    elif len(moves) > 1:
        chosen_move = moves[1]
    else:
        chosen_move = moves[0]
    
    # show current board state as fen
    curr_fen = pyffish.get_fen(variant, curr_fen, [chosen_move])
    print(f"Move {num_moves}: {chosen_move}")
    print(f"Board: {curr_fen}")
    score = evaluate_move(variant, curr_fen, None)
    num_moves += 1
