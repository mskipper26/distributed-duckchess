# quickstart.py

import ndcctools.taskvine as vine
import pyffish
import time
import random
import sys

def evaluate_fen_worker(variant, fen_to_evaluate, engine_path, depth):
    """
    The Worker: Now only takes a FEN. 
    It evaluates the position 'as is' and returns the score for the side to move.
    """
    import subprocess
    import re
    import traceback
    import sys

    process = None
    try:
        process = subprocess.Popen(
            engine_path,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
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

def run_tasks(num_workers):
    # Create a new manager
    m = vine.Manager(name=f"duckchess-{int(time.time())}")
    m.enable_monitoring()
    print(f"Listening on port {m.port}")

    workers = vine.Factory("condor", m)
    workers.max_workers = num_workers
    workers.cores = 1
    workers.memory = 1000
    workers.disk = 1000

    f = m.declare_file("./stockfish")

    variant = "duck"
    current_fen = pyffish.start_fen(variant)

    for i in range(20):
        moves = pyffish.legal_moves(variant, current_fen, [])
        if not moves: 
            break
        current_fen = pyffish.get_fen(variant, current_fen, [random.choice(moves)]) 

    moves = pyffish.legal_moves(variant, current_fen, [])
    n = len(moves)
    submit_time = time.time()
    # Submit several tasks for execution:
    with workers:
        print("submitting tasks...")
        for move in moves:
            resulting_fen = pyffish.get_fen(variant, current_fen, [move])
            task = vine.PythonTask(evaluate_fen_worker, variant, resulting_fen, "./stockfish", 4)
            task.add_input(f, "./stockfish")
            task.set_cores(1)
            m.submit(task)
    
        wait_time = time.time()
        first_time = None

        # As they complete, display the results:
        print("waiting for tasks to complete...")
        while not m.empty():
            task = m.wait(5)
            if task:
                if first_time is None:
                    first_time = time.time()
                # print("task {} completed with result {}".format(task.id, task.output))
        done_time = time.time()
        print("{} workers: {} tasks completed".format(num_workers, n))
    
        total = done_time - submit_time
        rate = n / (total * 1.0)
        print(f"\tTotal time: {total:.3f} seconds ({rate:.3f} tasks/sec)")

        total = done_time - wait_time
        rate = n / (total * 1.0)
        print(f"\tTime excluding submission: {total:.3f} seconds ({rate:.3f} tasks/sec)")

        total = done_time - first_time
        rate = n / (total * 1.0)
        print(f"\tTime after first result: {total:.3f} seconds ({rate:.3f} tasks/sec)")

    print("all done.")

if __name__ == "__main__":
    num_workers = int(sys.argv[1])
    random.seed(42)

    run_tasks(num_workers)
