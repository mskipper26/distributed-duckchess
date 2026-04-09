import pyffish
from tqdm import tqdm
import re
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
import sys
import random

def evaluate_fen_worker(variant, fen_to_evaluate, engine_path):
    """
    The Worker: Now only takes a FEN. 
    It evaluates the position 'as is' and returns the score for the side to move.
    """
    process = None
    try:
        process = subprocess.Popen(
            engine_path,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        def send(cmd):
            process.stdin.write(f"{cmd}\n")
            process.stdin.flush()

        send("uci")
        send(f"setoption name UCI_Variant value {variant}")
        send("isready")
        
        while True:
            line = process.stdout.readline()
            if "readyok" in line:
                break

        # Send the FEN only. No 'moves' list needed.
        send(f"position fen {fen_to_evaluate}")
        send("go depth 4")

        score = 0
        while True:
            line = process.stdout.readline()
            if not line: break 
            if "score cp" in line:
                match = re.search(r'score cp (-?\d+)', line)
                if match:
                    score = int(match.group(1))
            if "bestmove" in line:
                break

        send("quit")
        return score
    except Exception:
        print("Exception")
        return 0
    finally:
        if process:
            process.terminate()

def run_duckchess(engine_path):
    variant = "duck"
    current_fen = pyffish.start_fen(variant)
    random_plies = 20
    
    # 1. Play random moves locally
    print(f"--- Playing {random_plies} random moves ---")
    for i in range(random_plies):
        moves = pyffish.legal_moves(variant, current_fen, [])
        if not moves: break
        current_fen = pyffish.get_fen(variant, current_fen, [random.choice(moves)])

    print(f"Starting Search from FEN: {current_fen}\n")

    # 2. Pre-calculate all resulting FENs locally
    possible_moves = pyffish.legal_moves(variant, current_fen, [])
    
    # Create a list of (MoveName, ResultingFEN)
    # This keeps the 'Worker' from having to do any rule-processing
    tasks = []
    for move in possible_moves:
        resulting_fen = pyffish.get_fen(variant, current_fen, [move])
        tasks.append((move, resulting_fen))

    # 3. Parallel Evaluation of FENs
    results = []
    with ProcessPoolExecutor(max_workers=7) as executor:
        # Pass only the variant, the specific FEN, and the engine path
        future_to_move = {
            executor.submit(evaluate_fen_worker, variant, fen, engine_path): move 
            for move, fen in tasks
        }

        for f in tqdm(as_completed(future_to_move), total=len(tasks), desc="Evaluating FENs"):
            move_name = future_to_move[f]
            score = f.result()
            
            # Since the engine evaluates the state AFTER the move, 
            # the score is from the opponent's perspective. 
            # We negate it so higher = better for the current mover.
            results.append((move_name, -score))

    # 4. Results
    results.sort(key=lambda x: x[1], reverse=True)
    side = current_fen.split(' ')[1].upper()
    print(f"\n--- Top 10 Moves for {side} ---")
    for move, score in results[:10]:
        print(f"Move: {move:<15} | Score: {score}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script.py [path-to-large-branching-exe]")
        sys.exit(1)

    run_duckchess(sys.argv[1])