---
name: pdf
description: Process PDF files - extract text, create PDFs, merge documents. Use when user asks to read PDF, create PDF, or work with PDF files.
---

# PDF Processing Skill

You now have expertise in PDF manipulation. Follow these workflows:

## Reading PDFs

On Windows, avoid printing large PDF text directly to the console because PowerShell/GBK encoding can corrupt output. Prefer writing UTF-8 text to a file, then read that file.

**Option 1: Quick text extraction to UTF-8 text file (preferred)**
```powershell
# Using pdftotext (poppler-utils)
pdftotext input.pdf output.txt  # Output to file

# If the console encoding is problematic, force UTF-8 first:
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = 'utf-8'

# If pdftotext not available, try:
python -c "import fitz, pathlib; doc = fitz.open('input.pdf'); text = '\n\n'.join(page.get_text() for page in doc); pathlib.Path('output.txt').write_text(text, encoding='utf-8')"
```

**Option 2: Page-by-page with metadata**
```python
import fitz  # pip install pymupdf
from pathlib import Path

doc = fitz.open("input.pdf")
print(f"Pages: {len(doc)}")
print(f"Metadata: {doc.metadata}")

chunks = []
for i, page in enumerate(doc):
    text = page.get_text()
    chunks.append(f"--- Page {i+1} ---\n{text}")

Path("output.txt").write_text("\n\n".join(chunks), encoding="utf-8")
print("Saved extracted text to output.txt")
```

## Creating PDFs

**Option 1: From Markdown (recommended)**
```powershell
# Using pandoc
pandoc input.md -o output.pdf

# With custom styling
pandoc input.md -o output.pdf --pdf-engine=xelatex -V geometry:margin=1in
```

**Option 2: Programmatically**
```python
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

c = canvas.Canvas("output.pdf", pagesize=letter)
c.drawString(100, 750, "Hello, PDF!")
c.save()
```

**Option 3: From HTML**
```powershell
# Using wkhtmltopdf
wkhtmltopdf input.html output.pdf

# Or with Python
python -c "
import pdfkit
pdfkit.from_file('input.html', 'output.pdf')
"
```

## Merging PDFs

```python
import fitz

result = fitz.open()
for pdf_path in ["file1.pdf", "file2.pdf", "file3.pdf"]:
    doc = fitz.open(pdf_path)
    result.insert_pdf(doc)
result.save("merged.pdf")
```

## Splitting PDFs

```python
import fitz

doc = fitz.open("input.pdf")
for i in range(len(doc)):
    single = fitz.open()
    single.insert_pdf(doc, from_page=i, to_page=i)
    single.save(f"page_{i+1}.pdf")
```

## Key Libraries

| Task | Library | Install |
|------|---------|---------|
| Read/Write/Merge | PyMuPDF | `pip install pymupdf` |
| Create from scratch | ReportLab | `pip install reportlab` |
| HTML to PDF | pdfkit | `pip install pdfkit` + wkhtmltopdf |
| Text extraction | pdftotext | `winget install oschwartz10612.poppler` / `brew install poppler` / `apt install poppler-utils` |

## Best Practices

1. **Always check if tools are installed** before using them
2. **On Windows, prefer writing extracted text to UTF-8 files** instead of printing full PDF text to the console
3. **Set UTF-8 console output when needed** with `[Console]::OutputEncoding`, `$OutputEncoding`, and `PYTHONIOENCODING=utf-8`
4. **Handle encoding issues** - PDFs may contain various character encodings
5. **Large PDFs**: Process page by page to avoid memory issues
6. **OCR for scanned PDFs**: Use `pytesseract` if text extraction returns empty
