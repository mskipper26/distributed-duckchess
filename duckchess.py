import pyffish
from tqdm import tqdm
import re
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
import sys

def evaluate_position(variant, fen, engine_path, move_name):
    """The engine subprocess worker"""
    # Start the process
    # We use engine_path as the variable to avoid shadowing the process object
    process = subprocess.Popen(
        engine_path,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1  # Line buffered
    )

    def send(cmd):
        process.stdin.write(f"{cmd}\n")
        process.stdin.flush() # CRITICAL: Ensure engine sees the command

    # 1. UCI Setup
    send("uci")
    send("setoption name UCI_Variant value duck")
    send("isready")
    
    while True:
        line = process.stdout.readline()
        if "readyok" in line.strip():
            break

    # 2. Evaluation
    send(f"position fen {fen}")
    send("go depth 4")

    score = 0
    while True:
        line = process.stdout.readline()
        if not line: break # Process died
        
        if "score cp" in line:
            match = re.search(r'score cp (-?\d+)', line)
            if match:
                score = int(match.group(1))
        
        if "bestmove" in line:
            break

    # 3. Clean up
    send("quit")
    try:
        process.wait(timeout=1)
    except:
        process.terminate()
        
    # Fixed: Returning the score (move_name is handled by the future dictionary in main)
    return score

def run_duckchess(engine_path):
    print("Generating moves via pyffish...")
    variant = "duck"
    start_fen = pyffish.start_fen(variant)
    moves = pyffish.legal_moves(variant, start_fen, [])
    
    # Pre-calculate FENs
    tasks = []
    for move in moves:
        new_fen = pyffish.get_fen(variant, start_fen, [move])
        tasks.append((move, new_fen))
    
    print(f"Evaluating {len(tasks)} positions...")

    results = []
    # Using 7 workers as requested
    with ProcessPoolExecutor(max_workers=7) as executor:
        # Pass move_name into the function so it doesn't get lost
        future_to_move = {
            executor.submit(evaluate_position, variant, fen, engine_path, move): move 
            for move, fen in tasks
        }

        for f in tqdm(as_completed(future_to_move), total=len(tasks), desc="Searching"):
            move_name = future_to_move[f]
            try:
                score = f.result()
                # Note: Score is from Black's perspective because White just moved.
                # We multiply by -1 to show the score for White.
                results.append((move_name, -score))
            except Exception as e:
                print(f"\nError evaluating {move_name}: {e}")

    results.sort(key=lambda x: x[1], reverse=True)
    
    print("\n--- Top 10 Moves for White ---")
    for move, score in results[:10]:
        print(f"Move: {move:<15} | Score: {score}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test3.py [path-to-executable]")
        sys.exit(1)

    engine_binary = sys.argv[1]
    run_duckchess(engine_binary)