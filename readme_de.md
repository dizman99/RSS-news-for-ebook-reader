# eNews-eBooks

Ein kompaktes Tool für Windows, das erlaubt ePub-Dateien aus RSS-Feeds zu generieren. Parallel ist es auch ein vollständiger eReader-Sync. Das Besondere daran ist, dass zunächst eine vollständige Kopie des eReaders auf den PC gezogen wird. Danach dient dieses Verzeichnis als Master. Das bedeutet, man arbeitet selbst nur noch auf diesem Verzeichnis. Will man eBooks löschen, so löscht man sie aus dem PC-Verzeichnis. Will man neue auf dem Reader haben, so kopiert man sie ebenfalls ins PC-Verzeichnis. Beim "Sync" wird der eReader zu einem "Spiegel" des PC-Verzeichnisses – quasi wie Dropbox.

![Hauptansicht](screenshots/main.png)

---

**Hinweis:** Dieses Programm wurde komplett durch die Perplexity AI geschrieben. Ich habe es nur durch den Prozess geführt.

Dies soll ein Gemeinschaftsprojekt sein. Ich vermute, ich werde nicht (oder keine) Zeit haben, neue Sachen anzuhangen oder Bugs zu fixen. Fuhle dich frei, eigene Änderungen, Fixes oder neue Features hinzuzufugen.

**Entwicklungsziel:** Ich habe einen XTEink X4 Pro eBook-Reader, mit dem ich sehr zufrieden bin. Was mir fehlte, war die Möglichkeit, auch eNews darauf zu lesen. Es entstand die Idee, RSS-Feeds in eBooks zu verwandeln, um diese dann auf dem Reader zu lesen. Nachdem dies funktionierte, war schnell klar, dass das Handling der Files etwas umstandlich ist und so folgte Idee 2: Eine Synchronisation des kompletten Readers mit dem PC und darunter auch mit den erzeugten eNews-ePubs.

Ich hoffe, du magst es!

– Dietmar Bos

---

## Features

### Hauptmerkmale

- **RSS-Feed-Manager:** Verwalte beliebig viele RSS-Feeds mit individuellen Schlagworten
- **Automatische ePub-Generierung:** Erstellt täglich neue eBooks aus deinen RSS-Feeds
  - Pro Feed ein eigenes Kapitel
  - Detailliertes Inhaltsverzeichnis mit Links zu jedem Artikel
  - "Zuruck zum Inhaltsverzeichnis"-Link nach jedem Kapitel
- **Zeitsteuerung:** Automatische Ausfuhrung zu einstellbaren Zeiten (Start, Ende, Intervall)
- **Verzeichnis-Bereinigung:** Behalt nur die letzten N Tage (konfigurierbar)
- **eReader-Sync:** Vollstandige Synchronisation zwischen PC und eReader
  - PC als Master, Reader als Spiegel
  - Initialer Pull vom Reader (komplettes Root-Verzeichnis)
  - Sync (PC → Reader) 
  - Ausschluss von System-Verzeichnissen (z. B. "System Volume Information")
  - Keine Synchronisation von JSON-Dateien (nur .epub aus !eNews)

### Weitere Features

- **JSON-Konfiguration:** Alle Einstellungen in `config.json` gespeichert
- **Statusanzeige:** Echtzeit-Feedback beim Kopieren/Sync
- **Exclude-Liste:** System-Verzeichnisse werden automatisch ubersprungen
- **Verschluesselungsfrei:** Keine externen Abhangigkeiten auBer PySide6

---

## Installation

### Voraussetzungen

- Windows 10/11
- Python 3.8 oder hoher

### Abhangigkeiten installieren

```bash
python -m pip install PySide6 feedparser beautifulsoup4 lxml requests
```

### Programm starten

```bash
python enews_gui.py
```

