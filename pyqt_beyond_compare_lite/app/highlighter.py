# -*- coding: utf-8 -*-
"""Line highlighter for text diff editors."""
from __future__ import annotations

from typing import Dict, Optional

from PyQt5.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat


class DiffHighlighter(QSyntaxHighlighter):
    """Highlight entire lines according to a 0-based line status map."""

    def __init__(self, document, line_status: Optional[Dict[int, str]] = None):
        super().__init__(document)
        self.line_status: Dict[int, str] = line_status or {}
        self.formats = {
            "replace": self._make_format(QColor(255, 245, 157)),
            "delete": self._make_format(QColor(255, 205, 210)),
            "insert": self._make_format(QColor(200, 230, 201)),
        }

    @staticmethod
    def _make_format(color: QColor) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setBackground(color)
        return fmt

    def set_line_status(self, line_status: Dict[int, str]) -> None:
        self.line_status = line_status
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt API naming
        line_no = self.currentBlock().blockNumber()
        status = self.line_status.get(line_no)
        if status in self.formats:
            self.setFormat(0, max(1, len(text)), self.formats[status])
