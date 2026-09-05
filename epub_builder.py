#!/usr/bin/env python3
"""
Minimaler ePub-Builder für eNews (ohne externe Libraries)
- Baut ePub-Struktur selbst (ZIP mit XML/HTML)
- Pro Feed ein Chapter (Schlagwort als Überschrift)
- Items mit Titel, Datum, Content, Link
- Detailliertes Inhaltsverzeichnis mit Links zu jedem Artikel
- "ZurÃ¼ck zum Anfang"-Link nach jedem Kapitel

EPUB-Struktur:
- mimetype
- META-INF/container.xml
- OEBPS/content.opf
- OEBPS/toc.ncx
- OEBPS/nav.xhtml
- OEBPS/cover.xhtml
- OEBPS/toc_content.xhtml (detailliertes Inhaltsverzeichnis mit Links zu Artikeln)
- OEBPS/chapter_*.xhtml
"""

from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def xml_escape(text: str) -> str:
    """Escapt Sonderzeichen für XML/HTML."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def first_sentence(text: str, max_len: int = 80) -> str:
    """Extrahiert den ersten Satz oder die erste Zeile aus Text."""
    if not text:
        return ""
    # Ersten Absatz nehmen
    para = text.split("\n\n")[0].strip()
    if len(para) > max_len:
        para = para[:max_len].rsplit(" ", 1)[0] + "…"
    return para


def build_epub(
    results: List[Dict[str, Any]],
    output_path: Path,
    title: Optional[str] = None,
) -> None:
    """
    Erzeugt eine ePub-Datei aus RSS-Ergebnissen.

    results: Liste von {"keyword", "url", "feed_title", "items": [...], "error"?}
    output_path: Pfad zur Ausgabedatei (.epub)
    title: Buchtitel (Default: "eNews YYYY-MM-DD")
    """
    if title is None:
        title = f"eNews {datetime.now().strftime('%Y-%m-%d')}"

    # Filtere fehlerhafte Feeds
    valid_feeds = [f for f in results if "error" not in f and f.get("items")]

    # Kapitel-Dateinamen und IDs sammeln
    chapters: List[Dict[str, Any]] = []
    for feed in valid_feeds:
        keyword = feed.get("keyword", "Unbenannt")
        chapter_file = f"chapter_{keyword.lower().replace(' ', '_').replace('.', '').replace('-', '')}.xhtml"
        chapter_id = f"chapter-{keyword.lower().replace(' ', '-').replace('.', '').replace('-', '')}"
        chapters.append({
            "keyword": keyword,
            "file": chapter_file,
            "id": chapter_id,
            "items": feed.get("items", []),
        })

    # ZIP-Datei erstellen
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(str(output_path), "w", compression=zipfile.ZIP_DEFLATED) as epub:
        # 1. mimetype (MUSS unkomprimiert und als erste Datei)
        epub.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)

        # 2. META-INF/container.xml
        container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""
        epub.writestr("META-INF/container.xml", container_xml)

        # 3. OEBPS/content.opf
        manifest_items = [
            '  <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
            '  <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
            '  <item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>',
            '  <item id="toc_content" href="toc_content.xhtml" media-type="application/xhtml+xml"/>',
        ]
        spine_items = [
            '<itemref idref="cover"/>',
            '<itemref idref="toc_content"/>',
        ]

        for ch in chapters:
            manifest_items.append(f'  <item id="{ch["id"]}" href="{ch["file"]}" media-type="application/xhtml+xml"/>')
            spine_items.append(f'<itemref idref="{ch["id"]}"/>')

        content_opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="uid">{title.replace(' ', '-').lower()}-{datetime.now().strftime('%Y%m%d')}</dc:identifier>
    <dc:title>{xml_escape(title)}</dc:title>
    <dc:language>de</dc:language>
    <dc:creator>eNews Generator</dc:creator>
    <meta property="dcterms:modified">{datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')}</meta>
  </metadata>
  <manifest>
{chr(10).join(manifest_items)}
  </manifest>
  <spine toc="ncx">
{chr(10).join(spine_items)}
  </spine>
</package>
"""
        epub.writestr("OEBPS/content.opf", content_opf)

        # 4. OEBPS/toc.ncx (mit Links zu Kapiteln, nicht zu Artikeln)
        nav_points = []
        for i, ch in enumerate(chapters, 1):
            nav_points.append(f"""    <navPoint id="navpoint-{i}" playOrder="{i}">
      <navLabel><text>{xml_escape(ch["keyword"])}</text></navLabel>
      <content src="{ch["file"]}"/>
    </navPoint>""")

        toc_ncx = f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx version="2005-1" xmlns="http://www.daisy.org/z3986/2005/ncx/">
  <head>
    <meta name="dtb:uid" content="{title.replace(' ', '-').lower()}-{datetime.now().strftime('%Y%m%d')}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>{xml_escape(title)}</text></docTitle>
  <navMap>
{chr(10).join(nav_points)}
  </navMap>
