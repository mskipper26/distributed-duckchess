import subprocess
import re
import pyffish
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed

def evaluate_fen_worker(variant, fen_to_evaluate, engine_path, depth):
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
        send(f"go depth {depth}")

        score = 0
        while True:
            line = process.stdout.readline()
            if not line: break 
            if "score cp" in line:
                match = re.search(r'score cp (-?\d+)', line)
                if match:
                    score = int(match.group(1))

            elif "score mate" in line:
                match = re.search(r'score mate (-?\d+)', line)
                if match:
                    mate_in = int(match.group(1))
                    if mate_in > 0:
                        score = 100000 - mate_in
                    elif mate_in < 0:
                        score = -100000 - mate_in

            if "bestmove" in line:
                break

        if process.poll() is not None:
             raise Exception(f"Engine exited unexpectedly with code {process.returncode}")

        send("quit")
        return score
    except Exception:
        print("Exception")
        traceback.print_exc(file=sys.stderr)
        return 0
    finally:
        if process:
            process.terminate()

def run_duckchess(engine_path, num_workers, depth, startpos=None):
    variant = "duck"
    current_fen = pyffish.start_fen(variant) if startpos is None else startpos

    print(f"Starting Search from FEN: {current_fen}\n")
    
    # 2. Pre-calculate all resulting FENs locally
    possible_moves = pyffish.legal_moves(variant, current_fen, [])
    
    # Create a list of (MoveName, ResultingFEN)
    # This keeps the 'Worker' from having to do any rule-processing
    tasks = []
    immediate_wins = []
    for move in possible_moves:
        resulting_fen = pyffish.get_fen(variant, current_fen, [move])

        active_color_white = " w " in current_fen
        if active_color_white and 'k' not in resulting_fen:
            # White just captured the Black King!
            immediate_wins.append((move, 999999))
        elif not active_color_white and 'K' not in resulting_fen:
            # Black just captured the White King!
            immediate_wins.append((move, 999999))
        else:
            # Both kings are alive, evaluate normally
            tasks.append((move, resulting_fen))

    if immediate_wins:
        print("Winning move detected! Skipping engine evaluation.")
        results = immediate_wins
    else:

        # 3. Parallel Evaluation of FENs
        results = []
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            # Pass only the variant, the specific FEN, and the engine path
            future_to_move = {
                executor.submit(evaluate_fen_worker, variant, fen, engine_path, depth): move 
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
    if not results:
        print("Engine found no legal moves! (Checkmate/Stalemate or Invalid FEN)")
        return ""
        
    results.sort(key=lambda x: x[1], reverse=True)

    best_move_raw = results[0][0]

    # Convert Fairy-Stockfish format (e.g., "d7d5,d5g5") to GUI format (e.g., "d7d5@g5")
    if ',' in best_move_raw:
        parts = best_move_raw.split(',')
        piece_move = parts[0]
        duck_square = parts[1][-2:] # The last two characters are the duck's destination
        best_move_formatted = f"{piece_move}@{duck_square}"
    else:
        # Fallback if there's no comma for some reason
        best_move_formatted = best_move_raw

    return best_move_formatted