import time
import ndcctools.taskvine as vine
import pyffish
from engine import evaluate_fen_worker
from compare_engines import vanilla_best_move, distributed_best_move

# --- CONFIGURATION ---
ENGINE_PATH = "./stockfish"
VARIANT     = "duck"
DEPTH       = 10
NUM_WORKERS = 100

def play_engine_game():
    m = vine.Manager(name=f"duckchess-{int(time.time())}", port=0)
    print(f"Manager listening on port {m.port}")
    
    f_engine = m.declare_file(ENGINE_PATH)
    f_module = m.declare_file("engine.py")

    workers = vine.Factory("condor", m)
    workers.max_workers = NUM_WORKERS
    workers.cores = 1
    workers.memory = 1000
    workers.disk = 1000
    
    current_fen = pyffish.start_fen(VARIANT)
    move_history = []
    game_over = False
    turn_count = 1

    print(f"\n{'='*20} GAME START {'='*20}")
    print(f"White: Distributed (Depth {DEPTH}) | Black: Vanilla (Depth {DEPTH})")
    
    with workers:
        while not game_over:
            active_color = "White" if " w " in current_fen else "Black"
            print(f"\n--- Turn {turn_count} ({active_color}) ---")
            print(f"FEN: {current_fen}")

            start_time = time.time()
            
            if active_color == "White":
                # --- DISTRIBUTED ENGINE TURN ---
                results = distributed_best_move(VARIANT, current_fen, DEPTH m, f_engine, f_module)
                if not results:
                    print("Distributed engine failed to return moves!")
                    break
                best_move, score = results[0]
            else:
                # --- VANILLA ENGINE TURN ---
                best_move, score = vanilla_best_move(VARIANT, current_fen, ENGINE_PATH, DEPTH)
            
            elapsed = time.time() - start_time
            
            if not best_move:
                print(f"{active_color} resigned or crashed.")
                break

            # Apply move to FEN
            next_fen = pyffish.get_fen(VARIANT, current_fen, [best_move])
            
            opponent_king = 'k' if active_color == "White" else 'K'
            if opponent_king not in next_fen:
                print(f"\n{'*'*10} {active_color.upper()} WINS! {'*'*10}")
                print(f"Final Move: {best_move} (King Captured)")
                game_over = True
            
            print(f"Move: {best_move} | Score: {score} | Time: {elapsed:.2f}s")
            
            current_fen = next_fen
            move_history.append(best_move)
            
            if active_color == "Black":
                turn_count += 1
            
            if turn_count > 150:
                print("Game drawn by turn limit.")
                break

    print("\n" + "="*40)
    print("GAME SUMMARY")
    print(f"Total Moves: {len(move_history)}")
    print(f"PGN-ish: {' '.join(move_history)}")
    print("="*40)

if __name__ == "__main__":
    play_engine_game()