"""
screen_recorder.py
==================
基于 PyQt5 + mss + OpenCV 的桌面录屏工具

依赖安装：
    pip install PyQt5 mss opencv-python numpy

运行：
    python screen_recorder.py
"""

import sys
import time
import datetime
import numpy as np

import cv2
import mss

from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox, QFrame
)

# ─────────────────────────────────────────────
# 1.  录制线程
#     所有屏幕捕获 + VideoWriter 操作都在此线程中
#     完成，不阻塞主界面事件循环。
# ─────────────────────────────────────────────
class RecordThread(QThread):
    """
    在独立线程中持续捕获全屏画面并写入视频文件。

    信号
    ----
    status_signal(str)  : 向主窗口推送状态文字
    error_signal(str)   : 录制出错时通知主窗口
    finished_signal(str): 录制结束，携带保存路径
    """

    status_signal   = pyqtSignal(str)
    error_signal    = pyqtSignal(str)
    finished_signal = pyqtSignal(str)

    FPS = 20  # 目标帧率

    def __init__(self, output_path: str, parent=None):
        super().__init__(parent)
        self.output_path = output_path
        self._running = False          # 线程控制标志

    # ── 外部调用：请求停止 ──
    def stop(self):
        self._running = False

    # ── 线程主体 ──
    def run(self):
        self._running = True

        # 1. 用 mss 打开截图上下文，获取主显示器分辨率
        with mss.mss() as sct:
            # monitors[1] 是主显示器（monitors[0] 是所有显示器的聚合区域）
            monitor = sct.monitors[1]
            width   = monitor["width"]
            height  = monitor["height"]

            # 2. 初始化 OpenCV VideoWriter
            #    XVID 编解码器 + .avi 容器；若想要 mp4 可改为 mp4v/.mp4
            fourcc = cv2.VideoWriter_fourcc(*"XVID")
            writer = cv2.VideoWriter(
                self.output_path,
                fourcc,
                self.FPS,
                (width, height)
            )

            if not writer.isOpened():
                self.error_signal.emit("无法打开 VideoWriter，请检查编解码器是否可用。")
                return

            self.status_signal.emit("● 录制中...")

            frame_interval = 1.0 / self.FPS   # 每帧间隔（秒）
            next_frame_time = time.perf_counter()

            # 3. 主循环：捕获 → 转换 → 写入
            while self._running:
                loop_start = time.perf_counter()

                # ① 截取全屏，返回 BGRA 格式的 mss.ScreenShot 对象
                screenshot = sct.grab(monitor)

                # ② 转换为 numpy 数组（dtype=uint8，形状 H×W×4，BGRA）
                frame_bgra = np.array(screenshot, dtype=np.uint8)

                # ③ 去掉 Alpha 通道，转为 BGR（OpenCV 标准格式）
                frame_bgr = cv2.cvtColor(frame_bgra, cv2.COLOR_BGRA2BGR)

                # ④ 写入视频
                writer.write(frame_bgr)

                # ⑤ 精确限速：等待到下一帧时间点，减少 CPU 空转
                next_frame_time += frame_interval
                sleep_time = next_frame_time - time.perf_counter()
                if sleep_time > 0:
                    time.sleep(sleep_time)

            # 4. 循环退出后，释放 VideoWriter（必须显式调用，否则文件损坏）
            writer.release()

        self.status_signal.emit("空闲")
        self.finished_signal.emit(self.output_path)


