import sys
import chess
import chess.svg
from PyQt6.QtWidgets import QApplication, QMainWindow, QGraphicsScene, QGraphicsView, QGraphicsPixmapItem
from PyQt6.QtGui import QPixmap, QColor, QPainter
from PyQt6.QtCore import Qt, QSize, QRectF, QThread, pyqtSignal
from PyQt6.QtSvg import QSvgRenderer
import os

import pyffish
from tqdm import tqdm
import re
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed

import traceback
import multiprocessing

os.environ["QT_QPA_PLATFORM"] = "xcb"

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

        send("quit")
        return score
    except Exception as e:
        print(f"Engine Error: {repr(e)}")
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

class EngineWorker(QThread):
    move_calculated = pyqtSignal(str)

    def __init__(self, engine_path, fen, num_workers=7, depth=4):
        super().__init__()
        self.engine_path = engine_path
        self.fen = fen
        self.num_workers = num_workers
        self.depth = depth

    def run(self):
        try:
            best_move = run_duckchess(
                engine_path=self.engine_path, 
                num_workers=self.num_workers, 
                depth=self.depth, 
                startpos=self.fen
            )
            self.move_calculated.emit(best_move)
        except Exception as e:
            traceback.print_exc()
            self.move_calculated.emit("")

class DuckGUI(QMainWindow):
    def __init__(self):
        """Sets everything up"""
        super().__init__()
        self.setWindowTitle("ND CRC Duck Chess")
        self.board = chess.Board()
        self.pyffish_fen = pyffish.start_fen("duck")
        self.selected_square = None
        self.move_piece_part = None 
        self.duck_square = None

        self.is_computer = {chess.WHITE: False, chess.BLACK: True}
        self.engine_path = "./fairy-stockfish-all_x86-64"
        self.flip_board = False
        self.game_over = False

        self.scene = QGraphicsScene(0, 0, 600, 600)
        self.view = QGraphicsView(self.scene, self)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setCentralWidget(self.view)
        
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self.base_duck_pixmap = QPixmap("duck.png")
        self.duck_item = QGraphicsPixmapItem()
        self.duck_item.setZValue(1)
        self.duck_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.scene.addItem(self.duck_item)
        
        self.board_renderer = QSvgRenderer()
        self.view.drawBackground = self.draw_background
        self.render_all()

    def draw_background(self, painter, rect):
        """Draws the chessboard SVG."""
        if self.board_renderer.isValid():
            target_rect = QRectF(0, 0, 600, 600)
            painter.fillRect(rect, Qt.GlobalColor.white)
            self.board_renderer.render(painter, target_rect)

    def render_all(self):
        """Renders the board"""
        if self.move_piece_part is not None:
            active_color = not self.board.turn
        else:
            active_color = self.board.turn

        self.flip_board = (active_color == chess.BLACK and not self.is_computer[chess.BLACK])

        legal_targets = []
        if self.move_piece_part is None:
            if self.selected_square is not None:
                for move in self.board.generate_pseudo_legal_moves():
                    if move.from_square == self.selected_square and self.is_duck_legal(move):
                        legal_targets.append(move.to_square)

        fill_colors = {}
        if self.selected_square:
            fill_colors[self.selected_square] = "#cc0000cc"
            
        if self.game_over:
            last_move = self.board.peek() if self.board.move_stack else None
            if last_move:
                fill_colors[last_move.to_square] = "#ffd700cc"

        board_svg = chess.svg.board(
            self.board,
            flipped=self.flip_board,
            fill=fill_colors,
            squares=chess.SquareSet(legal_targets),
            size=600
        ).encode("utf-8")
        
        self.board_renderer.load(board_svg)
        self.view.viewport().repaint()

        if self.duck_square is None:
            self.duck_item.hide()
        else:
            self.duck_item.show()
            
            col = chess.square_file(self.duck_square)
            row = chess.square_rank(self.duck_square)
            
            if self.flip_board:
                col = 7 - col
                row = row
                display_row = row 
            else:
                display_row = 7 - row
            
            total_size = 600
            margin = total_size * 0.035
            sq_size = (total_size - (2 * margin)) / 8
            
            duck_px_size = int(sq_size * 0.95)
            scaled_duck = self.base_duck_pixmap.scaled(
                duck_px_size, duck_px_size, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            self.duck_item.setPixmap(scaled_duck)

            col = chess.square_file(self.duck_square)
            row = chess.square_rank(self.duck_square)
            
            if self.flip_board:
                display_col = 7 - col
                display_row = row
            else:
                display_col = col
                display_row = 7 - row

            pixel_x = margin + (display_col * sq_size) + (sq_size - duck_px_size) / 2
            pixel_y = margin + (display_row * sq_size) + (sq_size - duck_px_size) / 2 + 5
            
            self.duck_item.setPos(pixel_x, pixel_y)

    def mousePressEvent(self, event):
        """Determines which square was clicked"""
        scene_pos = self.view.mapToScene(event.pos())
        
        total_size = 600
        margin = total_size * 0.035
        inner_size = total_size - (2 * margin)
        sq_size = inner_size / 8

        local_x = scene_pos.x() - margin
        local_y = scene_pos.y() - margin

        raw_col = int(local_x // sq_size)
        raw_row = int(7 - (local_y // sq_size))

        if self.flip_board:
            col = 7 - raw_col
            row = 7 - raw_row
        else:
            col = raw_col
            row = raw_row

        self.handle_click(chess.square(col, row))

    def handle_click(self, square):
        """Determines outcome of click"""
        if self.game_over:
            print("The game is already over!")
            return

        # Determine who is actually interacting right now. 
        # If move_piece_part has text, the person who just moved is placing the duck.
        if self.move_piece_part is not None:
            active_color = not self.board.turn
        else:
            active_color = self.board.turn

        # Check if the currently active color belongs to the computer
        if self.is_computer[active_color]:
            print("Wait for computer...")
            return

        if self.move_piece_part is None:
            if self.selected_square is None:
                if self.board.piece_at(square) and self.board.color_at(square) == self.board.turn:
                    self.selected_square = square
            else:
                move = chess.Move(self.selected_square, square)
                if self.is_duck_legal(move):

                    if self.board.piece_at(self.selected_square).piece_type == chess.PAWN:
                        if chess.square_rank(square) in [0, 7]:
                            move.promotion = chess.QUEEN
                            
                    self.board.push(move)
                    self.move_piece_part = chess.square_name(self.selected_square) + chess.square_name(square)
                    self.piece_dest = chess.square_name(square)

                    if not self.check_kings_alive():
                        self.render_all()
                        return
                    print("Move the duck!")
                
                self.selected_square = None

        else:
            if self.board.piece_at(square) is None and square != self.duck_square:
                self.duck_square = square
                move = f"{self.move_piece_part}@{chess.square_name(square)}"
                print(f"Move complete: {move}")
                pyffish_move = f"{self.move_piece_part},{self.piece_dest}{chess.square_name(square)}"
                self.pyffish_fen = pyffish.get_fen("duck", self.pyffish_fen, [pyffish_move])
                self.move_piece_part = None

                if self.is_fowled():
                    print(f"FOWLED! {('Black' if self.board.turn == chess.WHITE else 'White')} wins!")
                    self.game_over = True

            # Trigger engine ONLY after the duck is placed
            if self.move_piece_part is None and self.is_computer[self.board.turn]:
                self.trigger_engine_eval()

        self.render_all()

    def is_duck_legal(self, move):
        """Checks if a move is blocked by the duck."""
        if move not in self.board.generate_pseudo_legal_moves():
            return False
            
        if move.to_square == self.duck_square:
            return False
    
        piece = self.board.piece_at(move.from_square)
        if piece and piece.piece_type != chess.KNIGHT:
            path = self.get_path(move.from_square, move.to_square)
            if self.duck_square in path:
                return False
                
        return True

    def get_path(self, start, end):
        """Returns a list of squares between start and end (exclusive)."""
        diff_file = chess.square_file(end) - chess.square_file(start)
        diff_rank = chess.square_rank(end) - chess.square_rank(start)
        
        step_f = 0 if diff_file == 0 else (1 if diff_file > 0 else -1)
        step_r = 0 if diff_rank == 0 else (1 if diff_rank > 0 else -1)
        
        path = []
        curr_f, curr_r = chess.square_file(start) + step_f, chess.square_rank(start) + step_r
        while (curr_f, curr_r) != (chess.square_file(end), chess.square_rank(end)):
            path.append(chess.square(curr_f, curr_r))
            curr_f += step_f
            curr_r += step_r
        return path

    def is_fowled(self):
        """Checks if the player to move has absolutely no legal moves."""
        for move in self.board.generate_pseudo_legal_moves():
            if self.is_duck_legal(move):
                return False
        return True

    def check_kings_alive(self):
            """Returns True if both kings are on the board, False otherwise."""
            white_king = self.board.king(chess.WHITE)
            black_king = self.board.king(chess.BLACK)
            
            if white_king is None:
                print("BLACK WINS! White King captured.")
                self.game_over = True
                return False
            if black_king is None:
                print("WHITE WINS! Black King captured.")
                self.game_over = True
                return False
                
            return True

    def apply_engine_move(self, engine_move_str):
        if not engine_move_str:
            print("Error: Engine returned no move.")
            return

        print(f"Computer plays: {engine_move_str}")

        # Split the piece move from the duck placement (e.g., "e7e5@d4")
        parts = engine_move_str.split('@')
        piece_move_str = parts[0]
        new_duck_str = parts[1] if len(parts) > 1 else None

        # 1. Apply the piece move
        move = chess.Move.from_uci(piece_move_str)
        piece_dest = chess.square_name(move.to_square)
        self.board.push(move)

        # 2. Apply the duck move
        if new_duck_str:
            self.duck_square = chess.parse_square(new_duck_str)

        pyffish_move = f"{piece_move_str},{piece_dest}{chess.square_name(self.duck_square)}"
        self.pyffish_fen = pyffish.get_fen("duck", self.pyffish_fen, [pyffish_move])

        # 3. Check for game-ending conditions
        if not self.check_kings_alive():
            self.render_all()
            return
            
        if self.is_fowled():
            print(f"FOWLED! {('Black' if self.board.turn == chess.WHITE else 'White')} wins!")
            self.game_over = True

        # 4. Update the visual board
        self.render_all()

    def trigger_engine_eval(self):
        print("Computer is thinking...")
        
        print(f"Sending FEN to workers: {self.pyffish_fen}")

        # Fire off the worker
        self.engine_thread = EngineWorker(self.engine_path, self.pyffish_fen)
        self.engine_thread.move_calculated.connect(self.apply_engine_move)
        self.engine_thread.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    multiprocessing.set_start_method('spawn', force=True)
    gui = DuckGUI()
    gui.show()
    sys.exit(app.exec())