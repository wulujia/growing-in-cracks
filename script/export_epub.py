#!/usr/bin/env python3
"""
导出《夹缝生长》为 EPUB。

依赖安装：
    pip install markdown ebooklib

用法：
    python script/export_epub.py
    python script/export_epub.py -o output/my_book.epub
"""

import argparse
import os
import re
import sys
import uuid

import markdown
from ebooklib import epub

# 项目根目录
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK_DIR = os.path.join(ROOT_DIR, "book")
INDEX_FILE = os.path.join(ROOT_DIR, "index.md")
DEFAULT_OUTPUT = os.path.join(ROOT_DIR, "output", "夹缝生长.epub")

# 不需要问题页的文件
SKIP_QUESTION_FILES = {"restart.md", "crack.md", "flomo.md", "acknowledgments.md"}


def parse_index():
    """从 index.md 解析书籍结构，返回章节列表。"""
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    title_match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
    book_title = title_match.group(1).strip() if title_match else "夹缝生长"

    chapters = []
    current_part = None
    current_section = None

    for line in content.split("\n"):
        line = line.rstrip()

        part_match = re.match(r"^-\s+(第.+部分：.+|前言：|后记：|第.+部分：)", line)
        if part_match:
            part_text = part_match.group(1).rstrip("：").rstrip(":")
            link_match = re.search(r"\[(.+?)\]\((.+?)\)", line)
            if link_match:
                label = link_match.group(1)
                path = link_match.group(2)
                current_part = part_text
                current_section = None
                chapters.append({
                    "part": current_part,
                    "section": None,
                    "title": label,
                    "file": path,
                    "is_part_header": True,
                })
            else:
                current_part = part_text
                current_section = None
            continue

        section_match = re.match(r"^\s*-\s+(.+?)$", line)
        if section_match and "[" not in line:
            current_section = section_match.group(1).strip()
            continue

        link_match = re.search(r"\[(.+?)\]\((.+?)\)", line)
        if link_match:
            chapters.append({
                "part": current_part,
                "section": current_section,
                "title": link_match.group(1),
                "file": link_match.group(2),
                "is_part_header": False,
            })

    return book_title, chapters


def read_chapter(file_path):
    """读取章节 markdown 内容。"""
    full_path = os.path.join(ROOT_DIR, file_path)
    if not os.path.exists(full_path):
        print(f"  警告：文件不存在，跳过 {file_path}", file=sys.stderr)
        return None
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


def extract_question(content, file_path):
    """从章节内容中提取引导问题。"""
    basename = os.path.basename(file_path)
    if basename in SKIP_QUESTION_FILES:
        return None, content

    match = re.match(r"^(.+?)\n\n---\n", content, re.DOTALL)
    if match:
        question = match.group(1).strip()
        body = content[match.end():]
        return question, body

    return None, content


def mark_epigraphs(html_content):
    """将紧跟在 <h1> 后面的连续 <blockquote> 标记为 epigraph。"""
    return re.sub(
        r'(</h1>\s*)((?:<blockquote>\s*.*?</blockquote>\s*)+)',
        lambda m: m.group(1) + re.sub(
            r'<blockquote>',
            '<blockquote class="epigraph">',
            m.group(2),
        ),
        html_content,
        flags=re.DOTALL,
    )


def collect_images(html_content, file_path):
    """收集章节中引用的本地图片路径，返回 {原始src: 文件名} 映射。"""
    images = {}
    for match in re.finditer(r'src="([^"]+)"', html_content):
        src = match.group(1)
        if src.startswith(("http://", "https://")):
            continue
        chapter_dir = os.path.dirname(os.path.join(ROOT_DIR, file_path))
        abs_path = os.path.abspath(os.path.join(chapter_dir, src))
        if os.path.exists(abs_path):
            filename = os.path.basename(abs_path)
            images[src] = {"abs_path": abs_path, "filename": f"images/{filename}"}
    return images


