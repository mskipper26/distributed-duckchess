import re
import time
import random
import statistics
import subprocess
import ndcctools.taskvine as vine
from tqdm import tqdm

import pyffish
from engine import evaluate_fen_worker

# --- CONFIGURATION ---
ENGINE_PATH     = "./fairy-stockfish-all_x86-64"
VARIANT         = "duck"
DEPTH           = 10
NUM_WORKERS     = 10
POSITIONS       = 20
RANDOM_PLIES    = 20
SEED            = 42

def vanilla_best_move(variant, fen, engine_path, depth):
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

        send(f"position fen {fen}")
        send(f"go depth {depth}")

        score = 0
        best_move = None
        while True:
            line = process.stdout.readline()
            if not line:
                break
            if "score cp" in line:
                m = re.search(r'score cp (-?\d+)', line)
                if m:
                    score = int(m.group(1))
            elif "score mate" in line:
                m = re.search(r'score mate (-?\d+)', line)
                if m:
                    mate_in = int(m.group(1))
                    score = 100000 - mate_in if mate_in > 0 else -100000 - mate_in
            if "bestmove" in line:
                m = re.search(r'bestmove (\S+)', line)
                if m:
                    best_move = m.group(1)
                break

        send("quit")
        return best_move, score

    except Exception as e:
        print(f"  [vanilla] engine error: {e}")
        return None, 0
    finally:
        if process:
            process.terminate()


def distributed_best_move(variant, fen, engine_path, depth):
    possible_moves = pyffish.legal_moves(variant, fen, [])

    tasks = []
    immediate_wins = []
    active_color_white = " w " in fen

    for move in possible_moves:
        resulting_fen = pyffish.get_fen(variant, fen, [move])
        if active_color_white and 'k' not in resulting_fen:
            immediate_wins.append((move, 999999))
        elif not active_color_white and 'K' not in resulting_fen:
            immediate_wins.append((move, 999999))
        else:
            tasks.append((move, resulting_fen))

    if immediate_wins:
        return immediate_wins

    results = []

    for move, fen in tasks:
        task = vine.PythonTask(evaluate_fen_worker, variant, fen, "./stockfish", 4)
        task.add_input(f, "./stockfish")
        task.set_cores(1)
        task.id = move
        m.submit(task)

    while not m.empty():
        task = m.wait(5)
        if task:
            score = task.output
            move = task.id
            results.append((move, -score))

    results.sort(key=lambda x: x[1], reverse=True)
    return results

def generate_positions(n, plies, seed):
    positions = []
    for i in range(n):
        random.seed(seed + i)
        fen = pyffish.start_fen(VARIANT)
        for _ in range(plies):
            moves = pyffish.legal_moves(VARIANT, fen, [])
            if not moves:
                break
            fen = pyffish.get_fen(VARIANT, fen, [random.choice(moves)])
        positions.append(fen)
    return positions


def run_benchmark():
    print(f"--- Duck Chess Move Quality Benchmark ---")
    print(f"  Depth:    {DEPTH}")
    print(f"  Workers:  {NUM_WORKERS} (distributed)")
    print(f"  Positions: {POSITIONS}")
    print()

    m = vine.Manager(name=f"duckchess-{int(time.time())}", port=0)
    m.enable_monitoring()
    print(f"Listening on port {m.port}")

    workers = vine.Factory("condor", m)
    workers.max_workers = num_workers
    workers.cores = 1
    workers.memory = 1000
    workers.disk = 1000

    f = m.declare_file("./stockfish")

    positions = generate_positions(POSITIONS, RANDOM_PLIES, SEED)

    vanilla_times     = []
    distributed_times = []
    ranks             = []
    score_gaps        = []

    with workers:
        for idx, fen in enumerate(positions):
            num_moves = len(pyffish.legal_moves(VARIANT, fen, []))
            print(f"Position {idx+1}/{POSITIONS}  ({num_moves} legal moves)")
            print(f"  FEN: {fen}")

            t0 = time.perf_counter()
            v_move, v_score = vanilla_best_move(VARIANT, fen, ENGINE_PATH, DEPTH)
            v_time = time.perf_counter() - t0
            vanilla_times.append(v_time)
            print(f"  Vanilla:  move={v_move:<15}  score={v_score:>7}  time={v_time:.3f}s")

            t0 = time.perf_counter()
            ranked = distributed_best_move(VARIANT, fen, ENGINE_PATH, DEPTH, NUM_WORKERS)
            d_time = time.perf_counter() - t0
            distributed_times.append(d_time)

            d_move, d_score = ranked[0]
            print(f"  Best:     move={d_move:<15}  score={d_score:>7}  time={d_time:.3f}s")

            ranked_moves = [m for m, _ in ranked]
            scores_dict  = {m: s for m, s in ranked}

            if v_move in ranked_moves:
                rank = ranked_moves.index(v_move) + 1
                v_distributed_score = scores_dict[v_move]
                gap = d_score - v_distributed_score
            else:
                rank = len(ranked) + 1
                gap = 0
                print(f"  WARNING: vanilla move {v_move} not found in distributed results")

            ranks.append(rank)
            score_gaps.append(gap)

            indicator = "optimal" if rank == 1 else f"rank {rank}/{len(ranked)}"
            print(f"  Vanilla rank: {rank}/{len(ranked)}  gap={gap:+} cp  {indicator}")
            print()

    avg_rank   = statistics.mean(ranks)
    avg_gap    = statistics.mean(score_gaps)
    median_gap = statistics.median(score_gaps)
    optimal    = sum(1 for r in ranks if r == 1)
    avg_vt     = statistics.mean(vanilla_times)
    avg_dt     = statistics.mean(distributed_times)

    print("=" * 50)
    print(f"FINAL RESULTS (Depth {DEPTH}, {POSITIONS} positions)")
    print("=" * 50)
    print(f"VANILLA MOVE RANK (in distributed evaluation):")
    print(f"  Optimal (rank 1): {optimal}/{POSITIONS} positions")
    print(f"  Avg rank:         {avg_rank:.1f}")
    print(f"  Worst rank:       {max(ranks)}")
    print(f"SCORE GAP (distributed best - vanilla's move):")
    print(f"  Mean:             {avg_gap:+.1f} cp")
    print(f"  Median:           {median_gap:+.1f} cp")
    print(f"  Worst:            {max(score_gaps):+.1f} cp")
    print(f"AVG TIME:")
    print(f"  Vanilla:          {avg_vt:.3f}s")
    print(f"  Distributed:      {avg_dt:.3f}s")
    print("=" * 50)

if __name__ == "__main__":
    run_benchmark()