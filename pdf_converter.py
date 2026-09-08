#!/usr/bin/env python3
"""
PDF-zu-ePub-Konverter für eNews
- Nur für durchsuchbare (textbasierte) PDFs
- Erzeugt ein einfaches ePub mit einem Kapitel pro PDF-Seite
- Nutzt PyMuPDF (fitz) zur Text-Extraktion
"""

from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

#import fitz  # PyMuPDF
import pymupdf as fitz

def is_searchable_pdf(pdf_path: Path, min_chars: int = 50) -> bool:
    """Prüft, ob ein PDF durchsuchbaren Text enthält (Stichprobe: erste 3 Seiten)."""
    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        return False

    total_chars = 0
    pages_to_check = min(3, doc.page_count)
    for i in range(pages_to_check):
        total_chars += len(str(doc[i].get_text()).strip())
    doc.close()

    return total_chars >= min_chars


def xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def convert_pdf_to_epub_original(pdf_path: Path, epub_path: Path) -> bool:
    """
    Konvertiert ein durchsuchbares PDF in ein einfaches ePub.
    Jede PDF-Seite wird zu einem eigenen Kapitel.

    Rückgabe: True bei Erfolg, False wenn PDF nicht durchsuchbar oder Fehler auftrat.
    """
    if not is_searchable_pdf(pdf_path):
        return False

    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        return False

    title = pdf_path.stem

    epub_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(str(epub_path), "w", compression=zipfile.ZIP_DEFLATED) as epub:
        epub.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)

        container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""
        epub.writestr("META-INF/container.xml", container_xml)

        manifest_items = []
        spine_items = []
        nav_points = []

        for i in range(doc.page_count):
            page_text = str(doc[i].get_text()).strip()
            chapter_id = f"page-{i+1}"
            chapter_file = f"page_{i+1}.xhtml"

            paragraphs = "\n".join(
                f"<p>{xml_escape(p)}</p>" for p in page_text.split("\n\n") if p.strip()
            )

            chapter_xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Seite {i+1}</title></head>
<body>
<h2>Seite {i+1}</h2>
{paragraphs}
</body>
</html>"""
            epub.writestr(f"OEBPS/{chapter_file}", chapter_xhtml)

            manifest_items.append(
                f'<item id="{chapter_id}" href="{chapter_file}" media-type="application/xhtml+xml"/>'
            )
            spine_items.append(f'<itemref idref="{chapter_id}"/>')
            nav_points.append(
                f'<navPoint id="navpoint-{i+1}" playOrder="{i+1}">'
                f'<navLabel><text>Seite {i+1}</text></navLabel>'
                f'<content src="{chapter_file}"/></navPoint>'
            )

        doc.close()

        content_opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{xml_escape(title)}</dc:title>
    <dc:language>de</dc:language>
    <dc:identifier id="BookId">urn:uuid:{title}-{datetime.now().strftime('%Y%m%d%H%M%S')}</dc:identifier>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    {"".join(manifest_items)}
  </manifest>
  <spine toc="ncx">
    {"".join(spine_items)}
  </spine>
</package>"""
        epub.writestr("OEBPS/content.opf", content_opf)

        toc_ncx = f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head/>
  <docTitle><text>{xml_escape(title)}</text></docTitle>
  <navMap>
    {"".join(nav_points)}
  </navMap>
</ncx>"""
        epub.writestr("OEBPS/toc.ncx", toc_ncx)

    return True

def convert_pdf_to_epub(pdf_path: Path, epub_path: Path) -> bool:
    """
    Konvertiert ein durchsuchbares PDF in ein einfaches ePub.
    Jede PDF-Seite wird zu einem eigenen Kapitel.

    Rückgabe: True bei Erfolg, False wenn PDF nicht durchsuchbar oder Fehler auftrat.
    """
    if not is_searchable_pdf(pdf_path):
        return False

    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        return False

    title = pdf_path.stem

    epub_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(str(epub_path), "w", compression=zipfile.ZIP_DEFLATED) as epub:
        epub.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)

        container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""
        epub.writestr("META-INF/container.xml", container_xml)

        manifest_items = []
        spine_items = []
        nav_points = []

        for i in range(doc.page_count):
            page_text = str(doc[i].get_text()).strip()
            chapter_id = f"page-{i+1}"
            chapter_file = f"page_{i+1}.xhtml"

            paragraphs = "\n".join(
                f"<p>{xml_escape(p)}</p>" for p in page_text.split("\n\n") if p.strip()
            )

            chapter_xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
            <html xmlns="http://www.w3.org/1999/xhtml">
            <head>
            <title>Seite {i+1}</title>
            <style>
            pre {{ white-space: pre-wrap; font-family: serif; font-size: 1em; }}
            </style>
            </head>
            <body>
            <h2>Seite {i+1}</h2>
            <pre>{xml_escape(page_text)}</pre>
            </body>
            </html>"""
            epub.writestr(f"OEBPS/{chapter_file}", chapter_xhtml)

            manifest_items.append(
                f'<item id="{chapter_id}" href="{chapter_file}" media-type="application/xhtml+xml"/>'
            )
            spine_items.append(f'<itemref idref="{chapter_id}"/>')
            nav_points.append(
                f'<navPoint id="navpoint-{i+1}" playOrder="{i+1}">'
                f'<navLabel><text>Seite {i+1}</text></navLabel>'
                f'<content src="{chapter_file}"/></navPoint>'
            )

        doc.close()

        content_opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{xml_escape(title)}</dc:title>
    <dc:language>de</dc:language>
    <dc:identifier id="BookId">urn:uuid:{title}-{datetime.now().strftime('%Y%m%d%H%M%S')}</dc:identifier>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    {"".join(manifest_items)}
  </manifest>
  <spine toc="ncx">
    {"".join(spine_items)}
  </spine>
</package>"""
        epub.writestr("OEBPS/content.opf", content_opf)

        toc_ncx = f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head/>
  <docTitle><text>{xml_escape(title)}</text></docTitle>
  <navMap>
    {"".join(nav_points)}
  </navMap>
</ncx>"""
        epub.writestr("OEBPS/toc.ncx", toc_ncx)

    return True

def convert_pdfs_in_dir(
    master_dir: Path,
    status_callback: Optional[Callable[[str], None]] = None,
) -> tuple[int, int, int]:
    """
    Durchsucht master_dir (nicht rekursiv nötig? -> hier: rekursiv wie sync) nach PDFs
    ohne gleichnamiges ePub und konvertiert sie.

    Rückgabe: (konvertiert, übersprungen_da_vorhanden, übersprungen_da_nicht_durchsuchbar)
    """
    converted = 0
    skipped_existing = 0
    skipped_not_searchable = 0

    for pdf_file in master_dir.rglob("*.pdf"):
        epub_file = pdf_file.with_suffix(".epub")

        if epub_file.exists():
            skipped_existing += 1
            continue

        if status_callback:
            status_callback(f"Konvertiere: {pdf_file.name}")

        success = convert_pdf_to_epub(pdf_file, epub_file)
        if success:
            converted += 1
        else:
            skipped_not_searchable += 1

    return converted, skipped_existing, skipped_not_searchable