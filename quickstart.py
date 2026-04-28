# quickstart.py

import ndcctools.taskvine as vine
import pyffish

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

# Create a new manager
m = vine.Manager([9123, 9129])
print(f"Listening on port {m.port}")

f = m.declare_file("./stockfish")

variant = "duck"
current_fen = pyffish.start_fen(variant)
moves = pyffish.legal_moves(variant, current_fen, [])

# Submit several tasks for execution:
print("submitting tasks...")
n = len(moves)
for move in moves:
    resulting_fen = pyffish.get_fen(variant, current_fen, [move])
    task = vine.PythonTask(evaluate_fen_worker, variant, resulting_fen, "./stockfish", 4)
    task.add_input(f, "./stockfish")
    task.set_cores(1)
    m.submit(task)

# As they complete, display the results:
print("waiting for tasks to complete...")
while not m.empty():
    task = m.wait(5)
    if task:
        print("task {} completed with result {}".format(task.id, task.output))

print("all done.")