# ─────────────────────────────────────────────
# 2.  主窗口
# ─────────────────────────────────────────────
class RecorderWindow(QWidget):
    """
    录屏工具主界面：
      - 状态标签
      - 开始 / 停止 按钮
      - 选择保存路径按钮
    """

    def __init__(self):
        super().__init__()
        self.record_thread = None
        self._output_path  = self._default_output_path()
        self._setup_ui()

    # ── 生成默认文件名（含时间戳，避免覆盖） ──
    @staticmethod
    def _default_output_path() -> str:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"recording_{ts}.avi"

    # ── 构建界面 ──
    def _setup_ui(self):
        self.setWindowTitle("🎬 桌面录屏工具")
        self.setMinimumSize(420, 260)
        self.setStyleSheet("""
            QWidget {
                background-color: #1a1a2e;
                color: #e0e0e0;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }
            QPushButton {
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-size: 14px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton#startBtn {
                background-color: #00b4d8;
                color: #ffffff;
            }
            QPushButton#startBtn:hover {
                background-color: #0096c7;
            }
            QPushButton#startBtn:disabled {
                background-color: #4a4a6a;
                color: #888888;
            }
            QPushButton#stopBtn {
                background-color: #ef233c;
                color: #ffffff;
            }
            QPushButton#stopBtn:hover {
                background-color: #d90429;
            }
            QPushButton#stopBtn:disabled {
                background-color: #4a4a6a;
                color: #888888;
            }
            QPushButton#pathBtn {
                background-color: #3a3a5c;
                color: #c0c0e0;
                font-size: 12px;
                font-weight: normal;
                min-width: 80px;
            }
            QPushButton#pathBtn:hover {
                background-color: #4a4a7a;
            }
            QLabel#statusLabel {
                font-size: 16px;
                font-weight: bold;
            }
            QLabel#pathLabel {
                font-size: 11px;
                color: #8888aa;
            }
            QFrame#divider {
                color: #3a3a5c;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(18)

        # ── 标题 ──
        title = QLabel("桌面录屏工具")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #00b4d8; letter-spacing: 2px;")
        root.addWidget(title)

        # ── 分割线 ──
        line = QFrame()
        line.setObjectName("divider")
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #3a3a5c; max-height: 1px;")
        root.addWidget(line)

        # ── 状态标签 ──
        self.status_label = QLabel("空闲")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #00e676;")
        root.addWidget(self.status_label)

        # ── 保存路径行 ──
        path_row = QHBoxLayout()
        path_row.setSpacing(8)

        self.path_label = QLabel(self._output_path)
        self.path_label.setObjectName("pathLabel")
        self.path_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.path_label.setWordWrap(False)
        path_row.addWidget(self.path_label, stretch=1)

        path_btn = QPushButton("更改路径")
        path_btn.setObjectName("pathBtn")
        path_btn.clicked.connect(self._choose_output_path)
        path_row.addWidget(path_btn)

        root.addLayout(path_row)

        # ── 操作按钮行 ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)

        self.start_btn = QPushButton("▶  开始录制")
        self.start_btn.setObjectName("startBtn")
        self.start_btn.clicked.connect(self.start_recording)
        btn_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("■  停止录制")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_recording)
        btn_row.addWidget(self.stop_btn)

        root.addLayout(btn_row)

    # ── 选择保存路径 ──
    def _choose_output_path(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "选择录像保存位置",
            self._output_path,
            "AVI 文件 (*.avi);;MP4 文件 (*.mp4)"
        )
        if path:
            self._output_path = path
            self.path_label.setText(path)

    # ── 开始录制 ──
    def start_recording(self):
        # 每次录制都生成新的默认路径（若用户未手动更改则自动更新时间戳）
        if not self._output_path or self._output_path.startswith("recording_"):
            self._output_path = self._default_output_path()
            self.path_label.setText(self._output_path)

        # 禁用开始、启用停止
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("● 正在初始化...")
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ff6b6b;")

        # 启动录制线程
        self.record_thread = RecordThread(self._output_path)
        self.record_thread.status_signal.connect(self._on_status)
        self.record_thread.error_signal.connect(self._on_error)
        self.record_thread.finished_signal.connect(self._on_finished)
        self.record_thread.start()

    # ── 停止录制 ──
    def stop_recording(self):
        self.stop_btn.setEnabled(False)
        self.status_label.setText("⏹ 正在停止...")
        if self.record_thread and self.record_thread.isRunning():
            self.record_thread.stop()   # 设置标志，线程自行退出
            # 等待线程完全结束（非阻塞 UI：使用 finished 信号回调恢复按钮）

    # ── 槽：状态更新 ──
    def _on_status(self, msg: str):
        self.status_label.setText(msg)
        if "录制" in msg:
            self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ff6b6b;")
        else:
            self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #00e676;")

    # ── 槽：错误处理 ──
    def _on_error(self, msg: str):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("错误")
        QMessageBox.critical(self, "录制错误", msg)

    # ── 槽：录制完成 ──
    def _on_finished(self, path: str):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        # 下次录制自动生成新时间戳文件名
        self._output_path = self._default_output_path()
        self.path_label.setText(self._output_path)

        QMessageBox.information(
            self,
            "录制完成",
            f"视频已保存到：\n{path}"
        )

    # ── 关闭窗口时确保线程停止 ──
    def closeEvent(self, event):
        if self.record_thread and self.record_thread.isRunning():
            self.record_thread.stop()
            self.record_thread.wait(3000)   # 最多等 3 秒
        event.accept()


# ─────────────────────────────────────────────
# 3.  程序入口
# ─────────────────────────────────────────────
if __name__ == "__main__":
    # 高 DPI 支持（Windows 4K 屏幕下界面不模糊）
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")   # 跨平台统一风格基础

    window = RecorderWindow()
    window.show()

    sys.exit(app.exec_())