def get_css():
    """返回 EPUB 样式。"""
    return """
body {
    font-family: sans-serif;
    font-size: 1em;
    line-height: 1.8;
    color: #333;
}

h1 {
    font-size: 1.6em;
    font-weight: 700;
    margin-top: 0;
    margin-bottom: 0.8em;
    color: #222;
    border-bottom: 1px solid #ddd;
    padding-bottom: 0.3em;
}

h2 {
    font-size: 1.3em;
    font-weight: 600;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
    color: #333;
}

h3 {
    font-size: 1.1em;
    font-weight: 600;
    margin-top: 1.2em;
    margin-bottom: 0.4em;
    color: #444;
}

p {
    margin: 0.6em 0;
    text-align: justify;
}

blockquote {
    margin: 1em 0;
    padding: 0.5em 1em;
    border-left: 3px solid #ccc;
    color: #666;
    font-style: italic;
    background: #fafafa;
}

blockquote p {
    margin: 0.3em 0;
}

blockquote.epigraph {
    border-left: none;
    background: #f7f3ee;
    border-radius: 4px;
    padding: 1em 1.5em;
    margin: 1.2em 0 1.5em 0;
    color: #555;
    font-style: italic;
    line-height: 2;
}

hr {
    border: none;
    border-top: 1px solid #ddd;
    margin: 1.5em 0;
}

img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 1em auto;
}

code {
    font-family: monospace;
    font-size: 0.9em;
    background: #f5f5f5;
    padding: 0.1em 0.3em;
    border-radius: 3px;
}

pre {
    background: #f5f5f5;
    padding: 1em;
    border-radius: 4px;
    overflow-x: auto;
    font-size: 0.85em;
    line-height: 1.5;
}

pre code {
    background: none;
    padding: 0;
}

ul, ol {
    margin: 0.5em 0;
    padding-left: 1.5em;
}

li {
    margin: 0.2em 0;
}

a {
    color: #333;
    text-decoration: none;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 1em 0;
    font-size: 0.9em;
}

th, td {
    border: 1px solid #ddd;
    padding: 0.4em 0.6em;
    text-align: left;
}

th {
    background: #f5f5f5;
    font-weight: 600;
}

/* 部分标题页 */
.part-title {
    text-align: center;
    font-size: 1.8em;
    font-weight: 700;
    margin-top: 40%;
    color: #222;
    border: none;
}

/* 子分类标题页 */
.section-title {
    text-align: center;
    font-size: 1.4em;
    font-weight: 600;
    margin-top: 40%;
    color: #444;
}

/* 问题页 */
.question-page {
    page-break-before: always;
    page-break-after: always;
    height: 100%;
}

.question-text {
    text-align: center;
    font-size: 1.2em;
    color: #555;
    font-style: italic;
    line-height: 2;
    margin-top: 40%;
}
"""


def build_chapter_html(title, body_html, css_filename="style.css"):
    """构建单个章节的 XHTML 内容，返回 bytes。"""
    html = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN" lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>{title}</title>
  <link rel="stylesheet" type="text/css" href="{css_filename}" />
