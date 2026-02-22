#!/usr/bin/env python3
"""
导出《夹缝生长》为 PDF。

依赖安装：
    pip install markdown weasyprint

用法：
    python script/export_pdf.py
    python script/export_pdf.py -o output/my_book.pdf
    python script/export_pdf.py --chapter 1
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

# 不需要问题页的文件（前言、后记等直接以标题开头）
SKIP_QUESTION_FILES = {"restart.md", "crack.md", "flomo.md"}

# 不参与编号的特殊文件
SPECIAL_FILES = {"restart.md", "crack.md", "acknowledgments.md"}


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

        # 匹配子分类标题（不含链接）
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


def assign_chapter_numbers(chapters):
    """为每个常规章节分配编号。前言、后记、致谢不编号。"""
    num = 0
    for ch in chapters:
        basename = os.path.basename(ch["file"])
        if basename in SPECIAL_FILES or ch.get("is_part_header"):
            ch["chapter_num"] = None
        elif ch["part"] and re.match(r"第.+部分", ch["part"]):
            num += 1
            ch["chapter_num"] = num
        else:
            ch["chapter_num"] = None


def add_numbering_to_content(content, chapter_num):
    """为章节内容的 h1、h2、h3 添加编号。"""
    if chapter_num is None:
        return content
    h2_counter = 0
    h3_counter = 0
    lines = content.split("\n")
    result = []
    for line in lines:
        if re.match(r"^# ", line):
            line = re.sub(r"^# (.+)", f"# {chapter_num}. \\1", line)
        elif re.match(r"^## ", line):
            h2_counter += 1
            h3_counter = 0
            line = re.sub(r"^## (.+)", f"## {chapter_num}.{h2_counter} \\1", line)
        elif re.match(r"^### ", line):
            h3_counter += 1
            line = re.sub(r"^### (.+)", f"### {chapter_num}.{h2_counter}.{h3_counter} \\1", line)
        result.append(line)
    return "\n".join(result)


def extract_h2_headings(content):
    """从 markdown 内容中提取 h2 标题列表（原始标题，不含编号）。"""
    headings = []
    for line in content.split("\n"):
        match = re.match(r"^## (.+)", line)
        if match:
            headings.append(match.group(1).strip())
    return headings


def read_chapter(file_path):
    """读取章节 markdown 内容。"""
    full_path = os.path.join(ROOT_DIR, file_path)
    if not os.path.exists(full_path):
        print(f"  警告：文件不存在，跳过 {file_path}", file=sys.stderr)
        return None
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


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

        chapter_num = ch.get("chapter_num")
        chapter_id = os.path.splitext(os.path.basename(ch["file"]))[0]

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

        # 子分类标题页（独立一页，大字居中）
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
                f'<div class="section-page" id="{section_id}">'
                f'<p class="section-page-title">{ch["section"]}</p>'
                f'</div>'
            )

        # 提取引导问题
        question, content = extract_question(content, ch["file"])

        # 提取 h2 标题（在添加编号之前）
        h2_headings = extract_h2_headings(content)

        # 添加编号
        content = add_numbering_to_content(content, chapter_num)

        # 章节内容
        html_content = markdown.markdown(content, extensions=md_extensions)
        html_content = fix_image_paths(html_content, BOOK_DIR)
        html_content = mark_epigraphs(html_content)

        # 为 h2 添加可链接的 ID
        h2_idx = [0]

        def replace_h2_tag(match, _idx=h2_idx, _cid=chapter_id):
            _idx[0] += 1
            return f'<h2 id="{_cid}-h2-{_idx[0]}">'

        html_content = re.sub(r'<h2[^>]*>', replace_h2_tag, html_content)

        # 插入问题页（独立一页，显示在章节正文之前）
        if question:
            body_parts.append(
                f'<div class="question-page">'
                f'<p class="question-text">{question}</p>'
                f'</div>'
            )

        # 为章节的第一个 h1 替换 ID
        html_content = re.sub(
            r'<h1[^>]*>',
            f'<h1 id="{chapter_id}">',
            html_content,
            count=1,
        )

        # 构建目录条目
        display_title = f"{chapter_num}. {ch['title']}" if chapter_num else ch["title"]
        chapter_entry = {
            "type": "chapter",
            "title": display_title,
            "id": chapter_id,
            "subheadings": [],
        }

        # 添加 h2 子标题到目录
        if chapter_num and h2_headings:
            for i, heading in enumerate(h2_headings, 1):
                chapter_entry["subheadings"].append({
                    "title": f"{chapter_num}.{i} {heading}",
                    "id": f"{chapter_id}-h2-{i}",
                })

        # 添加到目录
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


def build_chapter_html_standalone(book_title, chapters):
    """构建单个章节的 HTML（用于单章节导出）。"""
    md_extensions = ["extra", "toc", "sane_lists", "smarty"]

    body_parts = []

    for ch in chapters:
        content = read_chapter(ch["file"])
        if content is None:
            continue

        chapter_num = ch.get("chapter_num")

        # 提取引导问题
        question, content = extract_question(content, ch["file"])

        # 添加编号
        content = add_numbering_to_content(content, chapter_num)

        # 章节内容
        html_content = markdown.markdown(content, extensions=md_extensions)
        html_content = fix_image_paths(html_content, BOOK_DIR)
        html_content = mark_epigraphs(html_content)

        # 插入问题页
        if question:
            body_parts.append(
                f'<div class="question-page">'
                f'<p class="question-text">{question}</p>'
                f'</div>'
            )

        body_parts.append(f'<div class="chapter">{html_content}</div>')

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
{"".join(body_parts)}
</body>
</html>"""

    return html


