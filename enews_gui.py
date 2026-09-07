#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eNews GUI – mit RSS-, ePub-Integration, Bereinigung und eReader-Sync
- PySide6
- Tablelist-artige Tabelle: Checkbox, Schlagwort (editierbar), RSS-Link (editierbar)
- Spinbox Vorhaltezeit (Default 20, 0 = keine Bereinigung)
- Startzeit, Intervall (Stunden), Endzeit
- Buttons: Ausführen, Beenden
- Alles wird in config.json gespeichert/geladen
- RSS-Feeds werden geladen und als JSON + ePub im !eNews-Verzeichnis abgelegt
- Verzeichnis-Bereinigung: nur die letzten N Tage behalten
- eReader-Sync: PC als Master, Reader als Spiegel (komplettes Root-Verzeichnis)
"""

import json
import sys
from datetime import datetime, timedelta, time as dt_time
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from PySide6.QtCore import Qt, QTimer, QTime
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
    QAbstractItemView,
)

import rss_worker  # type: ignore[import-untyped]
import epub_builder  # type: ignore[import-untyped]
import sync_worker  # type: ignore[import-untyped]

import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    # Wird als .exe ausgeführt
    BASE_DIR = Path(sys.executable).parent
else:
    # Wird als Script ausgeführt
    BASE_DIR = Path(__file__).parent

CONFIG_FILE = BASE_DIR / "config.json"

ENEWS_DIR = Path(__file__).with_name("!eNews")


def load_config() -> Dict[str, Any]:
    """Lade Konfiguration aus JSON oder liefere Default."""
    if CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # Default-Struktur
    return {
        "feeds": [],  # Liste von {"enabled": True, "keyword": "", "url": ""}
        "retention_days": 20,
        "start_time": "17:00",
        "interval_hours": 4,
        "end_time": "22:00",
        "enews_dir": str(ENEWS_DIR),  # kann userüberschrieben werden
        "reader_master_dir": "",  # Lokales Master-Verzeichnis für Sync
        "reader_root": "",  # Reader-Root-Verzeichnis (z. B. "E:\\")
    }


def save_config(data: Dict[str, Any]) -> None:
    """Speichere Konfiguration in JSON."""
    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def cleanup_old_files(enews_dir: Path, retention_days: int) -> int:
    """
    Löscht alte Dateien im !eNews-Verzeichnis.

    retention_days:
      - 0: nichts löschen
      - >0: nur die letzten N Tage behalten (basierend auf Dateinamen YYYY-MM-DD.*)

    Rückgabe: Anzahl gelöschter Dateien.
    """
    if retention_days <= 0:
        return 0

    deleted_count = 0
    today = datetime.now().date()
    cutoff_date = today - timedelta(days=retention_days)

    # Dateien im Verzeichnis durchgehen
    if not enews_dir.exists():
        return 0

    for file_path in enews_dir.iterdir():
        if not file_path.is_file():
            continue

        # Dateinamen auf Muster YYYY-MM-DD.* prüfen
        stem = file_path.stem  # z. B. "2026-09-02"
        try:
            file_date = datetime.strptime(stem, "%Y-%m-%d").date()
        except ValueError:
            # Kein gültiges Datum im Namen â Ãberspringen
            continue

        if file_date < cutoff_date:
            file_path.unlink()
            deleted_count += 1

    return deleted_count


class FeedsTable(QTableWidget):
    """3-spaltige 'Tablelist': Checkbox, Schlagwort, RSS-Link."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(["Aktiv", "Schlagwort", "RSS-Link"])
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)

    def set_feeds(self, feeds: List[Dict[str, Any]]) -> None:
        """feeds: Liste von {"enabled": bool, "keyword": str, "url": str}"""
        self.setRowCount(0)
        for entry in feeds:
            row = self.rowCount()
            self.insertRow(row)

            # Checkbox
            cb = QCheckBox()
            cb.setChecked(entry.get("enabled", True))
            cb_widget = QWidget()
            cb_layout = QHBoxLayout(cb_widget)
            cb_layout.addWidget(cb)
            cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb_layout.setContentsMargins(0, 0, 0, 0)
            self.setCellWidget(row, 0, cb_widget)

            # Schlagwort
            kw_item = QTableWidgetItem(entry.get("keyword", ""))
            self.setItem(row, 1, kw_item)

            # URL
            url_item = QTableWidgetItem(entry.get("url", ""))
            self.setItem(row, 2, url_item)

    def get_feeds(self) -> List[Dict[str, Any]]:
        """Liefere Liste von {"enabled": bool, "keyword": str, "url": str}."""
        feeds: List[Dict[str, Any]] = []
        for row in range(self.rowCount()):
            cb_widget = self.cellWidget(row, 0)
            cb = cb_widget.findChild(QCheckBox) if cb_widget else None
            enabled = cb.isChecked() if cb else True

            kw_item = self.item(row, 1)
            url_item = self.item(row, 2)

            keyword = kw_item.text().strip() if kw_item is not None else ""
            url = url_item.text().strip() if url_item is not None else ""

            feeds.append({"enabled": enabled, "keyword": keyword, "url": url})
        return feeds

    def add_row(self, enabled: bool = True, keyword: str = "", url: str = "") -> None:
        row = self.rowCount()
        self.insertRow(row)

        cb = QCheckBox()
        cb.setChecked(enabled)
        cb_widget = QWidget()
        cb_layout = QHBoxLayout(cb_widget)
        cb_layout.addWidget(cb)
        cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cb_layout.setContentsMargins(0, 0, 0, 0)
        self.setCellWidget(row, 0, cb_widget)

        kw_item = QTableWidgetItem(keyword)
        self.setItem(row, 1, kw_item)

        url_item = QTableWidgetItem(url)
        self.setItem(row, 2, url_item)


class ENewsWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("eNews Generator")
        self.resize(950, 750)

        self.config = load_config()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.run_job)
        self.next_run_time: Optional[datetime] = None

        self._init_ui()
        self._load_config_to_ui()
        # self._update_schedule()  # <- Nicht hier aufrufen!

        # Stattdessen: Timer erst nach dem Laden starten
        self._update_schedule()  # <- Aber jetzt, nach _load_config_to_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        # ----- Feeds Tabelle -----
        feeds_group = QGroupBox("RSS-Feeds")
        feeds_layout = QVBoxLayout(feeds_group)

        self.feeds_table = FeedsTable(self)
        feeds_layout.addWidget(self.feeds_table)

        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("Hinzufügen", self)
        self.btn_remove = QPushButton("Entfernen", self)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_remove)
        btn_layout.addStretch()
        feeds_layout.addLayout(btn_layout)

        main_layout.addWidget(feeds_group)

        # ----- Einstellungen -----
        settings_group = QGroupBox("Einstellungen")
        settings_layout = QGridLayout(settings_group)

        # Vorhaltezeit
        settings_layout.addWidget(QLabel("Vorhaltezeit (Tage):"), 0, 0)
        self.spin_retention = QSpinBox(self)
        self.spin_retention.setRange(0, 365)
        self.spin_retention.setValue(20)
        settings_layout.addWidget(self.spin_retention, 0, 1)

        # Startzeit
        settings_layout.addWidget(QLabel("Startzeit:"), 1, 0)
        self.time_start = QTimeEdit(self)
        self.time_start.setTime(QTime(17, 0))
        settings_layout.addWidget(self.time_start, 1, 1)

        # Intervall
        settings_layout.addWidget(QLabel("Intervall (Stunden):"), 2, 0)
        self.spin_interval = QSpinBox(self)
        self.spin_interval.setRange(1, 24)
        self.spin_interval.setValue(4)
        settings_layout.addWidget(self.spin_interval, 2, 1)

        # Endzeit
        settings_layout.addWidget(QLabel("Endzeit:"), 3, 0)
        self.time_end = QTimeEdit(self)
        self.time_end.setTime(QTime(22, 0))
        settings_layout.addWidget(self.time_end, 3, 1)

        # !eNews-Verzeichnis
        settings_layout.addWidget(QLabel("!eNews-Verzeichnis (lokal):"), 4, 0)
        self.line_enews_dir = QLineEdit(self)
        self.line_enews_dir.setText(str(ENEWS_DIR))
        settings_layout.addWidget(self.line_enews_dir, 4, 1)

        self.btn_choose_dir = QPushButton("Wählen", self)
        self.btn_choose_dir.clicked.connect(self._choose_enews_dir)
        settings_layout.addWidget(self.btn_choose_dir, 4, 2)

        main_layout.addWidget(settings_group)

        # ----- eReader-Sync -----
        sync_group = QGroupBox("eReader-Sync")
        sync_layout = QGridLayout(sync_group)

        sync_layout.addWidget(QLabel("Reader-Root-Verzeichnis:"), 0, 0)
        self.line_reader_root = QLineEdit(self)
        self.line_reader_root.setPlaceholderText("z. B. E:\\ oder /media/reader")
        sync_layout.addWidget(self.line_reader_root, 0, 1)

        self.btn_choose_reader = QPushButton("Wählen", self)
        self.btn_choose_reader.clicked.connect(self._choose_reader_dir)
        sync_layout.addWidget(self.btn_choose_reader, 0, 2)

        sync_layout.addWidget(QLabel("Reader-Master-Verzeichnis (lokal):"), 1, 0)
        self.line_reader_master = QLineEdit(self)
        self.line_reader_master.setPlaceholderText("z. B. D:\\eBooks\\Reader-Master")
        sync_layout.addWidget(self.line_reader_master, 1, 1)

        self.btn_choose_master = QPushButton("Wählen", self)
        self.btn_choose_master.clicked.connect(self._choose_master_dir)
        sync_layout.addWidget(self.btn_choose_master, 1, 2)

        self.btn_pull = QPushButton("Vom Reader holen (initial)", self)
        self.btn_pull.clicked.connect(self._pull_from_reader)
        sync_layout.addWidget(self.btn_pull, 2, 1)

        self.btn_sync = QPushButton("Sync (PC >> Reader)", self)
        self.btn_sync.clicked.connect(self._sync_to_reader)
        sync_layout.addWidget(self.btn_sync, 2, 2)

        main_layout.addWidget(sync_group)

        # ----- Buttons -----
        btn_row = QHBoxLayout()
        self.btn_run = QPushButton("Ausführen", self)
        self.btn_run.clicked.connect(self.run_job)
        self.btn_exit = QPushButton("Beenden", self)
        self.btn_exit.clicked.connect(self.close)
        btn_row.addWidget(self.btn_run)
        btn_row.addWidget(self.btn_exit)
        btn_row.addStretch()
        main_layout.addLayout(btn_row)

        # Status / Info
        self.lbl_status = QLabel("", self)
        self.lbl_status.setWordWrap(True)
        main_layout.addWidget(self.lbl_status)

        # Connects
        self.btn_add.clicked.connect(self._add_feed_row)
        self.btn_remove.clicked.connect(self._remove_selected_rows)

        # Time edits signal for schedule update
        self.time_start.timeChanged.connect(self._update_schedule)
        self.time_end.timeChanged.connect(self._update_schedule)
        self.spin_interval.valueChanged.connect(self._update_schedule)
        self.line_enews_dir.textChanged.connect(self._update_schedule)

    def _choose_enews_dir(self) -> None:
        current = self.line_enews_dir.text().strip()
        if not current:
            current = str(Path(__file__).parent)
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Verzeichnis für !eNews wählen",
            current,
            QFileDialog.Option.ShowDirsOnly,
        )
        if dir_path:
            self.line_enews_dir.setText(dir_path)

    def _choose_reader_dir(self) -> None:
        current = self.line_reader_root.text().strip()
        if not current:
            current = ""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "eReader-Root-Verzeichnis wählen",
            current,
            QFileDialog.Option.ShowDirsOnly,
        )
        if dir_path:
            self.line_reader_root.setText(dir_path)

    def _choose_master_dir(self) -> None:
        current = self.line_reader_master.text().strip()
        if not current:
            current = str(Path(__file__).parent)
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Reader-Master-Verzeichnis wählen",
            current,
            QFileDialog.Option.ShowDirsOnly,
        )
        if dir_path:
            self.line_reader_master.setText(dir_path)

    def _add_feed_row(self) -> None:
        self.feeds_table.add_row(enabled=True, keyword="", url="")

    def _remove_selected_rows(self) -> None:
        rows = sorted(
            {item.row() for item in self.feeds_table.selectedItems()}, reverse=True
        )
        for row in rows:
            self.feeds_table.removeRow(row)

    def _pull_from_reader(self) -> None:
        """Holt komplettes Root vom Reader auf den PC."""
        self._save_config_from_ui()  # Settings speichern

        reader_root_str = self.line_reader_root.text().strip()
        if not reader_root_str:
            QMessageBox.warning(self, "Sync", "Bitte Reader-Root-Verzeichnis angeben.")
            return

        reader_root = Path(reader_root_str)
        if not reader_root.exists():
            QMessageBox.warning(self, "Sync", "Reader-Root-Verzeichnis existiert nicht.")
            return

        master_dir_str = self.line_reader_master.text().strip()
        if not master_dir_str:
            QMessageBox.warning(self, "Sync", "Bitte Reader-Master-Verzeichnis angeben.")
            return

        master_dir = Path(master_dir_str)

        reply = QMessageBox.question(
            self,
            "Pull bestätigen",
            f"Das komplette Reader-Verzeichnis wird nach {master_dir} kopiert.\n\n"
            "Bestehende Dateien werden Überschrieben.\n\n"
            "Fortfahren?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return

        # Status-Callback
        def on_status(msg: str):
            self.lbl_status.setText(f"Pull: {msg}")

        copied, skipped, msg = sync_worker.pull_from_reader(reader_root, master_dir, status_callback=on_status)

        self.lbl_status.setText(f"Pull: {msg}")
        if skipped > 0:
            QMessageBox.information(self, "Sync", f"{msg}")
        else:
            QMessageBox.information(self, "Sync", msg)

    def _sync_to_reader(self) -> None:
        """Spiegelt lokales Master-Verzeichnis auf den Reader."""
        self._save_config_from_ui()  # Settings speichern

        reader_root_str = self.line_reader_root.text().strip()
        if not reader_root_str:
            QMessageBox.warning(self, "Sync", "Bitte Reader-Root-Verzeichnis angeben.")
            return

        reader_root = Path(reader_root_str)
        if not reader_root.exists():
            QMessageBox.warning(self, "Sync", "Reader-Root-Verzeichnis existiert nicht.")
            return

        master_dir_str = self.line_reader_master.text().strip()
        if not master_dir_str:
            QMessageBox.warning(self, "Sync", "Bitte Reader-Master-Verzeichnis angeben.")
            return

        master_dir = Path(master_dir_str)
        if not master_dir.exists():
            QMessageBox.warning(self, "Sync", "Reader-Master-Verzeichnis existiert nicht.")
            return

        # --- NEU: Warnung bei leerem Master-Verzeichnis ---
        master_has_files = any(master_dir.rglob("*"))
        if not master_has_files:
            reply_empty = QMessageBox.question(
                self,
                "Achtung: PC-Verzeichnis ist leer",
                f"Das lokale Master-Verzeichnis\n{master_dir}\nenthält keine Dateien.\n\n"
                f"Wenn du jetzt fortfährst, wird der komplette Inhalt deines "
                f"eReaders ({reader_root}) GELÖSCHT!\n\n"
                "Hast du bereits den initialen Pull vom Reader ausgeführt?\n\n"
                "Trotzdem fortfahren und eReader leeren?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply_empty == QMessageBox.StandardButton.No:
                return
        # --- Ende NEU ---

        # Bestätigung einholen
        reply = QMessageBox.question(
            self,
            "Sync bestätigen",
            f"Das Reader-Verzeichnis {reader_root} wird mit dem lokalen Stand abgeglichen.\n\n"
            "Dateien auf dem Reader, die lokal nicht existieren, werden gelöscht!\n\n"
            "Fortfahren?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return

       # Status-Callback
        def on_status(msg: str):
            self.lbl_status.setText(f"Sync: {msg}")

        copied, updated, deleted, msg = sync_worker.sync_to_reader(master_dir, reader_root, status_callback=on_status)
        self.lbl_status.setText(f"Sync: {msg}")
        QMessageBox.information(self, "Sync", msg)

    def _load_config_to_ui(self) -> None:
        feeds = self.config.get("feeds", [])
        self.feeds_table.set_feeds(feeds)

        self.spin_retention.setValue(self.config.get("retention_days", 20))
        start_str = self.config.get("start_time", "17:00")
        end_str = self.config.get("end_time", "22:00")
        interval = self.config.get("interval_hours", 4)

        h, m = map(int, start_str.split(":"))
        self.time_start.setTime(QTime(h, m))

        h, m = map(int, end_str.split(":"))
        self.time_end.setTime(QTime(h, m))

        self.spin_interval.setValue(interval)

        enews_dir = self.config.get("enews_dir", str(ENEWS_DIR))
        self.line_enews_dir.setText(enews_dir)

        reader_master_dir = self.config.get("reader_master_dir", "")
        self.line_reader_master.setText(reader_master_dir)

        reader_root = self.config.get("reader_root", "")
        self.line_reader_root.setText(reader_root)

    def _save_config_from_ui(self) -> None:
        self.config["feeds"] = self.feeds_table.get_feeds()
        self.config["retention_days"] = self.spin_retention.value()
        self.config["start_time"] = self.time_start.time().toString("HH:mm")
        self.config["end_time"] = self.time_end.time().toString("HH:mm")
        self.config["interval_hours"] = self.spin_interval.value()
        self.config["enews_dir"] = self.line_enews_dir.text().strip() or str(ENEWS_DIR)
        self.config["reader_master_dir"] = self.line_reader_master.text().strip()
        self.config["reader_root"] = self.line_reader_root.text().strip()
        save_config(self.config)

    def _update_schedule(self) -> None:
        #self._save_config_from_ui()

        start_qt: dt_time = cast(dt_time, self.time_start.time().toPython())
        end_qt: dt_time = cast(dt_time, self.time_end.time().toPython())
        interval = self.spin_interval.value()

        now = datetime.now()
        start_dt = now.replace(hour=start_qt.hour, minute=start_qt.minute, second=0, microsecond=0)
        end_dt = now.replace(hour=end_qt.hour, minute=end_qt.minute, second=0, microsecond=0)

        if start_dt <= now <= end_dt:
            # Wir sind im Zeitfenster
            delta = (now - start_dt).total_seconds() / 3600.0
            slots = int(delta // interval)
            next_dt = start_dt + timedelta(hours=slots * interval)
            if next_dt < now:
                next_dt += timedelta(hours=interval)
            if next_dt > end_dt:
                self.timer.stop()
                self.next_run_time = None
                self.lbl_status.setText("Kein weiterer automatischer Lauf heute (außerhalb des Zeitfensters).")
                return
            self.next_run_time = next_dt
            ms = int((next_dt - now).total_seconds() * 1000)
            self.timer.start(ms)
            self.lbl_status.setText(f"Nächster automatischer Lauf: {next_dt.strftime('%H:%M')}")
        else:
            # Außerhalb des Fensters: nächster Start ist heute/morgen um start_time
            if now.time() > start_qt:
                start_dt = (now + timedelta(days=1)).replace(
                    hour=start_qt.hour, minute=start_qt.minute, second=0, microsecond=0
                )
            else:
                start_dt = now.replace(
                    hour=start_qt.hour, minute=start_qt.minute, second=0, microsecond=0
                )
            self.next_run_time = start_dt
            ms = int((start_dt - now).total_seconds() * 1000)
            self.timer.start(ms)
            self.lbl_status.setText(f"Nächster automatischer Lauf: {start_dt.strftime('%Y-%m-%d %H:%M')}")

    def run_job(self) -> None:
        """RSS-Feeds laden, als JSON + ePub im !eNews-Verzeichnis ablegen + Bereinigung."""
        self._save_config_from_ui()

        feeds = self.feeds_table.get_feeds()
        retention = self.spin_retention.value()
        start_str = self.time_start.time().toString("HH:mm")
        end_str = self.time_end.time().toString("HH:mm")
        interval = self.spin_interval.value()
        enews_dir = Path(self.line_enews_dir.text().strip() or str(ENEWS_DIR))

        # Verzeichnis anlegen
        enews_dir.mkdir(parents=True, exist_ok=True)

        # RSS-Feeds laden
        results = rss_worker.fetch_feeds(feeds)

        # Statistik
        total_items = sum(len(r.get("items", [])) for r in results)
        errors = [r for r in results if "error" in r]

        # JSON speichern (Datum als Dateiname)
        today = datetime.now().strftime("%Y-%m-%d")
        json_file = enews_dir / f"{today}.json"
        try:
            with json_file.open("w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            self.lbl_status.setText(f"Fehler beim Schreiben der JSON-Datei: {e}")
            return

        # ePub erstellen
        epub_file = enews_dir / f"{today}.epub"
        title = f"eNews {today}"
        try:
            epub_builder.build_epub(results, epub_file, title=title)
            epub_created = True
        except Exception as e:
            epub_created = False
            epub_error = str(e)

        # Verzeichnis-Bereinigung
        deleted_count = cleanup_old_files(enews_dir, retention)

        # Status anzeigen
        msg_lines = [
            f"Job gestartet ({datetime.now().strftime('%Y-%m-%d %H:%M')})",
            f"Feeds geladen: {len(results)}",
            f"Items insgesamt: {total_items}",
            f"JSON: {json_file}",
            f"ePub: {epub_file} ({'OK' if epub_created else 'FEHLER'})",
            f"Bereinigung: {deleted_count} alte Dateien gelöscht",
        ]
        if errors:
            msg_lines.append(f"Fehlerhafte Feeds: {len(errors)}")
            for err in errors:
                msg_lines.append(f"  - {err['keyword']}: {err.get('error', 'unbekannt')}")
        if not epub_created:
            msg_lines.append(f"ePub-Fehler: {epub_error}")

        self.lbl_status.setText("\n".join(msg_lines))

    def closeEvent(self, event: Any) -> None:
        self._save_config_from_ui()
        self.timer.stop()
        event.accept()


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = ENewsWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()