# -*- coding: utf-8 -*-
"""Small filesystem and text helpers."""
from __future__ import annotations

import os
import shutil
from typing import Iterable, List, Tuple

TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".json", ".xml", ".yaml", ".yml", ".csv", ".tsv",
    ".ini", ".cfg", ".conf", ".log", ".html", ".htm", ".css", ".js",
    ".ts", ".vue", ".java", ".c", ".cpp", ".h", ".hpp", ".cs", ".go",
    ".rs", ".php", ".rb", ".r", ".m", ".sql", ".sh", ".bat", ".ps1",
}


def normalize_rel_path(path: str) -> str:
    return path.replace("\\", "/")


def is_probably_text_file(path: str) -> bool:
    """Fast text/binary guess for the compare viewer."""
    ext = os.path.splitext(path)[1].lower()
    if ext in TEXT_EXTENSIONS:
        return True
    try:
        with open(path, "rb") as f:
            chunk = f.read(4096)
    except OSError:
        return False
    if b"\x00" in chunk:
        return False
    try:
        chunk.decode("utf-8")
        return True
    except UnicodeDecodeError:
        try:
            chunk.decode("gb18030")
            return True
        except UnicodeDecodeError:
            return False


def read_text_file(path: str) -> Tuple[str, str]:
    """Read a text file with several common encodings."""
    encodings = ("utf-8", "utf-8-sig", "gb18030", "big5", "latin-1")
    last_error = None
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                return f.read(), enc
        except UnicodeDecodeError as exc:
            last_error = exc
        except FileNotFoundError:
            return "", "utf-8"
    with open(path, "r", encoding="latin-1", newline="") as f:
        return f.read(), "latin-1"


def write_text_file(path: str, text: str, encoding: str = "utf-8") -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding=encoding, newline="") as f:
        f.write(text)


def copy_path(src: str, dst: str, overwrite: bool = True) -> None:
    """Copy one file or directory to the destination path."""
    if not os.path.exists(src):
        raise FileNotFoundError(src)
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    if os.path.isdir(src):
        if os.path.exists(dst):
            if not overwrite:
                raise FileExistsError(dst)
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            else:
                os.remove(dst)
        shutil.copytree(src, dst)
    else:
        if os.path.isdir(dst):
            dst = os.path.join(dst, os.path.basename(src))
        if os.path.exists(dst) and not overwrite:
            raise FileExistsError(dst)
        shutil.copy2(src, dst)


def delete_path(path: str) -> None:
    if not os.path.exists(path):
        return
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def safe_rename(path: str, new_name: str) -> str:
    """Rename a file/folder within the same parent folder and return new path."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    new_name = new_name.strip()
    if not new_name:
        raise ValueError("New name cannot be empty")
    parent = os.path.dirname(os.path.abspath(path))
    new_path = os.path.join(parent, new_name)
    if os.path.exists(new_path):
        raise FileExistsError(new_path)
    os.rename(path, new_path)
    return new_path
