#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
normalize_dialog.py - Dialog "Text normalisieren" fuer den eNews Generator (PySide6).
Benoetigt epub_normalizer.py (reine Logik). Die Konvertierung laeuft in einem QThread.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

import epub_normalizer as nz  # type: ignore[import-untyped]

PATH_ROLE = Qt.ItemDataRole.UserRole
BOOL_KEYS = ("indent_first", "merge_broken", "fix_mojibake", "typography", "keep_gaps")


class _Cancelled(Exception):
    pass


class NormalizeWorker(QThread):
    file_started = Signal(int, int, str)
    log = Signal(str)
    done = Signal(dict)

    def __init__(self, files: List[Path], master: Path, opts: Dict[str, Any],
                 dry_run: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.files, self.master, self.opts, self.dry_run = files, master, opts, dry_run
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def _progress(self, i: int, n: int, name: str) -> None:
        if self._cancel:
            raise _Cancelled()

    def run(self) -> None:
        sm: Dict[str, Any] = {"ok": 0, "skipped": 0, "failed": 0, "cancelled": False,
                              "mojibake": 0, "empty": 0, "merged": 0, "regrouped": 0}
        total = len(self.files)
        for i, path in enumerate(self.files, 1):
            if self._cancel:
                sm["cancelled"] = True
                break
            try:
                rel = path.relative_to(self.master)
            except ValueError:
                rel = Path(path.name)
            self.file_started.emit(i, total, str(rel))
            try:
                if self.dry_run:
                    with tempfile.TemporaryDirectory() as td:
                        st = nz.normalize_epub(path, Path(td) / "dry.epub", self.opts, self._progress)
                else:
                    st = nz.convert_file(path, self.master, self.opts, self._progress)
                sm["ok"] += 1
                for k in ("mojibake", "empty", "merged", "regrouped"):
                    sm[k] += st.get(k, 0)
                self.log.emit(
                    f"OK       {rel}: {st.get('docs_changed', 0)}/{st.get('docs', 0)} Kapitel, "
                    f"Blöcke {st.get('blocks_in', 0)} -> {st.get('blocks_out', 0)}, "
                    f"{st.get('mojibake', 0)} Zeichen repariert"
                )
            except _Cancelled:
                sm["cancelled"] = True
                break
            except nz.EpubError as e:
                sm["skipped"] += 1
                self.log.emit(f"ÜBERSPR. {rel}: {e}")
            except Exception as e:  # z. B. Datei gesperrt (Reader-Programm hat sie offen)
                sm["failed"] += 1
                self.log.emit(f"FEHLER   {rel}: {type(e).__name__}: {e}")
        self.done.emit(sm)


class NormalizeDialog(QDialog):
    def __init__(self, parent: QWidget | None, master_dir: Path, saved: Dict[str, Any] | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Text normalisieren")
        self.resize(1050, 720)
        self.master = Path(master_dir)
        self.saved = {**nz.DEFAULTS, "scope": "selection", "dry_run": False, **(saved or {})}
        self.worker: NormalizeWorker | None = None
        self._bulk = False
        self._init_ui()
        self._apply_saved()
        self._populate_tree()

    # ------------------------------------------------------------ UI
    def _init_ui(self) -> None:
        main = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        main.addWidget(splitter, 1)

        # links: Baum
        left = QGroupBox(f"Master-Verzeichnis: {self.master}")
        lv = QVBoxLayout(left)
        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels(["Name", "Größe"])
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setRootIsDecorated(True)
        self.tree.setItemsExpandable(True)
        self.tree.setExpandsOnDoubleClick(True)
        self.tree.setAlternatingRowColors(True)

        self.tree.setColumnWidth(0, 420)
        lv.addWidget(self.tree)
        row = QHBoxLayout()
        self.btn_all = QPushButton("Alle markieren", self)
        self.btn_none = QPushButton("Keine markieren", self)
        self.btn_expand = QPushButton("Aufklappen", self)
        self.btn_collapse = QPushButton("Zuklappen", self)
        self.btn_check_sel = QPushButton("Markierte anhaken", self)
        self.btn_uncheck_sel = QPushButton("Markierte abhaken", self)
        row.addWidget(self.btn_check_sel)
        row.addWidget(self.btn_uncheck_sel)
        # bei den connects:
        self.btn_check_sel.clicked.connect(lambda: self._check_selected(Qt.CheckState.Checked))
        self.btn_uncheck_sel.clicked.connect(lambda: self._check_selected(Qt.CheckState.Unchecked))
        for b in (self.btn_all, self.btn_none, self.btn_expand, self.btn_collapse):
            row.addWidget(b)
        row.addStretch()
        lv.addLayout(row)
        self.lbl_count = QLabel("", self)
        lv.addWidget(self.lbl_count)
        splitter.addWidget(left)

        # rechts: Optionen
        right = QWidget(self)
        rv = QVBoxLayout(right)

        g_scope = QGroupBox("Was konvertieren?")
        gl = QVBoxLayout(g_scope)
        self.rb_sel = QRadioButton("Nur die markierte Auswahl", self)
        self.rb_all = QRadioButton("Alle ePubs im Master-Verzeichnis", self)
        gl.addWidget(self.rb_sel)
        gl.addWidget(self.rb_all)
        rv.addWidget(g_scope)

        g_mode = QGroupBox("Ergebnis speichern")
        ml = QVBoxLayout(g_mode)
        self.rb_replace = QRadioButton("ePub ersetzen (Original nach .backup)", self)
        self.rb_suffix = QRadioButton("Neben dem Original als *_reformat.epub", self)
        ml.addWidget(self.rb_replace)
        ml.addWidget(self.rb_suffix)
        rv.addWidget(g_mode)
        grp1, grp2 = QButtonGroup(self), QButtonGroup(self)
        grp1.addButton(self.rb_sel)
        grp1.addButton(self.rb_all)
        grp2.addButton(self.rb_replace)
        grp2.addButton(self.rb_suffix)

        g_text = QGroupBox("Absätze und Layout")
        tl = QGridLayout(g_text)
        tl.addWidget(QLabel("Absatz frühestens nach (Sätze):"), 0, 0)
        self.spin_sent = QSpinBox(self)
        self.spin_sent.setRange(1, 500)
        self.spin_sent.setToolTip("1 = Absätze des Originals beibehalten. Dialogzeilen, Überschriften "
                                  "und Szenenwechsel brechen immer.")
        tl.addWidget(self.spin_sent, 0, 1)
        tl.addWidget(QLabel("Max. Absatzlänge (Zeichen):"), 1, 0)
        self.spin_chars = QSpinBox(self)
        self.spin_chars.setRange(300, 50000)
        self.spin_chars.setSingleStep(100)
        self.spin_chars.setToolTip("Obergrenze, damit keine Textwände entstehen. Bei sehr hoher "
                                   "Satzzahl ebenfalls erhöhen.")
        tl.addWidget(self.spin_chars, 1, 1)
        tl.addWidget(QLabel("Erstzeileneinzug:"), 2, 0)
        self.combo_indent = QComboBox(self)
        for label, val in (("kein Einzug", "0"), ("1.0 em", "1em"),
                           ("1.2 em (Standard)", "1.2em"), ("1.5 em", "1.5em")):
            self.combo_indent.addItem(label, val)
        tl.addWidget(self.combo_indent, 2, 1)
        self.chk_indent_first = QCheckBox("Auch ersten Absatz nach Überschrift einrücken", self)
        tl.addWidget(self.chk_indent_first, 3, 0, 1, 2)
        self.chk_keep_gaps = QCheckBox("Abschnittsabstände des Originals als 1 Leerzeile behalten", self)
        tl.addWidget(self.chk_keep_gaps, 4, 0, 1, 2)
        rv.addWidget(g_text)

        g_fix = QGroupBox("Textreparatur")
        fl = QVBoxLayout(g_fix)
        self.chk_moji = QCheckBox("Umlaute reparieren (Ã¼ → ü usw.)", self)
        self.chk_merge = QCheckBox("Mitten im Satz getrennte Absätze verbinden", self)
        self.chk_typo = QCheckBox("Typografie (Gedankenstrich, …, ›Zitat‹, Leerzeichen)", self)
        for c in (self.chk_moji, self.chk_merge, self.chk_typo):
            fl.addWidget(c)
        rv.addWidget(g_fix)

        g_misc = QGroupBox("Sonstiges")
        sl = QVBoxLayout(g_misc)
        self.chk_dry = QCheckBox("Testlauf (nichts schreiben, nur Statistik)", self)
        sl.addWidget(self.chk_dry)
        rv.addWidget(g_misc)
        rv.addStretch()
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        # unten
        self.progress = QProgressBar(self)
        self.progress.setValue(0)
        main.addWidget(self.progress)
        self.log_view = QPlainTextEdit(self)
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(150)
        main.addWidget(self.log_view)

        brow = QHBoxLayout()
        self.btn_start = QPushButton("Start", self)
        self.btn_cancel = QPushButton("Abbrechen", self)
        self.btn_cancel.setEnabled(False)
        self.btn_close = QPushButton("Schließen", self)
        brow.addWidget(self.btn_start)
        brow.addWidget(self.btn_cancel)
        brow.addStretch()
        brow.addWidget(self.btn_close)
        main.addLayout(brow)

        self.btn_all.clicked.connect(lambda: self._set_all(Qt.CheckState.Checked))
        self.btn_none.clicked.connect(lambda: self._set_all(Qt.CheckState.Unchecked))
        self.btn_expand.clicked.connect(self.tree.expandAll)
        self.btn_collapse.clicked.connect(self.tree.collapseAll)
        self.tree.itemChanged.connect(self._update_count)
        self.rb_all.toggled.connect(self._scope_changed)
        self.btn_start.clicked.connect(self._start)
        self.btn_cancel.clicked.connect(self._cancel)
        self.btn_close.clicked.connect(self.reject)

        self._option_widgets: List[QWidget] = [
            self.rb_sel, self.rb_all, self.rb_replace, self.rb_suffix, self.spin_sent, self.spin_chars,
            self.combo_indent, self.chk_indent_first, self.chk_keep_gaps, self.chk_moji, self.chk_merge,
            self.chk_typo, self.chk_dry, self.tree, self.btn_all, self.btn_none, self.btn_start,
        ]

    # ------------------------------------------------------------ Optionen
    def _apply_saved(self) -> None:
        s = self.saved
        (self.rb_all if s.get("scope") == "all" else self.rb_sel).setChecked(True)
        (self.rb_suffix if s.get("mode") == "suffix" else self.rb_replace).setChecked(True)
        self.spin_sent.setValue(int(s.get("min_sentences", 10)))
        self.spin_chars.setValue(int(s.get("max_chars", 2000)))
        idx = self.combo_indent.findData(s.get("indent", "1.2em"))
        self.combo_indent.setCurrentIndex(idx if idx >= 0 else 2)
        self.chk_indent_first.setChecked(bool(s.get("indent_first", True)))
        self.chk_keep_gaps.setChecked(bool(s.get("keep_gaps", True)))
        self.chk_moji.setChecked(bool(s.get("fix_mojibake", True)))
        self.chk_merge.setChecked(bool(s.get("merge_broken", True)))
        self.chk_typo.setChecked(bool(s.get("typography", True)))
        self.chk_dry.setChecked(bool(s.get("dry_run", False)))
        self._scope_changed()

    def get_options(self) -> Dict[str, Any]:
        """Alle Einstellungen (fuer config.json) - inklusive Scope und Testlauf."""
        return {
            "scope": "all" if self.rb_all.isChecked() else "selection",
            "mode": "suffix" if self.rb_suffix.isChecked() else "replace",
            "min_sentences": self.spin_sent.value(),
            "max_chars": self.spin_chars.value(),
            "indent": self.combo_indent.currentData() or "1.2em",
            "indent_first": self.chk_indent_first.isChecked(),
            "keep_gaps": self.chk_keep_gaps.isChecked(),
            "fix_mojibake": self.chk_moji.isChecked(),
            "merge_broken": self.chk_merge.isChecked(),
            "typography": self.chk_typo.isChecked(),
            "dry_run": self.chk_dry.isChecked(),
        }

    def _normalizer_opts(self) -> Dict[str, Any]:
        o = self.get_options()
        return {k: o[k] for k in nz.DEFAULTS if k in o} | {"style": "p"}

    # ------------------------------------------------------------ Baum
    def _populate_tree(self) -> None:
        self._bulk = True
        try:
            self.tree.clear()
            self._build(self.tree.invisibleRootItem(), self.master)
        finally:
            self._bulk = False
        self.tree.expandToDepth(0)
        self._update_count()

    def _check_selected(self, state: Qt.CheckState) -> None:
        self._bulk = True
        try:
            for it in self.tree.selectedItems():
                it.setCheckState(0, state)
        finally:
            self._bulk = False
        self._update_count()

    def _build(self, parent: QTreeWidgetItem, folder: Path) -> int:
        count = 0
        try:
            entries = sorted(os.scandir(folder), key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()))
        except OSError:
            return 0
        for e in entries:
            if e.name.startswith("."):          # .backup, .crosspoint usw.
                continue
            if e.is_dir(follow_symlinks=False):
                item = QTreeWidgetItem()
                item.setText(0, e.name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
                item.setCheckState(0, Qt.CheckState.Unchecked)
                n = self._build(item, Path(e.path))
                if n:
                    parent.addChild(item)
                    count += n
            elif e.name.lower().endswith(".epub") and not Path(e.name).stem.endswith(nz.SUFFIX):
                item = QTreeWidgetItem()
                item.setText(0, e.name)
                try:
                    item.setText(1, f"{e.stat().st_size / 1024:,.0f} KB")
                except OSError:
                    pass
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Unchecked)
                item.setData(0, PATH_ROLE, e.path)
                parent.addChild(item)
                count += 1
        return count

    def _leaf_items(self) -> List[QTreeWidgetItem]:
        out: List[QTreeWidgetItem] = []
        root = self.tree.invisibleRootItem()
        stack: List[QTreeWidgetItem] = [root] if root is not None else []
        while stack:
            it = stack.pop()
            for i in range(it.childCount()):
                ch = it.child(i)
                if ch is None:
                    continue
                if ch.data(0, PATH_ROLE):
                    out.append(ch)
                else:
                    stack.append(ch)
        return out

    def _selected_files(self) -> List[Path]:
        files = [Path(it.data(0, PATH_ROLE)) for it in self._leaf_items()
                 if it.checkState(0) == Qt.CheckState.Checked]
        return sorted(files, key=lambda p: str(p).lower())

    def _set_all(self, state: Qt.CheckState) -> None:
        self._bulk = True
        try:
            top = self.tree.invisibleRootItem()
            if top is not None:
                for i in range(top.childCount()):
                    child = top.child(i)
                    if child is not None:
                        child.setCheckState(0, state)   # Ordner propagieren auf alle Kinder
        finally:
            self._bulk = False
        self._update_count()

    def _update_count(self, *_: Any) -> None:
        if self._bulk:
            return
        total = len(self._leaf_items())
        sel = len(self._selected_files())
        self.lbl_count.setText(f"{sel} von {total} ePubs markiert")

    def _scope_changed(self, *_: Any) -> None:
        busy = self.worker is not None and self.worker.isRunning()
        self.tree.setEnabled(not self.rb_all.isChecked() and not busy)
        self.btn_all.setEnabled(not self.rb_all.isChecked() and not busy)
        self.btn_none.setEnabled(not self.rb_all.isChecked() and not busy)

    # ------------------------------------------------------------ Ablauf
    def _set_busy(self, busy: bool) -> None:
        for w in self._option_widgets:
            w.setEnabled(not busy)
        self.btn_cancel.setEnabled(busy)
        if not busy:
            self._scope_changed()

    def _start(self) -> None:
        opts = self.get_options()
        if opts["scope"] == "all":
            files = sorted(nz.iter_epubs(self.master), key=lambda p: str(p).lower())
        else:
            files = self._selected_files()
        if not files:
            QMessageBox.information(self, "Text normalisieren", "Keine ePubs ausgewählt.")
            return
        if opts["mode"] == "replace" and not opts["dry_run"]:
            r = QMessageBox.question(
                self, "Ersetzen bestätigen",
                f"{len(files)} ePub(s) werden im Master-Verzeichnis ersetzt.\n\n"
                "Die Originale werden einmalig nach .backup gesichert.\n"
                "Gelesene Bücher beginnen auf dem Reader danach von vorne.\n\nFortfahren?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if r != QMessageBox.StandardButton.Yes:
                return
        self.log_view.clear()
        self.progress.setRange(0, len(files))
        self.progress.setValue(0)
        self._set_busy(True)
        self.worker = NormalizeWorker(files, self.master, self._normalizer_opts(), opts["dry_run"], self)
        self.worker.file_started.connect(self._on_file)
        self.worker.log.connect(self.log_view.appendPlainText)
        self.worker.done.connect(self._on_done)
        self.worker.start()

    def _on_file(self, i: int, n: int, name: str) -> None:
        self.progress.setValue(i - 1)
        self.progress.setFormat(f"{i}/{n}  {name}")

    def _on_done(self, sm: Dict[str, Any]) -> None:
        self.progress.setValue(self.progress.maximum() if not sm["cancelled"] else self.progress.value())
        self._set_busy(False)
        head = "Abgebrochen. " if sm["cancelled"] else "Fertig. "
        txt = (f"{head}{sm['ok']} konvertiert, {sm['skipped']} übersprungen, {sm['failed']} Fehler | "
               f"{sm['mojibake']} Zeichen repariert, {sm['empty']} leere Blöcke entfernt, "
               f"{sm['merged']} Satzumbrüche verbunden, {sm['regrouped']} Absätze zusammengefasst")
        self.log_view.appendPlainText("\n" + txt)
        if sm["ok"] and not self.chk_dry.isChecked():
            self.log_view.appendPlainText(
                "Nächster Schritt: im Hauptfenster 'Sync (PC >> Reader)' ausführen "
                "(Option 'Lese-Cache geänderter ePubs löschen' beachten).")
        self.worker = None

    def _cancel(self) -> None:
        if self.worker:
            self.worker.cancel()
            self.btn_cancel.setEnabled(False)

    def reject(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(10000)
        super().reject()
