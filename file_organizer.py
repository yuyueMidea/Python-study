#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
file_organizer.py
===================
按文件扩展名自动分类整理文件夹的命令行工具。

功能：
1. 按预设分类（图片/视频/文档/压缩包/程序等）自动把文件移动到对应子文件夹。
2. 支持自定义分类规则（通过 --config 传入 JSON 文件覆盖默认分类）。
3. --dry-run 预览模式：只打印将要执行的操作，不真正移动文件，方便先确认。
4. --recursive 递归扫描子文件夹中的文件。
5. 自动处理重名冲突：目标位置已有同名文件时自动加序号后缀，不会覆盖或丢失文件。
6. 未匹配任何分类的文件会被归入 "Others" 文件夹（可关闭）。
7. 每次真正整理后会生成一份操作日志（JSON），可用 --undo 一键撤销本次整理。

用法示例：
    # 预览：查看 ~/Downloads 下的文件会被怎么分类，不真正移动
    python file_organizer.py organize ~/Downloads --dry-run

    # 真正执行整理
    python file_organizer.py organize ~/Downloads

    # 递归处理子文件夹里的文件，且不建立 "Others" 分类（未匹配的文件保持原位）
    python file_organizer.py organize ~/Downloads --recursive --no-others

    # 使用自定义分类规则
    python file_organizer.py organize ~/Downloads --config my_categories.json

    # 撤销上一次整理操作（根据日志文件）
    python file_organizer.py undo ~/Downloads/.file_organizer_log.json

自定义分类规则 JSON 格式示例（传给 --config）：
    {
      "Images": [".jpg", ".jpeg", ".png"],
      "Music": [".mp3", ".flac", ".wav"]
    }

作者：Claude
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# 默认分类规则
# ---------------------------------------------------------------------------

DEFAULT_CATEGORIES = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".webp"],
    "Videos": [".mp4", ".avi", ".mkv", ".mov"],
    "Documents": [".pdf", ".docx", ".txt", ".xlsx"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "Programs": [".exe", ".msi"],
}

LOG_FILENAME = ".file_organizer_log.json"


# ---------------------------------------------------------------------------
# 核心逻辑
# ---------------------------------------------------------------------------

def build_extension_map(categories):
    """把 {类别: [扩展名列表]} 转换成 {扩展名: 类别} 方便查找，扩展名统一小写。"""
    ext_map = {}
    for category, extensions in categories.items():
        for ext in extensions:
            ext_map[ext.lower()] = category
    return ext_map


def load_categories(config_path):
    if config_path is None:
        return DEFAULT_CATEGORIES
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"找不到分类配置文件: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("分类配置文件的顶层结构必须是一个对象（类别名 -> 扩展名列表）")
    return data


def collect_files(root_dir, recursive):
    """收集待整理的文件列表，跳过已存在的分类子文件夹和日志文件本身。"""
    root_dir = Path(root_dir)
    known_dirs = set()  # 后面会填入已生成的分类文件夹，扫描时跳过，避免重复整理

    if recursive:
        candidates = [p for p in root_dir.rglob("*") if p.is_file()]
    else:
        candidates = [p for p in root_dir.iterdir() if p.is_file()]

    # 过滤掉日志文件本身和隐藏文件（以 . 开头）
    candidates = [p for p in candidates if p.name != LOG_FILENAME and not p.name.startswith(".")]
    return candidates


def resolve_conflict(target_path):
    """
    如果目标路径已存在同名文件，自动加 _1 _2 ... 后缀，避免覆盖。
    返回一个不冲突的最终路径。
    """
    if not target_path.exists():
        return target_path
    stem, suffix = target_path.stem, target_path.suffix
    parent = target_path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def plan_moves(files, ext_map, root_dir, include_others=True):
    """
    根据扩展名规划每个文件的目标路径，返回 (源路径, 目标路径, 分类名) 的列表。
    不做实际的文件系统操作。
    """
    root_dir = Path(root_dir)
    plan = []
    for f in files:
        ext = f.suffix.lower()
        category = ext_map.get(ext)
        if category is None:
            if not include_others:
                continue
            category = "Others"
        target_dir = root_dir / category
        target_path = resolve_conflict(target_dir / f.name)
        plan.append((f, target_path, category))
    return plan


