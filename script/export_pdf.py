#!/usr/bin/env python3
"""
导出《夹缝生长》为 PDF。

依赖安装：
    pip install markdown weasyprint

用法：
    python script/export_pdf.py
    python script/export_pdf.py -o output/my_book.pdf
"""

import argparse
import os
import re
import sys

import markdown
from weasyprint import HTML

# 项目根目录
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK_DIR = os.path.join(ROOT_DIR, "book")
INDEX_FILE = os.path.join(ROOT_DIR, "index.md")
DEFAULT_OUTPUT = os.path.join(ROOT_DIR, "output", "夹缝生长.pdf")


def parse_index():
    """从 index.md 解析书籍结构，返回章节列表。"""
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # 提取书名
    title_match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
    book_title = title_match.group(1).strip() if title_match else "夹缝生长"

    chapters = []
    current_part = None
    current_section = None

    for line in content.split("\n"):
        line = line.rstrip()

        # 匹配部分标题：- 第一部分：xxx 或 - 前言：xxx 或 - 后记：xxx
        part_match = re.match(r"^-\s+(第.+部分：.+|前言：|后记：|第.+部分：)", line)
        if part_match:
            part_text = part_match.group(1).rstrip("：").rstrip(":")
            # 检查这一行本身是否包含链接
            link_match = re.search(r"\[(.+?)\]\((.+?)\)", line)
            if link_match:
                # 前言/后记这种自带链接的行
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

        # 匹配子分类标题（缩进或顶级均可，但不含链接、不是"第X部分"）
        # 例如：  - 做产品——xxx  或  - 做增长——xxx
        section_match = re.match(r"^\s*-\s+(.+?)$", line)
        if section_match and "[" not in line:
            current_section = section_match.group(1).strip()
            continue

        # 匹配章节链接：  - [标题](path)
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


# 不需要问题页的文件（前言、后记、第五部分等直接以标题开头）
SKIP_QUESTION_FILES = {"restart.md", "crack.md", "flomo.md"}


def extract_question(content, file_path):
    """从章节内容中提取引导问题。

    大多数章节格式为：
        问题文本
        ---
        # 标题
        ...

    返回 (question, body)，如果没有问题则返回 (None, content)。
    """
    basename = os.path.basename(file_path)
    if basename in SKIP_QUESTION_FILES:
        return None, content

    # 匹配开头的问题 + --- 分隔线
    match = re.match(r"^(.+?)\n\n---\n", content, re.DOTALL)
    if match:
        question = match.group(1).strip()
        body = content[match.end():]
        return question, body

    return None, content


def fix_image_paths(html_content, base_dir):
    """将图片的相对路径转为绝对路径（file:// URI）。"""
    def replace_src(match):
        src = match.group(1)
        if src.startswith(("http://", "https://", "file://")):
            return match.group(0)
        abs_path = os.path.abspath(os.path.join(base_dir, src))
        return f'src="file://{abs_path}"'

    return re.sub(r'src="([^"]+)"', replace_src, html_content)


