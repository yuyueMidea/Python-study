# -*- coding: utf-8 -*-
"""Pure-Python diff engine."""
from __future__ import annotations

import hashlib
import os
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from .models import DiffResult
from .utils import normalize_rel_path

ProgressCallback = Optional[Callable[[str], None]]


def _file_digest(path: str, block_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(block_size)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _collect_paths(root: str, progress: ProgressCallback = None) -> Dict[str, Tuple[str, bool]]:
    """Collect relative paths below root.

    Returns a map: rel_path -> (absolute_path, is_dir).
    A single file root is represented by its basename.
    """
    root = os.path.abspath(root)
    result: Dict[str, Tuple[str, bool]] = {}
    if not os.path.exists(root):
        raise FileNotFoundError(root)

    if os.path.isfile(root):
        rel = normalize_rel_path(os.path.basename(root))
        result[rel] = (root, False)
        return result

    for current_dir, dir_names, file_names in os.walk(root):
        dir_names[:] = sorted(dir_names)
        file_names = sorted(file_names)
        if progress:
            progress(current_dir)

        if current_dir != root:
            rel_dir = normalize_rel_path(os.path.relpath(current_dir, root))
            result[rel_dir] = (current_dir, True)

        for file_name in file_names:
            abs_path = os.path.join(current_dir, file_name)
            rel_path = normalize_rel_path(os.path.relpath(abs_path, root))
            result[rel_path] = (abs_path, False)
    return result


def compare_paths(left_root: str, right_root: str, progress: ProgressCallback = None) -> List[DiffResult]:
    """Compare two files/folders and return only differences."""
    left_root = os.path.abspath(left_root)
    right_root = os.path.abspath(right_root)
    if not os.path.exists(left_root):
        raise FileNotFoundError(left_root)
    if not os.path.exists(right_root):
        raise FileNotFoundError(right_root)

    # When both selected roots are files, compare them as one pair even if their file names differ.
    if os.path.isfile(left_root) and os.path.isfile(right_root):
        try:
            same = (
                os.path.getsize(left_root) == os.path.getsize(right_root)
                and _file_digest(left_root) == _file_digest(right_root)
            )
        except OSError:
            same = False
        if same:
            return []
        rel = normalize_rel_path(f"{os.path.basename(left_root)}  <->  {os.path.basename(right_root)}")
        return [DiffResult(rel, left_root, right_root, "different", False)]

    left_map = _collect_paths(left_root, progress)
    right_map = _collect_paths(right_root, progress)
    all_keys = sorted(set(left_map) | set(right_map))
    diffs: List[DiffResult] = []

    for rel_path in all_keys:
        left_item = left_map.get(rel_path)
        right_item = right_map.get(rel_path)
        if left_item is None:
            abs_right, right_is_dir = right_item  # type: ignore[misc]
            diffs.append(DiffResult(rel_path, None, abs_right, "right_only", right_is_dir))
            continue
        if right_item is None:
            abs_left, left_is_dir = left_item
            diffs.append(DiffResult(rel_path, abs_left, None, "left_only", left_is_dir))
            continue

        abs_left, left_is_dir = left_item
        abs_right, right_is_dir = right_item
        if left_is_dir != right_is_dir:
            diffs.append(DiffResult(rel_path, abs_left, abs_right, "type_mismatch", True))
            continue
        if left_is_dir:
            continue

        try:
            left_size = os.path.getsize(abs_left)
            right_size = os.path.getsize(abs_right)
            if left_size != right_size or _file_digest(abs_left) != _file_digest(abs_right):
                diffs.append(DiffResult(rel_path, abs_left, abs_right, "different", False))
        except OSError:
            diffs.append(DiffResult(rel_path, abs_left, abs_right, "different", False))
    return diffs