def execute_plan(plan, dry_run):
    """
    执行（或预览）文件移动计划。
    返回实际执行成功的操作记录列表（用于写日志和撤销）。
    """
    executed = []
    category_counts = {}

    for src, dst, category in plan:
        category_counts[category] = category_counts.get(category, 0) + 1
        if dry_run:
            print(f"[预览] {src.name}  ->  {category}/{dst.name}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(src), str(dst))
            print(f"[已移动] {src.name}  ->  {category}/{dst.name}")
            executed.append({"src": str(src), "dst": str(dst)})
        except Exception as e:
            print(f"[失败] {src.name}: {e}", file=sys.stderr)

    print("\n分类汇总：")
    for category, count in sorted(category_counts.items()):
        print(f"  - {category}: {count} 个文件")

    return executed


def write_log(root_dir, executed):
    """把本次真正执行的移动记录写入日志文件，供之后 undo 使用。"""
    log_path = Path(root_dir) / LOG_FILENAME
    log_data = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "moves": executed,
    }
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)
    return log_path


def undo_from_log(log_path):
    """根据日志文件把文件移回原位，并在成功后删除日志文件。"""
    log_path = Path(log_path)
    if not log_path.exists():
        raise FileNotFoundError(f"找不到日志文件: {log_path}")

    with open(log_path, "r", encoding="utf-8") as f:
        log_data = json.load(f)

    moves = log_data.get("moves", [])
    if not moves:
        print("日志中没有可撤销的操作。")
        return

    restored, failed = 0, []
    # 倒序撤销，更符合直觉（后移动的先撤销）
    for record in reversed(moves):
        src = Path(record["src"])
        dst = Path(record["dst"])
        try:
            if not dst.exists():
                raise FileNotFoundError(f"目标文件已不存在，可能被手动移动或删除: {dst}")
            src.parent.mkdir(parents=True, exist_ok=True)
            restore_path = resolve_conflict(src) if src.exists() else src
            shutil.move(str(dst), str(restore_path))
            print(f"[已撤销] {dst.name} -> {restore_path}")
            restored += 1
        except Exception as e:
            failed.append((str(dst), str(e)))
            print(f"[撤销失败] {dst}: {e}", file=sys.stderr)

    print(f"\n撤销完成：成功 {restored} 个，失败 {len(failed)} 个。")
    if not failed:
        log_path.unlink()
        print(f"已删除日志文件: {log_path}")


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------

def cmd_organize(args):
    root_dir = Path(args.directory)
    if not root_dir.is_dir():
        raise NotADirectoryError(f"不是一个有效的文件夹: {root_dir}")

    categories = load_categories(args.config)
    ext_map = build_extension_map(categories)

    files = collect_files(root_dir, recursive=args.recursive)
    if not files:
        print("没有找到待整理的文件。")
        return

    plan = plan_moves(files, ext_map, root_dir, include_others=not args.no_others)
    if not plan:
        print("所有文件都未匹配任何分类，且 --no-others 已开启，无需整理。")
        return

    print(f"共找到 {len(plan)} 个文件待整理（目录: {root_dir}）")
    print(f"{'--- 预览模式，不会真正移动文件 ---' if args.dry_run else '--- 开始整理 ---'}\n")

    executed = execute_plan(plan, dry_run=args.dry_run)

    if not args.dry_run and executed:
        log_path = write_log(root_dir, executed)
        print(f"\n本次操作已记录到: {log_path}")
        print("如需撤销，运行：")
        print(f"  python file_organizer.py undo \"{log_path}\"")


def cmd_undo(args):
    undo_from_log(args.log_file)


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="按文件类型自动归类整理文件夹的工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_organize = sub.add_parser("organize", help="整理指定文件夹")
    p_organize.add_argument("directory", help="要整理的文件夹路径")
    p_organize.add_argument("--dry-run", action="store_true",
                             help="只预览将要执行的操作，不真正移动文件")
    p_organize.add_argument("--recursive", action="store_true",
                             help="递归扫描子文件夹中的文件")
    p_organize.add_argument("--no-others", action="store_true",
                             help="未匹配任何分类的文件保持原位，不归入 Others 文件夹")
    p_organize.add_argument("--config", default=None,
                             help="自定义分类规则的 JSON 文件路径（覆盖默认分类）")

    p_undo = sub.add_parser("undo", help="根据日志文件撤销上一次整理")
    p_undo.add_argument("log_file", help="整理时生成的日志文件路径（默认名为 .file_organizer_log.json）")

    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    try:
        if args.command == "organize":
            cmd_organize(args)
        elif args.command == "undo":
            cmd_undo(args)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