def build_toc_html(toc_items):
    """构建目录 HTML，包含章节编号和 h2 子标题。"""
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
                        for sub in ch.get("subheadings", []):
                            lines.append(
                                f'<div class="toc-subheading">'
                                f'<a href="#{sub["id"]}">{sub["title"]}</a>'
                                f"</div>"
                            )
                elif child["type"] == "chapter":
                    lines.append(
                        f'<div class="toc-chapter">'
                        f'<a href="#{child["id"]}">{child["title"]}</a>'
                        f"</div>"
                    )
                    for sub in child.get("subheadings", []):
                        lines.append(
                            f'<div class="toc-subheading">'
                            f'<a href="#{sub["id"]}">{sub["title"]}</a>'
                            f"</div>"
                        )
            lines.append("</div>")
        elif item["type"] == "chapter":
            lines.append(
                f'<div class="toc-chapter toc-top">'
                f'<a href="#{item["id"]}">{item["title"]}</a>'
                f"</div>"
            )
            for sub in item.get("subheadings", []):
                lines.append(
                    f'<div class="toc-subheading toc-top-sub">'
                    f'<a href="#{sub["id"]}">{sub["title"]}</a>'
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
    padding-top: 35vh;
    text-align: center;
}

.cover-title {
    font-size: 32pt;
    font-weight: 700;
    letter-spacing: 0.1em;
    color: #222;
    border: none;
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

.toc-subheading {
    font-size: 10pt;
    margin-left: 3.5em;
    line-height: 1.8;
}

.toc-subheading a {
    color: #666;
}

.toc-subheading a::after {
    content: target-counter(attr(href), page);
    float: right;
    color: #bbb;
}

.toc-top-sub {
    margin-left: 2.5em;
}

/* 部分标题页 */
.part-page {
    page-break-before: always;
    page-break-after: always;
    padding-top: 35vh;
    text-align: center;
}

.part-page h1 {
    font-size: 26pt;
    font-weight: 700;
    color: #222;
    border: none;
}

/* 子分类标题页（如"做产品"、"做增长"等） */
.section-page {
    page-break-before: always;
    page-break-after: always;
    padding-top: 35vh;
    text-align: center;
}

.section-page-title {
    font-size: 20pt;
    font-weight: 600;
    color: #444;
    text-align: center;
}

/* 问题页 */
.question-page {
    page-break-before: always;
    page-break-after: always;
    padding-top: 35vh;
    text-align: center;
}

.question-text {
    font-size: 16pt;
    color: #555;
    font-style: italic;
    line-height: 2;
    text-align: center;
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

/* 章节开头引言 */
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
        default=None,
        help=f"输出路径 (默认: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--chapter",
        type=int,
        default=None,
        help="导出指定章节（按编号，如 --chapter 1）",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="同时保存中间 HTML 文件",
    )
    args = parser.parse_args()

    print("解析目录结构...")
    book_title, chapters = parse_index()
    assign_chapter_numbers(chapters)
    print(f"  书名: {book_title}")
    print(f"  章节数: {len(chapters)}")

    # 按章节过滤
    if args.chapter is not None:
        target = [ch for ch in chapters if ch.get("chapter_num") == args.chapter]
        if not target:
            print(f"错误：找不到第 {args.chapter} 章", file=sys.stderr)
            sys.exit(1)
        chapters = target
        ch = target[0]
        if args.output is None:
            output_dir = os.path.join(ROOT_DIR, "output")
            args.output = os.path.join(output_dir, f"{args.chapter:02d}-{ch['title']}.pdf")
        print(f"  导出章节: {args.chapter}. {ch['title']}")
    else:
        if args.output is None:
            args.output = DEFAULT_OUTPUT

    # 确保输出目录存在
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    print("合并章节内容...")
    if args.chapter is not None:
        html = build_chapter_html_standalone(book_title, chapters)
    else:
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
