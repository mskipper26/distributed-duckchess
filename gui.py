import chess
import chess.svg
import pyffish
import os
from PyQt6.QtWidgets import QMainWindow, QGraphicsScene, QGraphicsView, QGraphicsPixmapItem
from PyQt6.QtGui import QPixmap, QPainter
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtSvg import QSvgRenderer

from rules import is_duck_legal, is_fowled, check_kings_alive

os.environ["QT_QPA_PLATFORM"] = "xcb"

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
                    if move.from_square == self.selected_square:
                        if is_duck_legal(self.board, move, self.duck_square):
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
                if is_duck_legal(self.board, move, self.duck_square):

                    if self.board.piece_at(self.selected_square).piece_type == chess.PAWN:
                        if chess.square_rank(square) in [0, 7]:
                            move.promotion = chess.QUEEN
                            
                    self.board.push(move)
                    self.move_piece_part = chess.square_name(self.selected_square) + chess.square_name(square)
                    self.piece_dest = chess.square_name(square)

                    if not check_kings_alive(self.board):
                        self.game_over = True
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

                if is_fowled(self.board, self.duck_square):
                    print(f"FOWLED! {('Black' if self.board.turn == chess.WHITE else 'White')} wins!")
                    self.game_over = True

            # Trigger engine ONLY after the duck is placed
            if self.move_piece_part is None and self.is_computer[self.board.turn]:
                self.trigger_engine_eval()

        self.render_all()

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
        if not check_kings_alive(self.board):
            self.game_over = True
            self.render_all()
            return
            
        if is_fowled(self.board, self.duck_square):
            print(f"FOWLED! {('Black' if self.board.turn == chess.WHITE else 'White')} wins!")
            self.game_over = True

        # 4. Update the visual board
        self.render_all()

    def trigger_engine_eval(self):
        from main import EngineWorker
        print("Computer is thinking...")
        
        print(f"Sending FEN to workers: {self.pyffish_fen}")

        # Fire off the worker
        self.engine_thread = EngineWorker(self.engine_path, self.pyffish_fen)
        self.engine_thread.move_calculated.connect(self.apply_engine_move)
        self.engine_thread.start()