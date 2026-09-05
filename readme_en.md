# eNews-eBooks

A compact tool for Windows that allows generating ePub files from RSS feeds. Additionally, it provides complete eReader synchronization. The special feature is that initially a complete copy of the eReader is pulled to the PC. Afterwards, this directory serves as the master. This means you only work with this directory. If you want to delete eBooks, you delete them from the PC directory. If you want new ones on the reader, you copy them to the PC directory as well. During "Sync", the eReader becomes a "mirror" of the PC directory – just like Dropbox.

![Main View](screenshots/main.png)

---

**Note:** This program was completely written by Perplexity AI. I only guided it through the process.

This is intended to be a community project. I suspect I will not (or have no) time to add new features or fix bugs. Feel free to add your own changes, fixes, or new features.

**Development Goal:** I have an XTEink X4 Pro eBook reader that I'm very happy with. What I was missing was the ability to read eNews on it. The idea arose to convert RSS feeds into eBooks to read them on the reader. Once this worked, it quickly became clear that handling the files was somewhat cumbersome, and so idea 2 followed: Synchronization of the complete reader with the PC, including the generated eNews ePubs.

I hope you like it!

– Dietmar Bos

---

## Features

### Main Features

- **RSS Feed Manager:** Manage unlimited RSS feeds with individual keywords
- **Automatic ePub Generation:** Creates daily new eBooks from your RSS feeds
  - One chapter per feed
  - Detailed table of contents with links to each article
  - "Back to table of contents" link after each chapter
- **Time Scheduling:** Automatic execution at configurable times (start, end, interval)
- **Directory Cleanup:** Keep only the last N days (configurable)
- **eReader Sync:** Complete synchronization between PC and eReader
  - PC as master, reader as mirror
  - Initial pull from reader (complete root directory)
  - Sync (PC → reader) 
  - Exclusion of system directories (e.g., "System Volume Information")
  - No synchronization of JSON files (only .epub from !eNews)

### Additional Features

- **JSON Configuration:** All settings saved in `config.json`
- **Status Display:** Real-time feedback during copy/sync
- **Exclude List:** System directories are automatically skipped
- **No Encryption:** No external dependencies except PySide6

---

## Installation

### Requirements

- Windows 10/11
- Python 3.8 or higher

### Install Dependencies

```bash
python -m pip install PySide6 feedparser beautifulsoup4 lxml requests
```

### Start Program

```bash
python enews_gui.py
```

### Compile as .exe (optional)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed enews_gui.py
```

You'll find the .exe in the `dist` directory.

---

## Usage

### First Start

1. **Add RSS Feeds:**
   - Click "Hinzufugen" (Add) in the RSS feeds table
   - Enter a keyword (e.g., "Heise") and the RSS URL
   - Repeat for additional feeds

2. **Adjust Settings:**
   - Retention days: How many days should be kept in the !eNews directory? (0 = all)
   - Start time, interval, end time: When should the tool run automatically?
   - !eNews directory: Where should generated files be stored?

3. **Set Up eReader Sync:**
   - Reader root directory: Path to eReader (e.g., `E:\`)
   - Reader master directory: Local directory for synchronization
   - Click "Vom Reader holen (initial)" to completely copy the reader

4. **First Execution:**
   - Click "Ausfuhren" (Execute) to load RSS feeds and create ePub
   - Files are saved in the !eNews directory (as JSON and ePub)

5. **Sync to Reader:**
   - Click "Sync (PC → Reader)" to update the reader

### Exit Program

- Click "Beenden" (Exit) or close the window
- All settings are automatically saved to `config.json`

---

## Configuration

Settings are saved in `config.json`. This file can also be edited manually.

### Example Configuration

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

### Configuration Options

| Field | Description |
|-------|-------------|
| `feeds` | List of RSS feeds (enabled, keyword, url) |
| `retention_days` | How many days to keep in !eNews directory (0 = all) |
| `start_time` | Start time for automatic execution (HH:MM) |
| `interval_hours` | Interval between executions (in hours) |
| `end_time` | End time for automatic execution (HH:MM) |
| `enews_dir` | Local directory for generated files |
| `reader_root` | Root directory of eReader (e.g., `E:\`) |
| `reader_master_dir` | Local master directory for sync |

---

## Screenshots

### Main View

![Main View](screenshots/main.png)

### In-Action (ePub on Reader)

![In-Action](screenshots/inBook.png)

---

## Technical Details

### Dependencies

- **PySide6** – GUI framework
- **feedparser** – RSS/Atom parsing
- **beautifulsoup4** + **lxml** – HTML-to-text conversion
- **requests** – Robust HTTP download for feeds

### Architecture

- **enews_gui.py** – Main GUI with timer, RSS download, ePub generation, sync
- **rss_worker.py** – RSS download with fallback logic (lxml repair)
- **epub_builder.py** – Minimal ePub builder (no external libraries)
- **sync_worker.py** – Sync logic (pull/sync with exclude list)

### ePub Structure

The generated ePub contains:

- Cover page with title and date
- Detailed table of contents with links to each article
- One chapter per feed with keyword as heading
- Per article: title, date, link, content as plain text
- "Back to table of contents" link after each chapter

---

## Frequently Asked Questions

### Q: Why is my config.json not loaded?

A: Make sure the `config.json` is in the same directory as the .exe. It is automatically loaded on startup.

### Q: Which directories are not synchronized?

A: Excluded are: "System Volume Information", ".DS_Store", "$RECYCLE.BIN", "Thumbs.db", "desktop.ini".

### Q: Why are JSON files not synchronized?

A: JSON files are only relevant for generation and should not be on the reader.

### Q: Can I use the tool without an eReader?

A: Yes! You can use it only for RSS-to-ePub generation. Sync is optional.

---

## Credits

Developed with help from **Perplexity AI**. This project shows how AI-assisted development can create practical tools for everyday use.

---

## License

MIT License – See [LICENSE](LICENSE) file.

---

## Support

This is a community project. For questions or problems:

- Open an issue on GitHub
- Describe your problem as detailed as possible
- I'll try to help, but can't give any guarantee

**Note:** This project was developed with help from AI (Perplexity AI).

---

## Changelog

### Version 1.0 (September 2026)

- Initial release
- RSS feed manager with automatic ePub generation
- Time scheduling (start/end/interval)
- Directory cleanup (retention days)
- eReader sync (PC as master, reader as mirror)
- Exclude list for system directories
- Warning before sync if master directory is empty
- Status display during copy/sync