def build_html(book_title, chapters):
    """将所有章节合并为完整 HTML。"""
    md_extensions = ["extra", "toc", "sane_lists", "smarty"]

    toc_items = []
    body_parts = []
    part_counter = 0
    seen_parts = set()
    seen_sections = set()

    for ch in chapters:
        content = read_chapter(ch["file"])
        if content is None:
            continue

        # 在每个部分前插入部分标题页
        if ch["part"] and ch["part"] not in seen_parts:
            seen_parts.add(ch["part"])
            part_counter += 1
            part_id = f"part-{part_counter}"
            toc_items.append({
                "type": "part",
                "title": ch["part"],
                "id": part_id,
                "children": [],
            })
            body_parts.append(
                f'<div class="part-page" id="{part_id}">'
                f"<h1>{ch['part']}</h1>"
                f"</div>"
            )
            seen_sections.clear()

        # 子分类标题
        if ch["section"] and ch["section"] not in seen_sections:
            seen_sections.add(ch["section"])
            section_id = f"section-{len(seen_sections)}-{part_counter}"
            if toc_items and toc_items[-1]["type"] == "part":
                toc_items[-1]["children"].append({
                    "type": "section",
                    "title": ch["section"],
                    "id": section_id,
                    "children": [],
                })
            body_parts.append(
                f'<h2 class="section-title" id="{section_id}">{ch["section"]}</h2>'
            )

        # 提取引导问题
        question, content = extract_question(content, ch["file"])

        # 章节内容
        chapter_id = os.path.splitext(os.path.basename(ch["file"]))[0]
        html_content = markdown.markdown(content, extensions=md_extensions)
        html_content = fix_image_paths(html_content, BOOK_DIR)

        # 插入问题页（独立一页，显示在章节正文之前）
        if question:
            body_parts.append(
                f'<div class="question-page">'
                f'<p class="question-text">{question}</p>'
                f'</div>'
            )

        # 为章节的第一个 h1 替换 ID（toc 扩展可能已经生成了 id）
        html_content = re.sub(
            r'<h1[^>]*>',
            f'<h1 id="{chapter_id}">',
            html_content,
            count=1,
        )

        # 添加到目录
        chapter_entry = {"type": "chapter", "title": ch["title"], "id": chapter_id}
        if toc_items and toc_items[-1]["type"] == "part":
            children = toc_items[-1]["children"]
            if children and children[-1]["type"] == "section":
                children[-1]["children"].append(chapter_entry)
            else:
                children.append(chapter_entry)
        else:
            toc_items.append(chapter_entry)

        body_parts.append(f'<div class="chapter">{html_content}</div>')

    # 构建目录 HTML
    toc_html = build_toc_html(toc_items)

    # 组装完整 HTML
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{book_title}</title>
<style>
{get_css()}
</style>
</head>
<body>

<div class="cover-page">
    <h1 class="cover-title">{book_title}</h1>
</div>

<div class="toc-page">
    <h1 class="toc-heading">目录</h1>
    {toc_html}
</div>

{"".join(body_parts)}

</body>
</html>"""

    return html


def build_toc_html(toc_items):
    """构建目录 HTML。"""
    lines = ['<nav class="toc">']
    for item in toc_items:
        if item["type"] == "part":
            lines.append(
                f'<div class="toc-part">'
                f'<a href="#{item["id"]}">{item["title"]}</a>'
            )
            for child in item.get("children", []):
                if child["type"] == "section":
                    lines.append(
                        f'<div class="toc-section">{child["title"]}</div>'
                    )
                    for ch in child.get("children", []):
                        lines.append(
                            f'<div class="toc-chapter">'
                            f'<a href="#{ch["id"]}">{ch["title"]}</a>'
                            f"</div>"
                        )
                elif child["type"] == "chapter":
                    lines.append(
                        f'<div class="toc-chapter">'
                        f'<a href="#{child["id"]}">{child["title"]}</a>'
                        f"</div>"
                    )
            lines.append("</div>")
        elif item["type"] == "chapter":
            lines.append(
                f'<div class="toc-chapter toc-top">'
                f'<a href="#{item["id"]}">{item["title"]}</a>'
                f"</div>"
            )
    lines.append("</nav>")
    return "\n".join(lines)


def get_css():
    """返回 PDF 排版样式。"""
    return """
@page {
    size: A4;
    margin: 2.5cm 2cm;

    @bottom-center {
        content: counter(page);
        font-size: 9pt;
        color: #999;
    }
}

@page :first {
    @bottom-center { content: none; }
}

body {
    font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei",
                 "Noto Sans CJK SC", "Source Han Sans SC", sans-serif;
    font-size: 11pt;
    line-height: 1.8;
    color: #333;
}

/* 封面 */
.cover-page {
    page-break-after: always;
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100vh;
    text-align: center;
}

.cover-title {
    font-size: 32pt;
    font-weight: 700;
    letter-spacing: 0.1em;
    color: #222;
}

/* 目录页 */
.toc-page {
    page-break-after: always;
}

.toc-heading {
    font-size: 20pt;
    margin-bottom: 1.5em;
    text-align: center;
    color: #222;
}

.toc a {
    text-decoration: none;
    color: #333;
}

.toc a::after {
    content: target-counter(attr(href), page);
    float: right;
    color: #999;
}