</head>
<body>
{body_html if body_html.strip() else "<p></p>"}
</body>
</html>"""
    return html.encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description="导出《夹缝生长》为 EPUB")
    parser.add_argument(
        "-o", "--output",
        default=DEFAULT_OUTPUT,
        help=f"输出路径 (默认: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    print("解析目录结构...")
    book_title, chapters = parse_index()
    print(f"  书名: {book_title}")
    print(f"  章节数: {len(chapters)}")

    # 创建 EPUB
    book = epub.EpubBook()
    book.set_identifier(str(uuid.uuid4()))
    book.set_title(book_title)
    book.set_language("zh-CN")
    book.add_author("吴鲁加")

    # 添加样式
    css = epub.EpubItem(
        uid="style",
        file_name="style.css",
        media_type="text/css",
        content=get_css(),
    )
    book.add_item(css)

    md_extensions = ["extra", "toc", "sane_lists", "smarty"]
    spine = ["nav"]
    toc = []
    all_images = {}

    seen_parts = set()
    seen_sections = set()
    part_counter = 0
    current_toc_part = None
    current_toc_section = None

    print("合并章节内容...")

    for ch in chapters:
        content = read_chapter(ch["file"])
        if content is None:
            continue

        chapter_id = os.path.splitext(os.path.basename(ch["file"]))[0]

        # 部分标题页
        if ch["part"] and ch["part"] not in seen_parts:
            seen_parts.add(ch["part"])
            part_counter += 1
            part_id = f"part-{part_counter}"

            part_html = build_chapter_html(
                ch["part"],
                f'<h1 class="part-title">{ch["part"]}</h1>',
            )
            part_item = epub.EpubHtml(
                title=ch["part"],
                file_name=f"{part_id}.xhtml",
                lang="zh-CN",
            )
            part_item.set_content(part_html)
            part_item.add_item(css)
            book.add_item(part_item)
            spine.append(part_item)

            current_toc_part = (epub.Link(f"{part_id}.xhtml", ch["part"], part_id), [])
            toc.append(current_toc_part)
            current_toc_section = None
            seen_sections.clear()

        # 子分类标题页
        if ch["section"] and ch["section"] not in seen_sections:
            seen_sections.add(ch["section"])
            section_id = f"section-{len(seen_sections)}-{part_counter}"

            section_html = build_chapter_html(
                ch["section"],
                f'<p class="section-title">{ch["section"]}</p>',
            )
            section_item = epub.EpubHtml(
                title=ch["section"],
                file_name=f"{section_id}.xhtml",
                lang="zh-CN",
            )
            section_item.set_content(section_html)
            section_item.add_item(css)
            book.add_item(section_item)
            spine.append(section_item)

            current_toc_section = (
                epub.Link(f"{section_id}.xhtml", ch["section"], section_id),
                [],
            )
            if current_toc_part:
                current_toc_part[1].append(current_toc_section)

        # 提取引导问题
        question, content = extract_question(content, ch["file"])

        # 问题页
        if question:
            q_id = f"question-{chapter_id}"
            q_html = build_chapter_html(
                "问题",
                f'<div class="question-page"><p class="question-text">{question}</p></div>',
            )
            q_item = epub.EpubHtml(
                title="问题",
                file_name=f"{q_id}.xhtml",
                lang="zh-CN",
            )
            q_item.set_content(q_html)
            q_item.add_item(css)
            book.add_item(q_item)
            spine.append(q_item)

        # 章节内容
        html_content = markdown.markdown(content, extensions=md_extensions)
        html_content = mark_epigraphs(html_content)

        # 收集并处理图片
        images = collect_images(html_content, ch["file"])
        for src, info in images.items():
            epub_path = info["filename"]
            if epub_path not in all_images:
                all_images[epub_path] = info["abs_path"]
            html_content = html_content.replace(f'src="{src}"', f'src="{epub_path}"')

        chapter_html = build_chapter_html(ch["title"], html_content)
        chapter_item = epub.EpubHtml(
            title=ch["title"],
            file_name=f"{chapter_id}.xhtml",
            lang="zh-CN",
        )
        chapter_item.set_content(chapter_html)
        chapter_item.add_item(css)
        book.add_item(chapter_item)
        spine.append(chapter_item)

        # 添加到目录
        link = epub.Link(f"{chapter_id}.xhtml", ch["title"], chapter_id)
        if current_toc_section:
            current_toc_section[1].append(link)
        elif current_toc_part:
            current_toc_part[1].append(link)
        else:
            toc.append(link)

    # 添加图片到 EPUB
    for epub_path, abs_path in all_images.items():
        ext = os.path.splitext(abs_path)[1].lower()
        media_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".webp": "image/webp",
        }
        media_type = media_types.get(ext, "application/octet-stream")
        with open(abs_path, "rb") as f:
            img_content = f.read()
        img_item = epub.EpubItem(
            file_name=epub_path,
            media_type=media_type,
            content=img_content,
        )
        book.add_item(img_item)

    # 设置目录和书脊
    book.toc = toc
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    print("生成 EPUB...")
    epub.write_epub(args.output, book)
    print(f"完成: {args.output}")


if __name__ == "__main__":
    main()
