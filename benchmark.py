import subprocess
import time
import random
import statistics
import pyffish

# --- CONFIGURATION ---
ENGINE_PATH = "./fairy-stockfish-all_x86-64"
DEPTH = 15
ITERATIONS = 30
MOVES_TO_PLAY = 20


def time_engine(variant, fen, depth):
    process = None
    try:
        process = subprocess.Popen(
            ENGINE_PATH,
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

        send(f"position fen {fen}")

        start = time.perf_counter()
        send(f"go depth {depth}")

        while True:
            line = process.stdout.readline()
            if not line:
                break
            if "bestmove" in line:
                break

        elapsed = time.perf_counter() - start

        send("quit")
        return elapsed

    except Exception as e:
        print(f"Engine error: {e}")
        return 0.0
    finally:
        if process:
            process.terminate()


def run_benchmark():
    duck_times, std_times = [], []
    duck_move_counts, std_move_counts = [], []

    print(f"--- Benchmarking Fairy Stockfish (Depth {DEPTH}) ---")

    i = 0
    while i < ITERATIONS:
        duck_variant = "duck"
        std_variant = "chess"

        current_duck_fen = pyffish.start_fen(duck_variant)
        current_std_fen = pyffish.start_fen(std_variant)

        valid_path = True
        for _ in range(MOVES_TO_PLAY):
            d_moves = pyffish.legal_moves(duck_variant, current_duck_fen, [])
            s_moves = pyffish.legal_moves(std_variant, current_std_fen, [])

            standard_piece_moves = set(s_moves)
            compatible_duck_moves = [m for m in d_moves if m.split(',')[0] in standard_piece_moves]

            if not compatible_duck_moves:
                valid_path = False
                break

            mv = random.choice(compatible_duck_moves)
            piece_mv = mv.split(',')[0]

            current_duck_fen = pyffish.get_fen(duck_variant, current_duck_fen, [mv])
            current_std_fen = pyffish.get_fen(std_variant, current_std_fen, [piece_mv])

        if not valid_path:
            continue

        d_count = len(pyffish.legal_moves(duck_variant, current_duck_fen, []))
        s_count = len(pyffish.legal_moves(std_variant, current_std_fen, []))

        duck_move_counts.append(d_count)
        std_move_counts.append(s_count)

        print(f"Iteration {i+1}: Moves(Std:{s_count}, Duck:{d_count})")

        t_std = time_engine(std_variant, current_std_fen, DEPTH)
        std_times.append(t_std)

        t_duck = time_engine(duck_variant, current_duck_fen, DEPTH)
        duck_times.append(t_duck)

        print(f"  Time -> Std: {t_std:.4f}s | Duck: {t_duck:.4f}s")
        i += 1

    # --- STATS ---
    print("\n" + "="*50)
    print(f"FINAL RESULTS (Depth {DEPTH})")
    print("="*50)
    print(f"AVG BRANCHING FACTOR:")
    print(f"  Standard: {statistics.mean(std_move_counts):.2f}")
    print(f"  Duck:     {statistics.mean(duck_move_counts):.2f}")
    print(f"AVG RUNTIME:")
    print(f"  Standard: {statistics.mean(std_times):.4f}s")
    print(f"  Duck:     {statistics.mean(duck_times):.4f}s")
    print(f"SLOWDOWN FACTOR: {statistics.mean(duck_times) / statistics.mean(std_times):.2f}x")
    print("="*50)


if __name__ == "__main__":
    run_benchmark()