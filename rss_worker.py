#!/usr/bin/env python3
"""
RSS-Worker für eNews
- Liest aktivierte Feeds
- Lädt RSS/Atom mit feedparser (robust gegen bozo-Feeds via requests + lxml)
- Extrahiert Titel, Link, Datum, Content
- Bereinigt HTML zu FlieÃ¿text mit BeautifulSoup
"""

from __future__ import annotations

import re
from datetime import datetime
from html import unescape
from typing import Any, Dict, List, Optional

import feedparser
import requests
from bs4 import BeautifulSoup
from lxml import etree  # type: ignore[import-untyped]

# Optional: benutzerdefinierter User-Agent, falls Feeds blockieren
DEFAULT_USER_AGENT = "eNews-Reader/1.0 (Windows; RSS client)"


def html_to_text(html: Optional[str]) -> str:
    """Wandelt HTML in sauberen FlieÃ¿text um."""
    if not html:
        return ""
    html = unescape(html)
    soup = BeautifulSoup(html, "lxml")

    # Skripte, Styles, Header/Footer etc. entfernen
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()

    # Absätze und Zeilenumbrücke sinnvoll behandeln
    text = soup.get_text(separator="\n", strip=True)

    # Mehrfache Leerzeilen zusammenfassen
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def parse_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Extrahiert aus einem feedparser-Eintrag eine einheitliche Struktur."""
    title = entry.get("title", "")
    link = ""

    # Link-Priorität: enclosure > link > id
    if "link" in entry:
        link = entry["link"]
    elif "id" in entry:
        link = entry["id"]
    elif "enclosures" in entry and entry["enclosures"]:
        link = entry["enclosures"][0].get("href", "")

    # Datum
    published = None
    if "published_parsed" in entry and entry["published_parsed"]:
        try:
            published = datetime(*entry["published_parsed"][:6]).isoformat()
        except Exception:
            pass
    elif "updated_parsed" in entry and entry["updated_parsed"]:
        try:
            published = datetime(*entry["updated_parsed"][:6]).isoformat()
        except Exception:
            pass

    # Content: content > summary > description > title-only
    content_html = ""
    if "content" in entry and entry["content"]:
        # content ist Liste von {"value": "...", "type": "..."}
        content_html = entry["content"][0].get("value", "")
    elif "summary" in entry:
        content_html = entry["summary"]
    elif "description" in entry:
        content_html = entry["description"]

    content_text = html_to_text(content_html)

    # Fallback: wenn kein Content, aber Title, mindestens Title als Text
    if not content_text.strip() and title:
        content_text = title

    return {
        "title": title or "(ohne Titel)",
        "link": link,
        "published": published,
        "content": content_text,
    }


def fetch_feed(url: str, keyword: str) -> Dict[str, Any]:
    """Lädt einen einzelnen Feed und gibt strukturierte Daten zurück."""
    # Erster Versuch: normal mit feedparser
    parser = feedparser.parse(url, agent=DEFAULT_USER_AGENT)

    # Wenn bozo und keine Entries, versuche robusten Download mit requests + lxml
    if parser.bozo and not parser.entries:
        try:
            resp = requests.get(url, headers={"User-Agent": DEFAULT_USER_AGENT}, timeout=10)
            resp.raise_for_status()
            raw_data = resp.content

            # Versuche, das XML mit lxml zu parsen (repariert oft kleine Fehler)
            # recover=True erlaubt fehlerhaftes XML
            recovered = etree.fromstring(raw_data, parser=etree.XMLParser(recover=True, encoding="utf-8"))
            recovered_data = etree.tostring(recovered, encoding="utf-8", xml_declaration=True, method="xml")

            parser = feedparser.parse(recovered_data)
        except Exception as e:
            # Wenn auch das fehlschlägt, bleiben wir beim ursprünglichen Fehler
            return {
                "keyword": keyword,
                "url": url,
                "error": e,
                "items": [],
            }

    # Fallback: wenn immer noch bozo und keine Entries, melden wir den Fehler
    if parser.bozo and not parser.entries:
        return {
            "keyword": keyword,
            "url": url,
            "error": getattr(parser, "bozo_exception", None),
            "items": [],
        }

    feed_title = parser.feed.get("title", keyword)

    items = []
    for entry in parser.entries:
        item = parse_entry(entry)
        items.append(item)

    return {
        "keyword": keyword,
        "url": url,
        "feed_title": feed_title,
        "items": items,
    }


def fetch_feeds(feeds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Lädt alle aktivierten Feeds.

    feeds: Liste von {"enabled": bool, "keyword": str, "url": str}
    Rückgabe: Liste von {"keyword", "url", "feed_title"?, "items": [...], "error"?}
    """
    results = []
    for f in feeds:
        if not f.get("enabled", True):
            continue
        keyword = f.get("keyword", "").strip() or "Unbenannt"
        url = f.get("url", "").strip()
        if not url:
            continue
        result = fetch_feed(url, keyword)
        results.append(result)
    return results


if __name__ == "__main__":
    # Kleiner Test-Block, falls man das Script direkt aufruft
    test_feeds = [
        {
            "enabled": True,
            "keyword": "Heise",
            "url": "https://www.heise.de/rss/heise-atom.xml",
        },
        {
            "enabled": True,
            "keyword": "Tagesschau",
            "url": "https://www.tagesschau.de/xml/rss2/",
        },
    ]
    data = fetch_feeds(test_feeds)
    for feed in data:
        print(f"Feed: {feed['keyword']} ({feed.get('feed_title', '?')})")
        if "error" in feed:
            print(f"  Fehler: {feed['error']}")
        else:
            print(f"  Items: {len(feed['items'])}")
            for i, item in enumerate(feed["items"][:3], 1):
                print(f"    {i}. {item['title']}")
                print(f"       {item['published'] or 'kein Datum'}")
                print(f"       {len(item['content'])} Zeichen")
        print()