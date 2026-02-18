# 导出脚本

将《夹缝生长》导出为 PDF 和 EPUB。

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
- `--html` 同时保存中间 HTML 文件，方便预览排版效果

## 导出 EPUB

```bash
source .venv/bin/activate
python script/export_epub.py
```

输出：`output/夹缝生长.epub`

可选参数：
- `-o path` 指定输出路径
