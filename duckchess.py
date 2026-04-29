import pyffish
from tqdm import tqdm
import re
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
import sys
import random
import argparse
from engine import evaluate_fen_worker

DEFAULT_WORKER_COUNT = 7
DEFAULT_SEARCH_DEPTH = 4

def run_duckchess(engine_path, num_workers, depth):
    variant = "duck"
    current_fen = pyffish.start_fen(variant)
    random_plies = 20
    # random.seed(42)
    
    # 1. Play random moves locally
    print(f"--- Playing {random_plies} random moves ---")
    for i in range(random_plies):
        moves = pyffish.legal_moves(variant, current_fen, [])
        if not moves: 
            break
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
    results.sort(key=lambda x: x[1], reverse=True)
    side = current_fen.split(' ')[1].upper()
    print(f"\n--- Top 10 Moves for {side} ---")
    for move, score in results[:10]:
        print(f"Move: {move:<15} | Score: {score}")

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        prog="duckchess",
        description="This program evaluates the FEN of a duckchess board after random moves played.",
    )
    
    parser.add_argument("engine_path")
    parser.add_argument("-n", "--num_workers", type=int, default=DEFAULT_WORKER_COUNT)
    parser.add_argument("-d", "--depth", type=int, default=DEFAULT_SEARCH_DEPTH)
    parser.add_argument("-r", "--rand_seed", type=int, nargs="?", const=None, default=42)
    args = parser.parse_args()

    # print(args.engine_path, args.num_workers, args.depth, args.rand_seed)

    if args.rand_seed is None:
        rand_seed = random.randint(0, 1000000)
    else:
        rand_seed = args.rand_seed

    random.seed(rand_seed)
    run_duckchess(args.engine_path, args.num_workers, args.depth)
