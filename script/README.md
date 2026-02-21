# 导出脚本

将《夹缝生长》导出为 PDF、EPUB 和 DOCX。

## 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r script/requirements.txt
```

## 导出 PDF

```bash
source .venv/bin/activate
python script/export_pdf.py
```

输出：`output/夹缝生长.pdf`

可选参数：
- `-o path` 指定输出路径
- `--chapter N` 导出指定章节（如 `--chapter 1` 导出第 1 章）
- `--html` 同时保存中间 HTML 文件，方便预览排版效果

## 导出 EPUB

```bash
source .venv/bin/activate
python script/export_epub.py
```

输出：`output/夹缝生长.epub`

可选参数：
- `-o path` 指定输出路径
- `--chapter N` 导出指定章节

## 导出 DOCX

```bash
source .venv/bin/activate
python script/export_docx.py
```

输出：`output/夹缝生长.docx`

可选参数：
- `-o path` 指定输出路径
- `--chapter N` 导出指定章节

## 章节编号

导出时会自动为每一章生成编号（1, 2, 3...），并为章内的二级标题生成二级编号（1.1, 1.2...）。编号同时出现在目录和正文中。前言、后记、致谢不参与编号。