.toc-part {
    margin-top: 1.2em;
    margin-bottom: 0.3em;
}

.toc-part > a {
    font-size: 12pt;
    font-weight: 700;
    color: #222;
}

.toc-section {
    font-size: 10.5pt;
    font-weight: 600;
    color: #555;
    margin: 0.5em 0 0.2em 1em;
}

.toc-chapter {
    font-size: 10.5pt;
    margin-left: 2em;
    line-height: 2;
}

.toc-chapter a {
    color: #444;
}

.toc-top {
    margin-left: 1em;
    font-size: 11pt;
}

/* 部分标题页 */
.part-page {
    page-break-before: always;
    page-break-after: always;
    display: flex;
    align-items: center;
    justify-content: center;
    height: 80vh;
    text-align: center;
}

.part-page h1 {
    font-size: 26pt;
    font-weight: 700;
    color: #222;
    border: none;
}

/* 问题页 */
.question-page {
    page-break-before: always;
    page-break-after: always;
    display: flex;
    align-items: center;
    justify-content: center;
    height: 80vh;
    text-align: center;
}

.question-text {
    font-size: 16pt;
    color: #555;
    font-style: italic;
    max-width: 70%;
    line-height: 2;
}

/* 章节 */
.chapter {
    page-break-before: always;
}

h1 {
    font-size: 20pt;
    font-weight: 700;
    margin-top: 0;
    margin-bottom: 0.8em;
    color: #222;
    border-bottom: 1px solid #ddd;
    padding-bottom: 0.3em;
}

h2 {
    font-size: 15pt;
    font-weight: 600;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
    color: #333;
}

.section-title {
    page-break-before: avoid;
    font-size: 13pt;
    color: #555;
    border-left: 3px solid #999;
    padding-left: 0.5em;
    margin-top: 0;
}

h3 {
    font-size: 13pt;
    font-weight: 600;
    margin-top: 1.2em;
    margin-bottom: 0.4em;
    color: #444;
}

p {
    margin: 0.6em 0;
    text-align: justify;
}

/* 引用 */
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

/* 水平线 */
hr {
    border: none;
    border-top: 1px solid #ddd;
    margin: 1.5em 0;
}

/* 图片 */
img {
    max-width: 85%;
    max-height: 500px;
    width: auto;
    height: auto;
    display: block;
    margin: 1em auto;
    object-fit: contain;
}

/* 代码 */
code {
    font-family: "SF Mono", "Menlo", "Monaco", monospace;
    font-size: 9.5pt;
    background: #f5f5f5;
    padding: 0.1em 0.3em;
    border-radius: 3px;
}

pre {
    background: #f5f5f5;
    padding: 1em;
    border-radius: 4px;
    overflow-x: auto;
    font-size: 9pt;
    line-height: 1.5;
}

pre code {
    background: none;
    padding: 0;
}

/* 列表 */
ul, ol {
    margin: 0.5em 0;
    padding-left: 1.5em;
}

li {
    margin: 0.2em 0;
}

/* 链接 */
a {
    color: #333;
    text-decoration: none;
}

/* 表格 */
table {
    border-collapse: collapse;
    width: 100%;
    margin: 1em 0;
    font-size: 10pt;
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
"""


def main():
    parser = argparse.ArgumentParser(description="导出《夹缝生长》为 PDF")
    parser.add_argument(
        "-o", "--output",
        default=DEFAULT_OUTPUT,
        help=f"输出路径 (默认: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="同时保存中间 HTML 文件",
    )
    args = parser.parse_args()

    # 确保输出目录存在
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    print("解析目录结构...")
    book_title, chapters = parse_index()
    print(f"  书名: {book_title}")
    print(f"  章节数: {len(chapters)}")

    print("合并章节内容...")
    html = build_html(book_title, chapters)

    if args.html:
        html_path = args.output.rsplit(".", 1)[0] + ".html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  HTML 已保存: {html_path}")

    print("生成 PDF...")
    HTML(string=html, base_url=BOOK_DIR).write_pdf(args.output)
    print(f"完成: {args.output}")


if __name__ == "__main__":
    main()
