# -*- coding: utf-8 -*-
"""Background diff worker thread."""
from __future__ import annotations

from typing import List

from PyQt5.QtCore import QThread, pyqtSignal

from .diff_engine import compare_paths
from .models import DiffResult


class DiffThread(QThread):
    progress = pyqtSignal(str)
    finished_ok = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, left_path: str, right_path: str, parent=None):
        super().__init__(parent)
        self.left_path = left_path
        self.right_path = right_path

    def run(self) -> None:
        try:
            diffs: List[DiffResult] = compare_paths(
                self.left_path,
                self.right_path,
                progress=lambda text: self.progress.emit(text),
            )
            self.finished_ok.emit(diffs)
        except Exception as exc:  # keep UI alive on unexpected FS errors
            self.failed.emit(str(exc))
