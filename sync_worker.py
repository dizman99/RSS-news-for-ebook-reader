#!/usr/bin/env python3
"""
Sync-Worker für eNews
- Synchronisiert komplettes Root-Verzeichnis zwischen PC und eReader
- PC ist Master, Reader ist Spiegel
- Funktionen:
  - pull_from_reader(reader_root, local_dir): Holt komplettes Root vom Reader auf den PC
  - sync_to_reader(local_dir, reader_root): Spiegelt PC-Root auf den Reader
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, List, Optional, Tuple

# Exclude-Liste: Diese Verzeichnisse/Dateien werden nicht synchronisiert
EXCLUDE_PATTERNS = [
    "System Volume Information",
    ".DS_Store",
    ".crosspoint",
    "$RECYCLE.BIN",
    "Thumbs.db",
    "desktop.ini",
]


def should_exclude(path: Path, base_path: Path) -> bool:
    """
    Prüft, ob ein Pfad ausgeschlossen werden soll.

    path: VollstÃ¤ndiger Pfad der Datei/des Verzeichnisses
    base_path: Basis-Pfad (Reader-Root oder Local-Dir)

    Rückgabe: True, wenn ausgeschlossen, False sonst
    """
    # Relative Pfad-Komponenten prüfen
    try:
        rel_path = path.relative_to(base_path)
    except ValueError:
        return False  # Nicht innerhalb des Basis-Pfads

    # Jede Komponente des relativen Pfads prüfen
    for part in rel_path.parts:
        if part in EXCLUDE_PATTERNS:
            return True

    return False


def is_enews_json(file_path: Path) -> bool:
    """
    Prüft, ob es sich um eine !eNews-JSON-Datei handelt.

    Rückgabe: True, wenn JSON in !eNews-Verzeichnis, False sonst
    """
    # Prüfen, ob Datei in einem !eNews-Verzeichnis liegt
    for part in file_path.parts:
        if part == "!eNews":
            # Dateiendung prüfen
            if file_path.suffix.lower() == ".json":
                return True
    return False


def files_are_identical(file1: Path, file2: Path) -> bool:
    """
    Vergleicht zwei Dateien auf IdentitÃ¤t (Größe und Modifikationszeit).

    Rückgabe: True, wenn identisch, False sonst
    """
    try:
        stat1 = file1.stat()
        stat2 = file2.stat()
        return stat1.st_size == stat2.st_size and abs(stat1.st_mtime - stat2.st_mtime) < 1.0
    except Exception:
        return False


def pull_from_reader(
    reader_root: Path,
    local_dir: Path,
    status_callback: Optional[Callable[[str], None]] = None,
) -> Tuple[int, int, str]:
    """
    Holt den kompletten Inhalt vom Reader auf den PC.

    reader_root: Root-Verzeichnis des Readers (z. B. "E:\\")
    local_dir: Zielverzeichnis auf dem PC (wird erstellt, falls nicht existent)
    status_callback: Optionaler Callback für Statusmeldungen (wird mit Dateinamen aufgerufen)

    Rückgabe: (Anzahl kopierter Dateien, Anzahl übersprungener Dateien, Statusmeldung)
    """
    if not reader_root.exists():
        return 0, 0, "Reader-Verzeichnis existiert nicht."

    local_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    skipped = 0

    # Alle Dateien vom Reader auf den PC kopieren
    for src_file in reader_root.rglob("*"):
        if not src_file.is_file():
            continue

        # Exclude-Prüfung
        if should_exclude(src_file, reader_root):
            continue

        # !eNews-JSON-Dateien ausschließen
        if is_enews_json(src_file):
            continue

        # Relative Pfad berechnen
        rel_path = src_file.relative_to(reader_root)
        dst_file = local_dir / rel_path

        # Zielverzeichnis erstellen
        dst_file.parent.mkdir(parents=True, exist_ok=True)

        # Status-Callback
        if status_callback:
            status_callback(f"Kopiere: {rel_path}")

        # Prüfen, ob Datei schon existiert und identisch ist
        if dst_file.exists() and files_are_identical(src_file, dst_file):
            skipped += 1
            continue

        # Datei kopieren (überschreiben)
        try:
            shutil.copy2(str(src_file), str(dst_file))
            copied += 1
        except Exception as e:
            pass  # Fehler ignorieren oder loggen

    msg = f"{copied} Dateien vom Reader geholt, {skipped} Übersprungen (bereits vorhanden)"
    return copied, skipped, msg


def sync_to_reader(
    local_dir: Path,
    reader_root: Path,
    status_callback: Optional[Callable[[str], None]] = None,
) -> Tuple[int, int, int, str]:
    """
    Spiegelt den lokalen Stand auf den Reader.

    local_dir: Lokales Master-Verzeichnis (Master)
    reader_root: Root-Verzeichnis des Readers (wird gespiegelt)
    status_callback: Optionaler Callback für Statusmeldungen (wird mit Dateinamen aufgerufen)

    Rückgabe: (kopiert, aktualisiert, gelöscht, Statusmeldung)
    """
    local_dir = local_dir.resolve()

    if not local_dir.exists():
        return 0, 0, 0, "Lokales Master-Verzeichnis nicht gefunden."

    # Reader-Verzeichnis existiert bereits (wird gespiegelt)

    copied = 0
    updated = 0
    deleted = 0

    # 1. Alle lokalen Dateien auf den Reader kopieren/aktualisieren
    for src_file in local_dir.rglob("*"):
        if not src_file.is_file():
            continue

        # Exclude-Prüfung
        if should_exclude(src_file, local_dir):
            continue

        # !eNews-JSON-Dateien ausschließen
        if is_enews_json(src_file):
            continue

        rel_path = src_file.relative_to(local_dir)
        dst_file = reader_root / rel_path

        # Zielverzeichnis erstellen
        dst_file.parent.mkdir(parents=True, exist_ok=True)

        # Status-Callback
        if status_callback:
            status_callback(f"Kopiere: {rel_path}")

        # Prüfen, ob Datei schon existiert und identisch ist
        if dst_file.exists() and files_are_identical(src_file, dst_file):
            continue

        # Datei kopieren (überschreiben)
        try:
            shutil.copy2(str(src_file), str(dst_file))
            updated += 1
        except Exception as e:
            pass  # Fehler ignorieren oder loggen

    # 2. Alle Dateien auf dem Reader löschen, die nicht lokal existieren
    for dst_file in list(reader_root.rglob("*")):
        if not dst_file.is_file():
            continue

        # Exclude-Verzeichnisse nicht löschen (sicherheitshalber)
        if should_exclude(dst_file, reader_root):
            continue

        rel_path = dst_file.relative_to(reader_root)
        src_file = local_dir / rel_path

        if not src_file.exists():
            try:
                dst_file.unlink()
                deleted += 1
            except Exception:
                pass

    # 3. Leere Verzeichnisse auf dem Reader aufrÃ¤umen
    for dirpath in sorted(reader_root.rglob("*"), reverse=True):
        if dirpath.is_dir():
            try:
                if not any(dirpath.iterdir()):
                    dirpath.rmdir()
            except Exception:
                pass

    msg = f"Sync abgeschlossen: {updated} Dateien synchronisiert, {deleted} gelöscht"
    return copied, updated, deleted, msg


if __name__ == "__main__":
    # Test-Block (nur zur Demo)
    import sys

    if len(sys.argv) < 3:
        print("Usage: python sync_worker.py <reader_root> <local_dir>")
        print("Beispiel: python sync_worker.py E:\\ D:\\eBooks\\Reader-Master")
        sys.exit(1)

    reader_root = Path(sys.argv[1])
    local_dir = Path(sys.argv[2])

    print(f"Reader: {reader_root}")
    print(f"Lokal: {local_dir}")
    print()

    # Test: Sync zum Reader
    copied, updated, deleted, msg = sync_to_reader(local_dir, reader_root)
    print(msg)