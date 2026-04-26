import sys
import multiprocessing
import traceback
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread, pyqtSignal

from engine import run_duckchess
from gui import DuckGUI

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
    
if __name__ == "__main__":
    multiprocessing.set_start_method('spawn', force=True)
    app = QApplication(sys.argv)
    gui = DuckGUI()
    gui.show()
    sys.exit(app.exec())