</ncx>
"""
        epub.writestr("OEBPS/toc.ncx", toc_ncx)

        # 5. OEBPS/nav.xhtml (EPUB3 Navigation)
        nav_links = []
        for ch in chapters:
            nav_links.append(f'      <li><a href="{ch["file"]}">{xml_escape(ch["keyword"])}</a></li>')

        nav_xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
  <title>{xml_escape(title)}</title>
  <style>
    body {{ font-family: sans-serif; margin: 1em; }}
    nav ol {{ list-style: none; padding-left: 0; }}
    nav li {{ margin: 0.5em 0; }}
  </style>
</head>
<body>
  <nav epub:type="toc">
    <h1>Inhaltsverzeichnis</h1>
    <ol>
{chr(10).join(nav_links)}
    </ol>
  </nav>
</body>
</html>
"""
        epub.writestr("OEBPS/nav.xhtml", nav_xhtml)

        # 6. OEBPS/cover.xhtml
        cover_xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <title>Cover</title>
  <style>
    body {{ text-align: center; margin: 0; padding: 0; font-family: sans-serif; }}
    h1 {{ font-size: 2em; margin-top: 2em; }}
    p {{ font-size: 1.2em; margin-top: 1em; }}
  </style>
</head>
<body>
  <h1>{xml_escape(title)}</h1>
  <p>Erstellt am {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
  <p>eNews Generator</p>
</body>
</html>
"""
        epub.writestr("OEBPS/cover.xhtml", cover_xhtml)

        # 7. OEBPS/toc_content.xhtml (detailliertes Inhaltsverzeichnis mit Links zu jedem Artikel)
        toc_sections = []
        for ch in chapters:
            keyword = ch["keyword"]
            items = ch["items"]

            article_links = []
            for i, item in enumerate(items, 1):
                item_title = item.get("title", "(ohne Titel)")
                item_content = item.get("content", "")
                first_text = first_sentence(item_content, max_len=100)
                # Anker zum Artikel im Kapitel
                article_id = f"{ch['id']}-article-{i}"
                article_links.append(f"""        <li>
          <a href="{ch['file']}#{article_id}"><b>{xml_escape(item_title)}</b></a><br/>
          <small style="color:#666;">{xml_escape(first_text)}</small>
        </li>""")

            toc_sections.append(f"""    <section>
      <h2>{xml_escape(keyword)}</h2>
      <ul>
{chr(10).join(article_links)}
      </ul>
    </section>""")

        toc_content_xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <title>Inhaltsverzeichnis</title>
  <style>
    body {{ font-family: sans-serif; margin: 1em; line-height: 1.4; }}
    h1 {{ font-size: 1.6em; margin-bottom: 0.5em; border-bottom: 1px solid #ccc; }}
    h2 {{ font-size: 1.3em; margin-top: 1.5em; margin-bottom: 0.4em; color: #333; }}
    ul {{ list-style: none; padding-left: 0; }}
    li {{ margin: 0.6em 0; }}
    a {{ color: #0066cc; text-decoration: none; }}
    small {{ color: #666; }}
  </style>
</head>
<body>
  <h1 id="toc">Inhaltsverzeichnis</h1>
{chr(10).join(toc_sections)}
</body>
</html>
"""
        epub.writestr("OEBPS/toc_content.xhtml", toc_content_xhtml)

        # 8. OEBPS/chapter_*.xhtml
        for ch in chapters:
            keyword = ch["keyword"]
            items = ch["items"]

            html_parts = [
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<!DOCTYPE html>',
                '<html xmlns="http://www.w3.org/1999/xhtml">',
                "<head>",
                f"  <title>{xml_escape(keyword)}</title>",
                "  <style>",
                "    body { font-family: sans-serif; margin: 1em; line-height: 1.6; }",
                "    h1 { font-size: 1.8em; margin-bottom: 0.5em; border-bottom: 1px solid #ccc; }",
                "    h2 { font-size: 1.4em; margin-top: 1.5em; margin-bottom: 0.3em; }",
                "    .meta { font-size: 0.9em; color: #555; margin-bottom: 0.5em; }",
                "    p { margin-bottom: 1em; }",
                "    a { color: #0066cc; }",
                "    .backlink {{ font-size: 0.8em; color: #888; margin-top: 2em; }}",
                "  </style>",
                "  </head>",
                "<body>",
                f'  <h1 id="{ch["id"]}">{xml_escape(keyword)}</h1>',
            ]

            for i, item in enumerate(items, 1):
                item_title = item.get("title", "(ohne Titel)")
                item_link = item.get("link", "")
                item_published = item.get("published", "")
                item_content = item.get("content", "")

                # Anker für diesen Artikel
                article_id = f"{ch['id']}-article-{i}"

                html_parts.append(f'  <h2 id="{article_id}">{xml_escape(item_title)}</h2>')

                meta_parts = []
                if item_published:
                    try:
                        dt = datetime.fromisoformat(item_published)
                        meta_parts.append(dt.strftime("%Y-%m-%d %H:%M"))
                    except Exception:
                        meta_parts.append(item_published)
                if item_link:
                    meta_parts.append(f'<a href="{xml_escape(item_link)}">Link</a>')

                if meta_parts:
                    html_parts.append(f'  <p class="meta">{" | ".join(meta_parts)}</p>')

                # Content als Text mit AbsÃ¤tzen
                paragraphs = item_content.split("\n\n")
                for para in paragraphs:
                    para = para.strip()
                    if para:
                        html_parts.append(f"  <p>{xml_escape(para)}</p>")

                html_parts.append("")  # Leerzeile zwischen Items

            # "ZurÃ¼ck zum Anfang"-Link am Ende des Kapitels (mit explizitem Dateinamen)
            html_parts.append(f'  <p class="backlink"><a href="toc_content.xhtml#toc">↑ Inhaltsverzeichnis</a></p>')
            html_parts.extend([
                "</body>",
                "</html>",
            ])

            chapter_content = "\n".join(html_parts)
            epub.writestr(f"OEBPS/{ch['file']}", chapter_content)

    # Fertig