#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
epub_normalizer.py - reine Logik (ohne GUI, ohne Fremdlibrary) zum Aufraeumen von ePubs.

CLI-Test:
  python epub_normalizer.py buch.epub out.epub --style p --min-sentences 10 --indent 0
  python epub_normalizer.py kapitel.xhtml out.xhtml --css book.css
"""
import os
import posixpath
import re
import shutil
import sys
import zipfile
from html import escape, unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree as ET

CSS_NAME = "enb_normalized.css"
BACKUP_DIR = ".backup"
SUFFIX = "_reformat"

DEFAULTS = {
    "style": "p",             # "p" = ein <p> je Absatz, "div" = Fliesstext in einer Div
    "fix_mojibake": True,     # Ã¼ -> ü usw.
    "typography": True,       # " - " -> Gedankenstrich, ... -> Auslassungspunkte usw.
    "merge_broken": True,     # mitten im Satz getrennte Absaetze zusammenfuehren
    "min_sentences": 10,      # Fliesstext: Absatz fruehestens nach N Saetzen (1 = aus)
    "max_chars": 2000,        # Obergrenze, damit keine Textwaende entstehen
    "keep_gaps": True,        # Abschnittsabstaende des Originals als genau 1 Leerzeile
    "indent": "1.2em",        # Erstzeileneinzug ("0" = keiner)
    "indent_first": True,     # auch der erste Absatz nach einer Ueberschrift eingerueckt
    "mode": "replace",        # "replace" (Backup nach .backup) oder "suffix" (_reformat.epub)
}

class EpubError(Exception):
    pass

# ---------------------------------------------------------------- Mojibake
def _cont_chars():
    out = []
    for b in range(0x80, 0xC0):
        try:
            out.append(bytes([b]).decode("cp1252"))
        except UnicodeDecodeError:
            out.append(chr(b))
    return "".join(re.escape(c) for c in out)

_C = _cont_chars()
_MOJI = re.compile(
    r"[\u00c2-\u00df][%s]|[\u00e0-\u00ef][%s]{2}|[\u00f0-\u00f4][%s]{3}" % (_C, _C, _C)
)

def _moji_repl(m):
    seq = m.group(0)
    try:
        raw = bytearray()
        for ch in seq:
            try:
                raw += ch.encode("cp1252")
            except UnicodeEncodeError:
                raw += ch.encode("latin-1")
        return bytes(raw).decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return seq

def fix_mojibake(text, stats=None):
    new, n = _MOJI.subn(_moji_repl, text)
    if stats is not None and new != text:
        stats["mojibake"] = stats.get("mojibake", 0) + n
    return new

_LIG = {"\ufb01": "fi", "\ufb02": "fl", "\ufb00": "ff", "\ufb03": "ffi", "\ufb04": "ffl"}
_INVIS = dict.fromkeys(map(ord, "\u00ad\u200b\u200c\u200d\u2060\ufeff"), None)

def clean_chars(s):
    s = s.translate(_INVIS).replace("\u00a0", " ").replace("\u2009", " ").replace("\u202f", " ")
    for k, v in _LIG.items():
        s = s.replace(k, v)
    return s

def typography(h):
    h = re.sub(r"(?<=\s)-(?=\s)", "\u2013", h)          # " - " -> " – "
    h = h.replace("...", "\u2026")
    h = re.sub(r"&gt;([^&<>]{1,80}?)&lt;", "\u203a\\1\u2039", h)  # >Wort< -> ›Wort‹
    h = re.sub(r"\s+([,.;:!?])", r"\1", h)
    return h

# ---------------------------------------------------------------- CSS
def parse_css(text):
    rules = {}
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", text):
        props = {}
        for d in body.split(";"):
            if ":" in d:
                k, v = d.split(":", 1)
                props[k.strip().lower()] = v.strip().lower()
        for s in sel.split(","):
            m = re.fullmatch(r"\s*(?:[a-z0-9]+)?\.([\w-]+)\s*", s)
            if m:
                rules.setdefault(m.group(1), {}).update(props)
    return rules

def class_props(rules, classes):
    p = {}
    for c in classes:
        p.update(rules.get(c, {}))
    return p

def _is_bold(p):
    v = p.get("font-weight", "")
    return v in ("bold", "bolder") or (v.isdigit() and int(v) >= 600)

def _is_italic(p):
    return p.get("font-style", "") in ("italic", "oblique")

def _has_gap(p):
    v = p.get("margin-bottom", "")
    m = re.match(r"([\d.]+)\s*(%|em|px|pt|rem)", v)
    if not m:
        return False
    x, u = float(m.group(1)), m.group(2)
    return (u == "%" and x >= 5) or (u in ("em", "rem") and x >= 1.2) or (u in ("px", "pt") and x >= 20)

# ---------------------------------------------------------------- Parser
BLOCK = {"div", "p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote",
         "pre", "section", "article", "center"}
UNSAFE = {"table", "svg", "math", "ul", "ol", "object", "audio", "video"}
INLINE = {"b": "strong", "strong": "strong", "i": "em", "em": "em", "sup": "sup", "sub": "sub"}
DIALOG = ("\u2013", "\u2014", "-", "\u00bb", "\u201e", "\u201c", "\u203a", "\u2022", "*",
          "\u00ab", "\u201a", '"')
TERMINAL = tuple('.!?\u2026:;"\u201c\u201d\u00bb\u00ab\u203a\u2039)]\'\u2019')

def _plain(h):
    return unescape(re.sub(r"<[^>]+>", "", h)).strip()

class _Parser(HTMLParser):
    def __init__(self, rules, opts, stats):
        super().__init__(convert_charrefs=True)
        self.rules, self.opts, self.stats = rules, opts, stats
        self.blocks, self.cur = [], None
        self.inl = []
        self.in_body = False
        self.in_title = False
        self.skip = 0
        self.title = ""
        self.lang = "de"
        self.unsafe = False

    def _txt(self, s):
        if self.opts["fix_mojibake"]:
            s = fix_mojibake(s, self.stats)
        return clean_chars(s)

    def _ensure(self):
        if self.cur is None:
            self.cur = {"tag": "p", "cls": [], "html": [], "br": False}

    def _flush(self):
        if self.cur is None:
            self.inl = []
            return
        for _, close in reversed(self.inl):
            self.cur["html"].append(close)
        self.inl = []
        h = re.sub(r"\s+", " ", "".join(self.cur["html"])).strip()
        if self.opts["typography"]:
            h = typography(h)
        pl = _plain(h)
        if pl:
            self.blocks.append({"kind": "p", "tag": self.cur["tag"], "cls": self.cur["cls"],
                                "html": h, "plain": pl})
        else:
            self.stats["empty"] = self.stats.get("empty", 0) + 1
        self.cur = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in UNSAFE:
            self.unsafe = True
        if tag == "html":
            self.lang = a.get("xml:lang") or a.get("lang") or "de"
        elif tag == "title":
            self.in_title = True
        elif tag in ("style", "script"):
            self.skip += 1
        elif tag == "body":
            self.in_body = True
        if not self.in_body:
            return
        if tag in BLOCK:
            self._flush()
            self.cur = {"tag": tag, "cls": a.get("class", "").split(), "html": [], "br": False}
        elif tag == "br":
            if self.cur is not None and self.cur["br"]:
                self._flush()
            elif self.cur is not None:
                self.cur["html"].append(" ")
                self.cur["br"] = True
        elif tag == "img":
            self._flush()
            self.blocks.append({"kind": "img", "src": a.get("src", ""), "alt": a.get("alt", "")})
        elif tag in INLINE:
            self._ensure()
            self.cur["html"].append("<%s>" % INLINE[tag])
            self.inl.append((tag, "</%s>" % INLINE[tag]))
        elif tag == "span":
            self._ensure()
            p = class_props(self.rules, a.get("class", "").split())
            op, cl = "", ""
            if _is_bold(p):
                op, cl = op + "<strong>", "</strong>" + cl
            if _is_italic(p):
                op, cl = op + "<em>", "</em>" + cl
            self.cur["html"].append(op)
            self.inl.append(("span", cl))

    def handle_startendtag(self, tag, attrs):
        if tag in ("br", "img"):
            self.handle_starttag(tag, attrs)
        else:
            self.handle_starttag(tag, attrs)
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag in ("style", "script"):
            self.skip = max(0, self.skip - 1)
        if not self.in_body:
            return
        if tag == "body":
            self._flush()
            self.in_body = False
        elif tag in BLOCK:
            self._flush()
        elif tag in INLINE or tag == "span":
            for i in range(len(self.inl) - 1, -1, -1):
                if self.inl[i][0] == tag:
                    if self.cur:
                        self.cur["html"].append(self.inl[i][1])
                    del self.inl[i]
                    break

    def handle_data(self, d):
        if self.skip:
            return
        if self.in_title:
            self.title += d
            return
        if not self.in_body:
            return
        t = self._txt(d)
        if self.cur is None and not t.strip():
            return
        self._ensure()
        if t.strip():
            self.cur["br"] = False
        self.cur["html"].append(escape(t, quote=False))

# ---------------------------------------------------------------- Saetze / Dialog
_ABBR = {"dr", "prof", "nr", "st", "bzw", "usw", "ca", "vgl", "hr", "fr", "mr", "mrs", "mt",
         "jr", "sr", "etc", "evtl", "ggf", "inkl", "max", "min", "tel", "str", "geb", "gest",
         "abb", "bd", "kap", "vs", "al", "sog", "std", "mio", "mrd", "jh", "ev", "kath"}
_TERM = re.compile(r"([.!?\u2026]+)([\"\u201c\u201d\u00bb\u00ab\u203a\u2039)\]'\u2019]*)(?=\s+\S|\s*$)")

def count_sentences(t):
    n = 0
    for m in _TERM.finditer(t):
        if m.group(1) == ".":
            w = re.search(r"(\w+)$", t[:m.start()])
            word = w.group(1).lower() if w else ""
            if word in _ABBR or word.isdigit() or (len(word) == 1 and word.isalpha()):
                continue
            nxt = t[m.end():].lstrip()[:1]
            if nxt and nxt.islower():
                continue
        n += 1
    return max(n, 1)

def is_dialog(plain):
    return plain.startswith(DIALOG)

# ---------------------------------------------------------------- Umbau
_SB = re.compile(r"^[\*\-\u2013\u2014_=\u2022~#\s]{3,}$")

def _classify(blocks, rules, opts):
    paras = []
    for i, b in enumerate(blocks):
        if b["kind"] != "p":
            continue
        pr = class_props(rules, b["cls"])
        pl = b["plain"]
        term = pl.endswith(TERMINAL)
        if _SB.match(pl):
            b["kind"] = "sb"
            b["html"] = "* * *"
            continue
        if b["tag"] in ("h1", "h2", "h3", "h4", "h5", "h6") or \
           (_is_bold(pr) and len(pl) < 120 and not term) or \
           (i == 0 and len(pl) < 80 and not term):
            b["kind"] = "h"
            continue
        b["gap"] = _has_gap(pr)
        if _is_italic(pr) and not b["html"].startswith("<em>"):
            b["html"] = "<em>%s</em>" % b["html"]
        paras.append(b)
    if paras:
        share = sum(1 for p in paras if p["gap"]) / len(paras)
        if share > 0.3 or not opts["keep_gaps"]:
            for p in paras:
                p["gap"] = False
    return blocks

def _merge(blocks, stats):
    """Satz endet nicht -> Fortsetzung im naechsten Block (Gross/Klein egal, deutsch!)."""
    out = []
    for b in blocks:
        prev = out[-1] if out else None
        if (prev and prev["kind"] == "p" and b["kind"] == "p" and not prev.get("gap")
                and len(prev["plain"]) >= 40 and not prev["plain"].endswith(TERMINAL)
                and not b["plain"].startswith(DIALOG)):
            if prev["plain"].endswith("-") and len(prev["plain"]) > 1 and prev["plain"][-2].isalpha():
                prev["html"] = prev["html"].rstrip("-") + b["html"]
            else:
                prev["html"] += " " + b["html"]
            prev["plain"] = _plain(prev["html"])
            prev["gap"] = b.get("gap", False)
            stats["merged"] = stats.get("merged", 0) + 1
        else:
            out.append(b)
    return out

def _regroup(blocks, min_sent, max_chars, stats):
    """Fliesstext-Absaetze sammeln, bis min_sent Saetze erreicht sind.
    Umbruch erzwingen: Dialog (davor/danach), Ueberschrift/Szenenwechsel/Bild, Original-Abstand."""
    out, cur = [], None
    for b in blocks:
        if b["kind"] != "p":
            if cur:
                out.append(cur)
                cur = None
            out.append(b)
            continue
        b["dlg"] = is_dialog(b["plain"])
        b["n"] = count_sentences(b["plain"])
        if cur is None:
            cur = b
            continue
        too_long = len(cur["plain"]) + len(b["plain"]) > max_chars
        if b["dlg"] or cur["dlg"] or cur["n"] >= min_sent or cur.get("gap") or too_long:
            out.append(cur)
            cur = b
        else:
            cur["html"] += " " + b["html"]
            cur["plain"] = cur["plain"] + " " + b["plain"]
            cur["n"] += b["n"]
            cur["gap"] = b.get("gap", False)
            stats["regrouped"] = stats.get("regrouped", 0) + 1
    if cur:
        out.append(cur)
    return out

CSS_TEXT = """body { margin: 0; padding: 0; }
h1, h2, h3 { font-weight: bold; text-align: center; margin: 1.2em 0 0.8em 0; page-break-after: avoid; }
h1 { font-size: 1.4em; }
h2 { font-size: 1.2em; }
p { margin: 0; padding: 0; text-indent: %(indent)s; text-align: justify; }
p.f { text-indent: 0; }
p.gap { margin-bottom: 1em; }
p.sb { text-align: center; text-indent: 0; margin: 1em 0; }
div.body { margin: 0; padding: 0; text-align: justify; }
img { max-width: 100%%; }
"""

def build_css(opts):
    return CSS_TEXT % {"indent": opts["indent"]}

def _render(blocks, title, lang, css_href, opts):
    o = []
    first_h = True
    after_h = True
    div_open = False
    div_style = opts["style"] == "div"
    n = len(blocks)
    for i, b in enumerate(blocks):
        k = b["kind"]
        nxt = blocks[i + 1]["kind"] if i + 1 < n else None
        if k != "p" and div_open:
            o.append("</div>")
            div_open = False
        if k == "h":
            t = "h1" if first_h else "h2"
            first_h = False
            o.append("<%s>%s</%s>" % (t, b["html"], t))
            after_h = True
        elif k == "sb":
            o.append('<p class="sb">%s</p>' % b["html"])
            after_h = True
        elif k == "img":
            o.append('<p class="sb"><img src="%s" alt="%s" /></p>' % (escape(b["src"]), escape(b["alt"])))
        else:
            gap = b.get("gap") and i + 1 < n and nxt != "sb"
            if div_style:
                if not div_open:
                    o.append('<div class="body">')
                    div_open = True
                ind = "" if opts["indent"] in ("0", "none") else "\u2003"
                o.append(ind + b["html"] + "<br />" + ("<br />" if gap else ""))
            else:
                cls = " ".join(c for c in ("f" if after_h and not opts["indent_first"] else "",
                                           "gap" if gap else "") if c)
                o.append("<p%s>%s</p>" % (' class="%s"' % cls if cls else "", b["html"]))
            after_h = False
    if div_open:
        o.append("</div>")
    body = "\n".join(o)
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"\n'
        '  "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="%s">\n<head>\n'
        '  <title>%s</title>\n'
        '  <link href="%s" rel="stylesheet" type="text/css" />\n</head>\n<body>\n%s\n</body>\n</html>\n'
        % (escape(lang), escape(title.strip()), escape(css_href), body)
    )

def normalize_xhtml(raw, rules, css_href, opts=None, stats=None):
    """Liefert neues XHTML als bytes oder None, wenn die Datei unveraendert bleiben soll."""
    opts = {**DEFAULTS, **(opts or {})}
    stats = stats if stats is not None else {}
    text = raw.decode("utf-8-sig", errors="replace")
    p = _Parser(rules, opts, stats)
    p.feed(text)
    p.close()
    p._flush()
    if p.unsafe:
        stats["skipped_complex"] = stats.get("skipped_complex", 0) + 1
        return None
    stats["blocks_in"] = stats.get("blocks_in", 0) + len(p.blocks)
    if sum(len(b.get("plain", "")) for b in p.blocks) < 100 and any(b["kind"] == "img" for b in p.blocks):
        return None  # Cover / Bildseite
    if not p.blocks:
        return None
    blocks = _classify(p.blocks, rules, opts)
    if opts["merge_broken"]:
        blocks = _merge(blocks, stats)
    if opts["min_sentences"] > 1:
        blocks = _regroup(blocks, opts["min_sentences"], opts["max_chars"], stats)
    stats["blocks_out"] = stats.get("blocks_out", 0) + len(blocks)
    title = fix_mojibake(p.title) if opts["fix_mojibake"] else p.title
    return _render(blocks, title, p.lang, css_href, opts).encode("utf-8")

# ---------------------------------------------------------------- ePub
def _local(tag):
    return tag.rsplit("}", 1)[-1]

def _find_opf(z):
    root = ET.fromstring(z.read("META-INF/container.xml"))
    for el in root.iter():
        if _local(el.tag) == "rootfile" and el.get("full-path"):
            return el.get("full-path")
    raise EpubError("Kein OPF in container.xml gefunden")

def normalize_epub(src, dst, opts=None, progress=None):
    """Schreibt ein normalisiertes ePub nach dst. Gibt Statistik-Dict zurueck."""
    opts = {**DEFAULTS, **(opts or {})}
    stats = {"docs": 0, "docs_changed": 0}
    with zipfile.ZipFile(src) as zin:
        names = zin.namelist()
        if "META-INF/encryption.xml" in names:
            raise EpubError("DRM/Verschluesselung erkannt - uebersprungen")
        opf_path = _find_opf(zin)
        opf_dir = posixpath.dirname(opf_path)
        opf_bytes = zin.read(opf_path)
        if b"pre-paginated" in opf_bytes:
            raise EpubError("Fixed-Layout-ePub - uebersprungen")
        css_path = posixpath.join(opf_dir, CSS_NAME)
        if css_path in names:
            raise EpubError("Bereits normalisiert - uebersprungen")
        root = ET.fromstring(opf_bytes)
        docs, rules = [], {}
        for el in root.iter():
            if _local(el.tag) != "item":
                continue
            mt, href = el.get("media-type", ""), unquote(el.get("href", ""))
            full = posixpath.normpath(posixpath.join(opf_dir, href))
            if full not in names:
                continue
            if mt == "text/css":
                rules.update(parse_css(zin.read(full).decode("utf-8-sig", errors="replace")))
            elif mt in ("application/xhtml+xml", "text/html") and "nav" not in el.get("properties", ""):
                docs.append(full)
        new_docs = {}
        for i, d in enumerate(docs):
            if progress:
                progress(i + 1, len(docs), d)
            stats["docs"] += 1
            href = posixpath.relpath(css_path, posixpath.dirname(d) or ".")
            res = normalize_xhtml(zin.read(d), rules, href, opts, stats)
            if res is not None:
                new_docs[d] = res
                stats["docs_changed"] += 1
        if not new_docs:
            raise EpubError("Nichts zu konvertieren")
        ot = opf_bytes.decode("utf-8-sig")
        item = '<item id="enb-css" href="%s" media-type="text/css"/>' % CSS_NAME
        ot, n = re.subn(r"(</(?:\w+:)?manifest>)", item + r"\1", ot, count=1)
        if n == 0:
            raise EpubError("Manifest im OPF nicht gefunden")
        tmp = str(dst) + ".tmp"
        with zipfile.ZipFile(tmp, "w") as zout:
            zout.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
            for nme in names:
                if nme == "mimetype" or nme.endswith("/"):
                    continue
                if nme == opf_path:
                    data = ot.encode("utf-8")
                elif nme in new_docs:
                    data = new_docs[nme]
                else:
                    data = zin.read(nme)
                zout.writestr(nme, data, compress_type=zipfile.ZIP_DEFLATED)
            zout.writestr(css_path, build_css(opts), compress_type=zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(tmp) as chk:   # Verifikation
        if chk.testzip() is not None:
            raise EpubError("Ausgabe-ZIP defekt")
        for nme in new_docs:
            ET.fromstring(chk.read(nme))
    os.replace(tmp, dst)
    return stats

def iter_epubs(master):
    for dp, dns, fns in os.walk(master):
        dns[:] = [d for d in dns if not d.startswith(".")]
        for f in fns:
            if f.lower().endswith(".epub") and not Path(f).stem.endswith(SUFFIX):
                yield Path(dp) / f

def convert_file(path, master, opts=None, progress=None):
    """Konvertiert eine Datei im Master. Backup nach <master>/.backup/<relativer Pfad>."""
    opts = {**DEFAULTS, **(opts or {})}
    path, master = Path(path), Path(master)
    if opts["mode"] == "suffix":
        dst = path.with_name(path.stem + SUFFIX + ".epub")
        return normalize_epub(path, dst, opts, progress)
    tmp = path.with_name(path.name + ".norm.tmp")
    stats = normalize_epub(path, tmp, opts, progress)
    bak = master / BACKUP_DIR / path.relative_to(master)
    if not bak.exists():                 # echtes Original nie ueberschreiben
        bak.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, bak)
    os.replace(tmp, path)
    return stats

# ---------------------------------------------------------------- CrossPoint-Cache
def crosspoint_cache_id(reader_path):
    """Ordnername .crosspoint/epub_<id> = libstdc++ std::hash<std::string> (32 Bit) des
    Pfads auf der SD-Karte, z. B. '/Dick, Phillip K/Buch.epub' (UTF-8, mit fuehrendem '/')."""
    M = 0xFFFFFFFF
    data = reader_path.encode("utf-8")
    m, ln, i = 0x5bd1e995, len(data), 0
    h = (0xc70f6907 ^ ln) & M
    while ln - i >= 4:
        k = int.from_bytes(data[i:i + 4], "little")
        k = (k * m) & M
        k ^= k >> 24
        k = (k * m) & M
        h = ((h * m) & M) ^ k
        i += 4
    r = ln - i
    if r == 3:
        h ^= data[i + 2] << 16
    if r >= 2:
        h ^= data[i + 1] << 8
    if r >= 1:
        h ^= data[i]
        h = (h * m) & M
    h ^= h >> 13
    h = (h * m) & M
    h ^= h >> 15
    return "epub_%d" % h

def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--style", default="p", choices=["p", "div"])
    ap.add_argument("--css", default="")
    ap.add_argument("--min-sentences", type=int, default=DEFAULTS["min_sentences"])
    ap.add_argument("--max-chars", type=int, default=DEFAULTS["max_chars"])
    ap.add_argument("--indent", default=DEFAULTS["indent"])
    a = ap.parse_args(argv)
    o = {"style": a.style, "min_sentences": a.min_sentences, "max_chars": a.max_chars, "indent": a.indent}
    if a.src.lower().endswith((".xhtml", ".html", ".htm", ".txt")):
        rules = parse_css(Path(a.css).read_text("utf-8", "replace")) if a.css else {}
        st = {}
        out = normalize_xhtml(Path(a.src).read_bytes(), rules, CSS_NAME, {**DEFAULTS, **o}, st)
        Path(a.dst).write_bytes(out or b"")
        Path(a.dst).with_name(CSS_NAME).write_text(build_css({**DEFAULTS, **o}), "utf-8")
    else:
        st = normalize_epub(a.src, a.dst, o)
    print(st)

if __name__ == "__main__":
    main(sys.argv[1:])