### Als .exe kompilieren (optional)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed enews_gui.py
```

Die .exe findest du im `dist`-Verzeichnis.

---

## Verwendung

### Erster Start

1. **RSS-Feeds eintragen:**
   - Klicke auf "Hinzufugen" in der RSS-Feeds-Tabelle
   - Trage ein Schlagwort (z. B. "Heise") und die RSS-URL ein
   - Wiederhole fur weitere Feeds

2. **Einstellungen anpassen:**
   - Vorhaltezeit: Wie viele Tage sollen im !eNews-Verzeichnis behalten werden? (0 = alle)
   - Startzeit, Intervall, Endzeit: Wann soll das Tool automatisch laufen?
   - !eNews-Verzeichnis: Wo sollen die generierten Dateien gespeichert werden?

3. **eReader-Sync einrichten:**
   - Reader-Root-Verzeichnis: Pfad zum eReader (z. B. `E:\`)
   - Reader-Master-Verzeichnis: Lokales Verzeichnis fur die Synchronisation
   - Klicke auf "Vom Reader holen (initial)", um den Reader komplett zu kopieren

4. **Erste Ausfuhrung:**
   - Klicke auf "Ausfuhren", um RSS-Feeds zu laden und ePub zu erstellen
   - Die Dateien landen im !eNews-Verzeichnis (als JSON und ePub)

5. **Sync auf den Reader:**
   - Klicke auf "Sync (PC → Reader)", um den Reader zu aktualisieren

### Programm beenden

- Klicke auf "Beenden" oder schlieBe das Fenster
- Alle Einstellungen werden automatisch in `config.json` gespeichert

---

## Konfiguration

Die Einstellungen werden in `config.json` gespeichert. Diese Datei kann auch manuell bearbeitet werden.

### Beispiel-Konfiguration

```json
{
  "feeds": [
    {
      "enabled": true,
      "keyword": "Computerbase",
      "url": "https://www.computerbase.de/rss/news.xml"
    },
    {
      "enabled": true,
      "keyword": "Tagesschau",
      "url": "https://www.tagesschau.de/xml/rss2/"
    },
    {
      "enabled": true,
      "keyword": "heise",
      "url": "https://www.heise.de/rss/heise-atom.xml"
    }
  ],
  "retention_days": 20,
  "start_time": "17:00",
  "interval_hours": 4,
  "end_time": "22:00",
  "enews_dir": "D:/zz/!eNews-Master/!eNews",
  "reader_root": "G:/",
  "reader_master_dir": "D:/zz/!eNews-Master"
}
```

### Konfigurationsoptionen

| Feld | Beschreibung |
|------|-------------|
| `feeds` | Liste der RSS-Feeds (enabled, keyword, url) |
| `retention_days` | Wie viele Tage im !eNews-Verzeichnis behalten (0 = alle) |
| `start_time` | Startzeit fur automatische Ausfuhrung (HH:MM) |
| `interval_hours` | Intervall zwischen Ausfuhrungen (in Stunden) |
| `end_time` | Endzeit fur automatische Ausfuhrung (HH:MM) |
| `enews_dir` | Lokales Verzeichnis fur generierte Dateien |
| `reader_root` | Root-Verzeichnis des eReaders (z. B. `E:\`) |
| `reader_master_dir` | Lokales Master-Verzeichnis fur Sync |

---

## Screenshots

### Hauptansicht

![Hauptansicht](screenshots/main.png)

### In-Action (ePub auf dem Reader)

![In-Action](screenshots/inBook.png)

---

## Technische Details

### Abhangigkeiten

- **PySide6** – GUI-Framework
- **feedparser** – RSS/Atom-Parsing
- **beautifulsoup4** + **lxml** – HTML-zu-Text-Konvertierung
- **requests** – Robuster HTTP-Download fur Feeds

### Architektur

- **enews_gui.py** – Haupt-GUI mit Timer, RSS-Download, ePub-Generierung, Sync
- **rss_worker.py** – RSS-Download mit Fallback-Logik (lxml-Repair)
- **epub_builder.py** – Minimaler ePub-Builder (ohne externe Libraries)
- **sync_worker.py** – Sync-Logik (Pull/Sync mit Exclude-Liste)

### ePub-Struktur

Das generierte ePub enthalt:

- Cover-Seite mit Titel und Datum
- Detailliertes Inhaltsverzeichnis mit Links zu jedem Artikel
- Pro Feed ein Kapitel mit Schlagwort als Uberschrift
- Pro Artikel: Titel, Datum, Link, Content als FlieBtext
- "Zuruck zum Inhaltsverzeichnis"-Link nach jedem Kapitel

---

## Haufige Fragen

### Q: Warum wird meine config.json nicht geladen?

A: Stelle sicher, dass die `config.json` im gleichen Verzeichnis wie die .exe liegt. Beim Start wird sie automatisch geladen.

### Q: Welche Verzeichnisse werden nicht synchronisiert?

A: Ausgeschlossen sind: "System Volume Information", ".DS_Store", "$RECYCLE.BIN", "Thumbs.db", "desktop.ini".

### Q: Warum werden JSON-Dateien nicht synchronisiert?

A: JSON-Dateien sind nur fur die Generierung relevant und sollen nicht auf den Reader.

### Q: Kann ich das Tool auch ohne eReader nutzen?

A: Ja! Du kannst es nur fur die RSS-zu-ePub-Generierung verwenden. Der Sync ist optional.

---

## Credits

Entwickelt mit Hilfe von **Perplexity AI**. Dieses Projekt zeigt, wie KI-gestutzte Entwicklung praktische Tools fur den Alltag schaffen kann.

---

## Lizenz

MIT License – Siehe [LICENSE](LICENSE) Datei.

---

## Support

Dies ist ein Community-Projekt. Bei Fragen oder Problemen:

- Offne ein Issue auf GitHub
- Beschreibe dein Problem so detailliert wie moglich
- Ich versuche zu helfen, kann aber keine Garantie geben

**Hinweis:** Dieses Projekt wurde mit Hilfe von KI (Perplexity AI) entwickelt.

---

## Changelog

### Version 1.0 (September 2026)

- Erster Release
- RSS-Feed-Manager mit automatischer ePub-Generierung
- Zeitsteuerung (Start/Ende/Intervall)
- Verzeichnis-Bereinigung (Vorhaltezeit)
- eReader-Sync (PC als Master, Reader als Spiegel)
- Exclude-Liste fur System-Verzeichnisse
- Warnung vor Sync bei leerem Master-Verzeichnis
- Statusanzeige beim Kopieren/Sync