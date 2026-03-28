#!/usr/bin/env python3
"""
修复全书中文双引号方向问题。

常见问题：
1. 左引号用了 U+201D（"）而非 U+201C（"），导致开口闭口方向一样
2. 中文语境下误用了英文直引号（"）

用法：
    python script/fix_quotes.py          # 修复并写入文件
    python script/fix_quotes.py --check  # 仅检查，不修改
"""
import argparse
import os
import re
import sys


def fix_chinese_quotes(filepath, dry_run=False):
    with open(filepath, "r") as f:
        content = f.read()

    original = content
    lines = content.split("\n")
    fixed_lines = []
    in_code_block = False
    quote_depth = 0

    for line in lines:
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            fixed_lines.append(line)
            continue

        if in_code_block:
            fixed_lines.append(line)
            continue

        chars = list(line)
        i = 0
        while i < len(chars):
            c = chars[i]

            if c == "\u201c":  # correct left quote
                quote_depth += 1
            elif c == "\u201d":  # right quote - but should it be left?
                if quote_depth <= 0:
                    chars[i] = "\u201c"
                    quote_depth += 1
                else:
                    quote_depth -= 1
            elif c == '"':  # straight double quote
                prev_char = chars[i - 1] if i > 0 else "\n"
                next_char = chars[i + 1] if i + 1 < len(chars) else "\n"

                is_chinese_context = False
                if prev_char and re.match(
                    r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]", prev_char
                ):
                    is_chinese_context = True
                if next_char and re.match(
                    r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]", next_char
                ):
                    is_chinese_context = True
                if prev_char in "，。；：、—…）】》":
                    is_chinese_context = True
                if next_char in "，。；：、—…（【《":
                    is_chinese_context = True

                if is_chinese_context:
                    if quote_depth <= 0:
                        chars[i] = "\u201c"
                        quote_depth += 1
                    else:
                        chars[i] = "\u201d"
                        quote_depth -= 1

            i += 1

        fixed_lines.append("".join(chars))

    result = "\n".join(fixed_lines)

    if result != original:
        changes = []
        orig_lines = original.split("\n")
        res_lines = result.split("\n")
        for idx, (ol, rl) in enumerate(zip(orig_lines, res_lines), 1):
            if ol != rl:
                changes.append(f"  L{idx}: {rl.strip()[:120]}")

        if not dry_run:
            with open(filepath, "w") as f:
                f.write(result)

        left = result.count("\u201c")
        right = result.count("\u201d")
        balance = "BALANCED" if left == right else f"UNBALANCED left={left} right={right}"
        action = "would fix" if dry_run else "fixed"

        print(f"\n=== {filepath} ({len(changes)} lines {action}, {balance}) ===")
        for c in changes[:20]:
            print(c)
        if len(changes) > 20:
            print(f"  ... and {len(changes) - 20} more")
        return len(changes)
    else:
        left = result.count("\u201c")
        right = result.count("\u201d")
        if left != right:
            print(f"\n=== {filepath} (UNBALANCED left={left} right={right}) ===")
            return -1
        return 0


def main():
    parser = argparse.ArgumentParser(description="修复全书中文双引号方向")
    parser.add_argument("--check", action="store_true", help="仅检查，不修改文件")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    index_path = os.path.join(project_root, "index.md")

    if not os.path.exists(index_path):
        print(f"Error: {index_path} not found", file=sys.stderr)
        sys.exit(1)

    book_files = []
    with open(index_path, "r") as f:
        for line in f:
            m = re.search(r"\((book/\S+\.md)\)", line)
            if m:
                book_files.append(os.path.join(project_root, m.group(1)))

    total_fixed = 0
    for fpath in book_files:
        if os.path.exists(fpath):
            n = fix_chinese_quotes(fpath, dry_run=args.check)
            if n and n > 0:
                total_fixed += n

    print(f"\n--- {'Check' if args.check else 'Fix'} complete: {total_fixed} lines across {len(book_files)} files ---")


if __name__ == "__main__":
    main()
