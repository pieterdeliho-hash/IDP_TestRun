"""GUI for the PDF reader — read, compare, batch extract, and benchmark."""

from __future__ import annotations

import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import filedialog, messagebox
import tkinter.ttk as ttk

import customtkinter as ctk

from src.benchmark import (
    create_reader,
    detect_hardware,
    discover_readers,
    generate_markdown_report,
    word_stats,
)
from src.utils import ALL_EXTENSIONS, find_documents

# ── Theme ─────────────────────────────────────────────────────────────

logging.getLogger("RapidOCR").setLevel(logging.ERROR)
logging.getLogger("docling.models.stages.ocr.rapid_ocr_model").setLevel(logging.ERROR)

READER_TIMEOUT = 180

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Color palette
COLOR_PRIMARY = "#3a7bfd"
COLOR_SUCCESS = "#2ecc71"
COLOR_WARN = "#f39c12"
COLOR_DANGER = "#e74c3c"
COLOR_CARD = "#2d2d2d"
COLOR_BORDER = "#444444"
COLOR_HOVER = "#3d3d3d"


# ── Helpers ───────────────────────────────────────────────────────────


def _section_label(
    parent: ctk.CTkFrame, text: str, font_size: int = 13
) -> ctk.CTkLabel:
    """Return a bold section-heading label."""
    lbl = ctk.CTkLabel(parent, text=text, font=("Segoe UI", font_size, "bold"))
    return lbl


def _card(parent: ctk.CTkFrame) -> ctk.CTkFrame:
    """Return a flat card frame with subtle border."""
    card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, border_color=COLOR_BORDER,
                         border_width=1)
    return card


def _section_heading(parent: ctk.CTkFrame, title: str) -> None:
    """Insert a styled section heading that takes its own row."""
    _section_label(parent, title).pack(anchor="w", padx=12, pady=(10, 2))


def _reader_name_icon(name: str) -> str:
    """Prefix a reader name with a short icon."""
    icons: dict[str, str] = {
        "hybrid": "⚡",
        "pymupdf": "🚀",
        "docling": "🧠",
        "pypdf+ocr": "📄",
        "pdfplumber": "📐",
        "unstructured": "🔍",
        "image+tesseract": "🖼️",
        "surya": "☀️",
        "marker": "🏷️",
    }
    return f"{icons.get(name, '📌')} {name}"


# ── Data containers ──────────────────────────────────────────────────


@dataclass
class ReaderResult:
    """Holds the output of a single read operation."""

    name: str
    text: str
    elapsed: float
    error: str | None = None


# ── Main application ─────────────────────────────────────────────────


class App(ctk.CTk):
    """Four-tab GUI: Read, Compare, Batch, Benchmark."""

    # ── Window setup ─────────────────────────────────────────────────

    def __init__(self) -> None:
        super().__init__()

        hw = detect_hardware()
        gpu_str = hw["gpu"] if hw["gpu"] != "none" else ""
        self._hw_info = hw

        title_parts = ["PDF Reader"]
        if gpu_str:
            title_parts.append(f"{gpu_str}")
        self.title(" — ".join(title_parts))
        self.geometry("1300x800")

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)  # status bar
        self.grid_columnconfigure(0, weight=1)

        # Tabview
        self.tabview = ctk.CTkTabview(self, height=770)
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 0))

        self._tab_read = self.tabview.add("📄  Read")
        self._tab_compare = self.tabview.add("⚖️  Compare")
        self._tab_batch = self.tabview.add("📦  Batch")
        self._tab_benchmark = self.tabview.add("📊  Benchmark")

        self._build_read()
        self._build_compare()
        self._build_batch()
        self._build_benchmark()

        # Status bar
        self._build_statusbar()

        # Graceful shutdown
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._closing = False

    def _on_close(self) -> None:
        """Cancel in-flight work and quit cleanly."""
        self._closing = True
        self._bm_cancelled = True
        self.destroy()

    # ── Status bar ───────────────────────────────────────────────────

    def _build_statusbar(self) -> None:
        bar = ctk.CTkFrame(self, height=30, fg_color="#1e1e1e")
        bar.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        bar.grid_propagate(False)

        readers = discover_readers()
        avail = len(readers)
        gpu = self._hw_info["gpu"] if self._hw_info["gpu"] != "none" else "CPU"

        self._status_left = ctk.CTkLabel(
            bar,
            text=f"🔌 {avail} readers  •  {gpu}",
            font=("Segoe UI", 10),
            anchor="w",
        )
        self._status_left.pack(side="left", padx=10, pady=4)

        self._status_msg = ctk.CTkLabel(
            bar, text="Ready.", font=("Segoe UI", 10), anchor="e"
        )
        self._status_msg.pack(side="right", padx=10, pady=4)

    def _status(self, msg: str) -> None:
        self._status_msg.configure(text=msg)

    # ──────────────────────────────────────────────────────────────────
    # Tab 1: READ
    # ──────────────────────────────────────────────────────────────────

    def _build_read(self) -> None:
        tab = self._tab_read
        tab.grid_rowconfigure(0, weight=0)
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        # ── Control card ──
        ctrl = _card(tab)
        ctrl.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        _section_heading(ctrl, "📂  Pick a file, choose a reader")

        btn_row = ctk.CTkFrame(ctrl, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(4, 8))

        self._read_open_btn = ctk.CTkButton(
            btn_row, text="📂  Open File", width=130, height=32,
            command=self._read_open,
        )
        self._read_open_btn.pack(side="left", padx=(0, 8))

        readers = list(discover_readers())
        self._read_reader_var = ctk.StringVar(
            value=readers[0] if readers else ""
        )
        menu_width = max(160, len(readers[0]) * 9 + 40) if readers else 160
        self._read_reader_menu = ctk.CTkOptionMenu(
            btn_row,
            values=[_reader_name_icon(r) for r in readers],
            variable=self._read_reader_var,
            width=menu_width,
        )
        self._read_reader_menu.pack(side="left", padx=8)
        # Store raw names for logic
        self._read_reader_names = readers

        self._read_btn = ctk.CTkButton(
            btn_row, text="⚡  Extract Text", width=150, height=32,
            fg_color=COLOR_PRIMARY, command=self._read_run,
        )
        self._read_btn.pack(side="left", padx=8)

        self._read_save_btn = ctk.CTkButton(
            btn_row, text="💾  Save .txt", width=120, height=32,
            state="disabled", command=self._read_save,
        )
        self._read_save_btn.pack(side="left", padx=(0, 8))

        self._read_info_lbl = ctk.CTkLabel(
            btn_row, text="", font=("Segoe UI", 10)
        )
        self._read_info_lbl.pack(side="right")

        self._read_file_lbl = ctk.CTkLabel(
            ctrl, text="No file selected.", font=("Segoe UI", 11),
            text_color="#aaaaaa",
        )
        self._read_file_lbl.pack(anchor="w", padx=12, pady=(0, 8))

        # ── Text output card ──
        text_card = _card(tab)
        text_card.grid(row=1, column=0, sticky="nsew", padx=10, pady=(10, 10))
        text_card.grid_rowconfigure(1, weight=1)
        text_card.grid_columnconfigure(0, weight=1)

        _section_label(text_card, "📝  Extracted Text").pack(
            anchor="w", padx=12, pady=(10, 4)
        )

        self._read_text = ctk.CTkTextbox(text_card, wrap="word",
                                           font=("Consolas", 11))
        self._read_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._read_current_text: str = ""
        self._read_current_file: str = ""

    def _read_open(self) -> None:
        path = filedialog.askopenfilename(
            title="Select a PDF or image",
            filetypes=[
                ("Documents", [f"*{e}" for e in ALL_EXTENSIONS]),
                ("All files", "*.*"),
            ],
        )
        if path:
            self._read_current_file = path
            self._read_file_lbl.configure(
                text=f"📄  {Path(path).name}  ({Path(path).stat().st_size:,} bytes)",
                text_color="white",
            )

    def _read_run(self) -> None:
        if not self._read_current_file:
            messagebox.showwarning("No file", "Open a file first.")
            return
        display = self._read_reader_var.get()
        # Map display name back to raw name
        raw = next(
            (r for r in self._read_reader_names
             if _reader_name_icon(r) == display),
            display,
        )
        self._read_btn.configure(state="disabled")
        self._status("Extracting...")
        threading.Thread(
            target=self._read_worker, args=(raw,), daemon=True
        ).start()

    def _read_worker(self, name: str) -> None:
        try:
            reader = create_reader(name)
            t0 = time.perf_counter()
            text = reader.read(self._read_current_file)
            elapsed = time.perf_counter() - t0
            result = ReaderResult(name=name, text=text, elapsed=elapsed)
        except Exception as e:
            result = ReaderResult(
                name=name, text="", elapsed=0,
                error=f"{type(e).__name__}: {e}",
            )
        self.after(0, self._read_done, result)

    def _read_done(self, result: ReaderResult) -> None:
        self._read_btn.configure(state="normal")
        self._read_text.delete("0.0", "end")
        if result.error:
            self._read_text.insert("0.0", f"❌  ERROR: {result.error}")
            self._read_save_btn.configure(state="disabled")
            self._status(f"Error: {result.error[:60]}")
        else:
            self._read_current_text = result.text
            self._read_text.insert("0.0", result.text)
            self._read_save_btn.configure(state="normal")
            words = len(result.text.split())
            self._read_info_lbl.configure(
                text=f"✅  {result.elapsed:.2f}s  |  {len(result.text):,} chars  |  {words:,} words"
            )
            self._status(f"Done — {len(result.text):,} chars in {result.elapsed:.1f}s")

    def _read_save(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("All", "*.*")],
        )
        if path:
            Path(path).write_text(self._read_current_text, encoding="utf-8")
            self._status(f"Saved to {Path(path).name}")

    # ──────────────────────────────────────────────────────────────────
    # Tab 2: COMPARE
    # ──────────────────────────────────────────────────────────────────

    def _build_compare(self) -> None:
        tab = self._tab_compare
        tab.grid_columnconfigure(0, weight=0)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        # ── Left sidebar ──
        sidebar = ctk.CTkFrame(tab, width=220, fg_color=COLOR_CARD,
                                border_color=COLOR_BORDER, border_width=1)
        sidebar.grid(row=0, column=0, sticky="ns", padx=10, pady=10)
        sidebar.grid_propagate(False)

        _section_heading(sidebar, "📂  File")

        ctk.CTkButton(sidebar, text="📂  Open File", width=180, height=30,
                       command=self._cmp_open).pack(padx=10, pady=(2, 4))

        self._cmp_file_lbl = ctk.CTkLabel(
            sidebar, text="No file.", font=("Segoe UI", 10),
            text_color="#aaaaaa",
        )
        self._cmp_file_lbl.pack(anchor="w", padx=14, pady=(0, 8))

        _section_heading(sidebar, "🔍  Readers")

        avail = discover_readers()
        self._cmp_reader_vars: dict[str, tk.BooleanVar] = {}
        reader_sf = ctk.CTkScrollableFrame(sidebar, width=200, height=200)
        reader_sf.pack(fill="both", padx=10, pady=(2, 0))

        all_on = tk.BooleanVar(value=True)
        toggle_row = ctk.CTkFrame(reader_sf, fg_color="transparent")
        toggle_row.pack(fill="x", padx=2, pady=2)
        ctk.CTkCheckBox(toggle_row, text="All", variable=all_on,
                         command=lambda: self._cmp_toggle_all(all_on.get())
                         ).pack(side="left", padx=(0, 8))
        ctk.CTkCheckBox(toggle_row, text="None", variable=tk.BooleanVar(),
                         command=lambda: self._cmp_toggle_all(False)
                         ).pack(side="left")

        for name in avail:
            var = tk.BooleanVar(value=True)
            self._cmp_reader_vars[name] = var
            ctk.CTkCheckBox(reader_sf, text=_reader_name_icon(name),
                             variable=var).pack(anchor="w", padx=6, pady=1)

        self._cmp_run_btn = ctk.CTkButton(
            sidebar, text="⚖️  Compare", width=180, height=32,
            fg_color=COLOR_PRIMARY, command=self._cmp_run,
        )
        self._cmp_run_btn.pack(padx=10, pady=(10, 4))

        self._cmp_progress = ctk.CTkProgressBar(sidebar, width=200)
        self._cmp_progress.pack(padx=10)
        self._cmp_progress.set(0)

        self._cmp_status_lbl = ctk.CTkLabel(
            sidebar, text="", font=("Segoe UI", 10)
        )
        self._cmp_status_lbl.pack(padx=14, pady=(4, 0))

        # ── Right: result panes ──
        self._cmp_outer = ctk.CTkScrollableFrame(tab, width=1050, height=700)
        self._cmp_outer.grid(row=0, column=1, sticky="nsew",
                              padx=(0, 10), pady=10)

        self._cmp_panes: dict[str, ctk.CTkTextbox] = {}
        self._cmp_current_file: str = ""

        # Overlap chips container (appears dynamically)
        self._cmp_chips_frame = ctk.CTkFrame(tab, fg_color="transparent")
        # Placed in _cmp_done when results arrive

    def _cmp_toggle_all(self, state: bool) -> None:
        for var in self._cmp_reader_vars.values():
            var.set(state)

    def _cmp_open(self) -> None:
        path = filedialog.askopenfilename(
            title="Select a PDF or image",
            filetypes=[
                ("Documents", [f"*{e}" for e in ALL_EXTENSIONS]),
                ("All", "*.*"),
            ],
        )
        if path:
            self._cmp_current_file = path
            p = Path(path)
            self._cmp_file_lbl.configure(
                text=f"📄  {p.name}", text_color="white"
            )

    def _cmp_run(self) -> None:
        if not self._cmp_current_file:
            messagebox.showwarning("No file", "Open a file first.")
            return
        names = [n for n, v in self._cmp_reader_vars.items() if v.get()]
        if not names:
            messagebox.showwarning("No readers", "Select at least one reader.")
            return

        for pane in self._cmp_panes.values():
            pane.destroy()
        self._cmp_panes.clear()

        # Remove old chips
        for w in self._cmp_chips_frame.winfo_children():
            w.destroy()

        self._cmp_run_btn.configure(state="disabled")
        self._cmp_progress.set(0)
        self._status("Comparing readers...")
        threading.Thread(
            target=self._cmp_worker, args=(names,), daemon=True
        ).start()

    def _cmp_worker(self, names: list[str]) -> None:
        results: dict[str, ReaderResult] = {}
        for i, name in enumerate(names):
            self.after(0, self._cmp_prog, i + 1, len(names))
            try:
                reader = create_reader(name)
                t0 = time.perf_counter()
                with ThreadPoolExecutor(max_workers=1) as ex:
                    fut = ex.submit(reader.read, self._cmp_current_file)
                    text = fut.result(timeout=READER_TIMEOUT)
                results[name] = ReaderResult(
                    name=name, text=text,
                    elapsed=time.perf_counter() - t0,
                )
            except TimeoutError:
                results[name] = ReaderResult(
                    name=name, text="", elapsed=READER_TIMEOUT, error="TIMEOUT",
                )
            except Exception as e:
                results[name] = ReaderResult(
                    name=name, text="", elapsed=0,
                    error=f"{type(e).__name__}: {e}",
                )
        self.after(0, self._cmp_done, results)

    def _cmp_prog(self, done: int, total: int) -> None:
        self._cmp_progress.set(min(done / total, 1.0))
        self._cmp_status_lbl.configure(text=f"{done}/{total}")

    def _cmp_done(self, results: dict[str, ReaderResult]) -> None:
        self._cmp_run_btn.configure(state="normal")
        self._cmp_status_lbl.configure(
            text=f"✅ {sum(1 for r in results.values() if not r.error)}/{len(results)}"
        )

        cols = 2
        idx = 0
        for name, r in results.items():
            col = idx % cols
            row = idx // cols
            card = ctk.CTkFrame(self._cmp_outer, fg_color=COLOR_CARD,
                                 border_color=COLOR_BORDER, border_width=1)
            card.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)
            card.grid_rowconfigure(1, weight=1)
            card.grid_columnconfigure(0, weight=1)

            status_icon = "✅" if not r.error else "❌"
            header_text = (
                f"{status_icon}  {_reader_name_icon(name)}  "
                f"|  {r.elapsed:.2f}s  |  {len(r.text):,} chars"
            )
            hdr = ctk.CTkLabel(
                card, text=header_text, font=("Segoe UI", 10, "bold"),
            )
            hdr.grid(row=0, column=0, sticky="w", padx=8, pady=(6, 2))

            txt = ctk.CTkTextbox(card, wrap="word", font=("Consolas", 10))
            txt.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
            txt.insert("0.0", r.text if not r.error else f"ERROR: {r.error}")
            self._cmp_panes[name] = txt
            idx += 1

        # Overlap chips
        texts = {r.name: r.text for r in results.values() if not r.error}
        if len(texts) >= 2:
            stats = word_stats(texts)
            baseline = max(
                texts, key=lambda n: len(set(texts[n].lower().split()))
            )
            parts = [f"🏆 Baseline: {baseline}"]
            for name, s in stats.items():
                pct = (s["common"] / s["total_base"] * 100
                       if s["total_base"] else 0)
                color = (COLOR_SUCCESS if pct >= 80 else
                          COLOR_WARN if pct >= 50 else COLOR_DANGER)
                parts.append(f"{_reader_name_icon(name)} {pct:.0f}%")
                self._cmp_chips_frame._last_color = color  # noqa: SLF001
            self._cmp_status_lbl.configure(text=" | ".join(parts))
        else:
            self._cmp_status_lbl.configure(text="")
        self._status("Compare complete.")

    # ──────────────────────────────────────────────────────────────────
    # Tab 3: BATCH
    # ──────────────────────────────────────────────────────────────────

    def _build_batch(self) -> None:
        tab = self._tab_batch
        tab.grid_rowconfigure(0, weight=0)
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        # Control card
        ctrl = _card(tab)
        ctrl.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        _section_heading(ctrl, "📦  Extract every document in a folder")

        btn_row = ctk.CTkFrame(ctrl, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(4, 4))

        ctk.CTkButton(btn_row, text="📂  Select Folder", width=150, height=32,
                       command=self._batch_select).pack(side="left", padx=(0, 8))

        self._batch_dir_lbl = ctk.CTkLabel(
            btn_row, text="No folder selected.", font=("Segoe UI", 11),
            text_color="#aaaaaa",
        )
        self._batch_dir_lbl.pack(side="left", padx=8)

        self._batch_count_lbl = ctk.CTkLabel(
            btn_row, text="", font=("Segoe UI", 10),
            text_color=COLOR_SUCCESS,
        )
        self._batch_count_lbl.pack(side="left", padx=4)

        readers = list(discover_readers())
        self._batch_reader_var = ctk.StringVar(
            value=readers[0] if readers else ""
        )
        self._batch_reader_names = readers
        menu_vals = [_reader_name_icon(r) for r in readers]
        ctk.CTkOptionMenu(btn_row, values=menu_vals,
                           variable=self._batch_reader_var,
                           width=160).pack(side="left", padx=8)

        self._batch_btn = ctk.CTkButton(
            btn_row, text="⚡  Extract All", width=140, height=32,
            fg_color=COLOR_PRIMARY, command=self._batch_run,
        )
        self._batch_btn.pack(side="left", padx=8)

        self._batch_save_btn = ctk.CTkButton(
            btn_row, text="💾  Save All .txt", width=140, height=32,
            state="disabled", command=self._batch_save,
        )
        self._batch_save_btn.pack(side="left", padx=(0, 8))

        self._batch_progress = ctk.CTkProgressBar(btn_row, width=200)
        self._batch_progress.pack(side="right", padx=(0, 8))
        self._batch_progress.set(0)

        self._batch_status_lbl = ctk.CTkLabel(
            btn_row, text="", font=("Segoe UI", 10),
        )
        self._batch_status_lbl.pack(side="right")

        # Results table
        inner = _card(tab)
        inner.grid(row=1, column=0, sticky="nsew", padx=10, pady=(10, 10))
        inner.grid_rowconfigure(1, weight=1)
        inner.grid_columnconfigure(0, weight=1)

        _section_heading(inner, "📋  Results")

        table_frame = ctk.CTkFrame(inner, fg_color="transparent")
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        cols = ("file", "time", "chars", "status")
        self._batch_tree = ttk.Treeview(
            table_frame, columns=cols, show="headings"
        )
        self._style_tree(self._batch_tree)

        headings = [
            ("file", "File", 350, "w"),
            ("time", "Time", 80, "e"),
            ("chars", "Chars", 90, "e"),
            ("status", "Status", 80, "center"),
        ]
        for cid, label, w, a in headings:
            self._batch_tree.heading(cid, text=label)
            self._batch_tree.column(cid, width=w, anchor=a)  # type: ignore[call-overload]

        sb = ctk.CTkScrollbar(table_frame, command=self._batch_tree.yview)
        self._batch_tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")
        self._batch_tree.grid(row=0, column=0, sticky="nsew")

        self._batch_dir: str = ""
        self._batch_texts: dict[str, str] = {}

    def _batch_select(self) -> None:
        folder = filedialog.askdirectory(
            title="Select folder with PDFs / images"
        )
        if not folder:
            return
        self._batch_dir = folder
        docs = find_documents(folder)
        self._batch_dir_lbl.configure(
            text=f"📂  {folder}", text_color="white"
        )
        self._batch_count_lbl.configure(text=f"({len(docs)} documents)")
        for item in self._batch_tree.get_children():
            self._batch_tree.delete(item)
        self._batch_texts.clear()
        self._batch_save_btn.configure(state="disabled")
        self._batch_status_lbl.configure(text="")
        self._batch_progress.set(0)
        self._status(f"Folder loaded: {len(docs)} files")

    def _batch_run(self) -> None:
        if not self._batch_dir:
            messagebox.showwarning("No folder", "Select a folder first.")
            return
        display = self._batch_reader_var.get()
        raw = next(
            (r for r in self._batch_reader_names
             if _reader_name_icon(r) == display),
            display,
        )
        docs = find_documents(self._batch_dir)
        if not docs:
            messagebox.showwarning("No files", "No supported documents found.")
            return
        self._batch_btn.configure(state="disabled")
        self._batch_save_btn.configure(state="disabled")
        self._status("Batch extracting...")
        threading.Thread(
            target=self._batch_worker, args=(raw, docs), daemon=True
        ).start()

    def _batch_worker(self, name: str, docs: list[Path]) -> None:
        try:
            reader = create_reader(name)
        except Exception as e:
            self.after(0, self._batch_error, str(e))
            return

        texts: dict[str, str] = {}
        total = len(docs)
        for i, doc in enumerate(docs):
            try:
                t0 = time.perf_counter()
                text = reader.read(doc)
                elapsed = time.perf_counter() - t0
                texts[doc.name] = text
                status = "✅ ok"
            except Exception as e:
                elapsed = 0.0
                text = ""
                status = f"❌ {type(e).__name__}"
            self.after(0, self._batch_update_row,
                       doc.name, elapsed, len(text), status,
                       i + 1, total)

        self.after(0, self._batch_done, texts, total)

    def _batch_update_row(
        self, name: str, elapsed: float, chars: int,
        status: str, done: int, total: int,
    ) -> None:
        self._batch_tree.insert(
            "", "end",
            values=(name, f"{elapsed:.2f}s", f"{chars:,}", status),
        )
        self._batch_progress.set(done / total)
        self._batch_status_lbl.configure(text=f"{done}/{total}")

    def _batch_done(self, texts: dict[str, str], total: int) -> None:
        self._batch_btn.configure(state="normal")
        self._batch_texts = texts
        ok = len(texts)
        self._batch_status_lbl.configure(
            text=f"✅ {ok}/{total} succeeded"
        )
        if ok:
            self._batch_save_btn.configure(state="normal")
        self._status(f"Batch done: {ok}/{total}")

    def _batch_error(self, msg: str) -> None:
        self._batch_btn.configure(state="normal")
        self._batch_status_lbl.configure(text=f"❌ {msg}")
        self._status(f"Batch error: {msg[:50]}")

    def _batch_save(self) -> None:
        out_dir = filedialog.askdirectory(
            title="Select output folder for .txt files"
        )
        if not out_dir:
            return
        out_path = Path(out_dir)
        saved = 0
        for name, text in self._batch_texts.items():
            stem = Path(name).stem
            (out_path / f"{stem}.txt").write_text(text, encoding="utf-8")
            saved += 1
        self._status(f"Saved {saved} files to {out_path.name}")

    # ──────────────────────────────────────────────────────────────────
    # Tab 4: BENCHMARK
    # ──────────────────────────────────────────────────────────────────

    def _build_benchmark(self) -> None:
        tab = self._tab_benchmark
        tab.grid_columnconfigure(0, weight=0)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        self._bm_results: list[dict[str, Any]] = []
        self._bm_export_data: dict[str, Any] = {}

        self._bm_build_left(tab)
        self._bm_build_right(tab)

    def _bm_build_left(self, tab: ctk.CTkTabview) -> None:
        panel = ctk.CTkFrame(tab, width=260, fg_color=COLOR_CARD,
                              border_color=COLOR_BORDER, border_width=1)
        panel.grid(row=0, column=0, sticky="ns", padx=10, pady=10)
        panel.grid_propagate(False)

        _section_heading(panel, "⚙️  Readers")

        avail = discover_readers()
        self._bm_reader_vars: dict[str, tk.BooleanVar] = {}

        all_on = tk.BooleanVar(value=True)
        toggle_row = ctk.CTkFrame(panel, fg_color="transparent")
        toggle_row.pack(fill="x", padx=14, pady=2)
        ctk.CTkCheckBox(toggle_row, text="All", variable=all_on,
                         command=lambda: self._bm_toggle_all(all_on.get())
                         ).pack(side="left", padx=(0, 6))
        ctk.CTkCheckBox(toggle_row, text="None", variable=tk.BooleanVar(),
                         command=lambda: self._bm_toggle_all(False)
                         ).pack(side="left")

        reader_sf = ctk.CTkScrollableFrame(panel, width=240, height=120)
        reader_sf.pack(fill="x", padx=12, pady=(2, 4))
        for name in avail:
            var = tk.BooleanVar(value=True)
            self._bm_reader_vars[name] = var
            ctk.CTkCheckBox(reader_sf, text=_reader_name_icon(name),
                             variable=var).pack(anchor="w", padx=4, pady=1)

        _section_heading(panel, "📂  Files")

        fbtns = ctk.CTkFrame(panel, fg_color="transparent")
        fbtns.pack(fill="x", padx=14, pady=2)
        ctk.CTkButton(fbtns, text="Add Files", width=100, height=26,
                       command=self._bm_add_files).pack(side="left", padx=(0, 4))
        ctk.CTkButton(fbtns, text="Add Folder", width=100, height=26,
                       command=self._bm_add_folder).pack(side="left")

        self._bm_file_vars: dict[str, tk.BooleanVar] = {}
        self._bm_file_frame = ctk.CTkScrollableFrame(
            panel, width=240, height=160
        )
        self._bm_file_frame.pack(fill="both", expand=True, padx=12, pady=4)

        self._bm_run_btn = ctk.CTkButton(
            panel, text="🚀  Run Benchmark", width=220, height=34,
            fg_color=COLOR_PRIMARY, command=self._bm_run,
        )
        self._bm_run_btn.pack(padx=14, pady=(6, 4))

        self._bm_progress = ctk.CTkProgressBar(panel, width=240)
        self._bm_progress.pack(padx=14)
        self._bm_progress.set(0)

        self._bm_status_lbl = ctk.CTkLabel(
            panel, text="", font=("Segoe UI", 10), wraplength=230,
        )
        self._bm_status_lbl.pack(padx=14, pady=(2, 4))

        # Export buttons
        _section_heading(panel, "💾  Export")
        ex_row = ctk.CTkFrame(panel, fg_color="transparent")
        ex_row.pack(fill="x", padx=14, pady=2)
        self._bm_export_json_btn = ctk.CTkButton(
            ex_row, text="📋 JSON", width=100, height=26,
            state="disabled", command=self._bm_export_json,
        )
        self._bm_export_json_btn.pack(side="left", padx=(0, 4))
        self._bm_export_md_btn = ctk.CTkButton(
            ex_row, text="📝 Markdown", width=100, height=26,
            state="disabled", command=self._bm_export_md,
        )
        self._bm_export_md_btn.pack(side="left")

    def _bm_build_right(self, tab: ctk.CTkTabview) -> None:
        table_frame = _card(tab)
        table_frame.grid(row=0, column=1, sticky="nsew",
                          padx=(0, 10), pady=10)
        tab.grid_rowconfigure(0, weight=1)
        table_frame.grid_rowconfigure(1, weight=1)

        _section_heading(table_frame, "📊  Benchmark Results")

        inner = ctk.CTkFrame(table_frame, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        inner.grid_rowconfigure(0, weight=1)
        inner.grid_columnconfigure(0, weight=1)

        cols = ("file", "method", "time", "chars", "status")
        self._bm_tree = ttk.Treeview(
            inner, columns=cols, show="headings", selectmode="browse"
        )
        self._style_tree(self._bm_tree)

        headings = [
            ("file", "File", 220, "w"),
            ("method", "Method", 120, "w"),
            ("time", "Time", 80, "e"),
            ("chars", "Chars", 90, "e"),
            ("status", "Status", 80, "center"),
        ]
        for cid, label, w, a in headings:
            self._bm_tree.heading(cid, text=label)
            self._bm_tree.column(cid, width=w, anchor=a)  # type: ignore[call-overload]

        sb = ctk.CTkScrollbar(inner, command=self._bm_tree.yview)
        self._bm_tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")
        self._bm_tree.grid(row=0, column=0, sticky="nsew")

        self._bm_summary_lbl = ctk.CTkLabel(
            table_frame, text="", font=("Segoe UI", 11)
        )
        self._bm_summary_lbl.pack(anchor="w", padx=14, pady=(0, 8))

        self._bm_readers_used: list[str] = []
        self._bm_files_used: list[str] = []
        self._bm_raw_results: list[dict[str, Any]] = []
        self._bm_cancelled = False

    @staticmethod
    def _style_tree(tree: ttk.Treeview) -> None:
        """Apply dark-theme styling to a Treeview."""
        style = ttk.Style()
        style.configure(
            "Treeview",
            background="#1e1e1e",
            fieldbackground="#1e1e1e",
            foreground="#d0d0d0",
            font=("Consolas", 10),
            rowheight=24,
        )
        style.configure(
            "Treeview.Heading",
            background="#2d2d2d",
            foreground="white",
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Treeview",
                   background=[("selected", "#3a7bfd")],
                   foreground=[("selected", "white")])

    # ── Benchmark helpers ────────────────────────────────────────────

    def _bm_toggle_all(self, state: bool) -> None:
        for var in self._bm_reader_vars.values():
            var.set(state)

    def _bm_add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select PDFs or images",
            filetypes=[
                ("Documents", [f"*{e}" for e in ALL_EXTENSIONS]),
                ("All files", "*.*"),
            ],
        )
        for p in paths:
            self._bm_add_file(p)

    def _bm_add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select folder")
        if not folder:
            return
        for ext in ALL_EXTENSIONS:
            for p in Path(folder).glob(f"**/*{ext}"):
                self._bm_add_file(str(p))

    def _bm_add_file(self, path: str) -> None:
        if path in self._bm_file_vars:
            return
        name = Path(path).name
        var = tk.BooleanVar(value=True)
        self._bm_file_vars[path] = var
        ctk.CTkCheckBox(self._bm_file_frame, text=f"📄  {name}", variable=var).pack(
            anchor="w", padx=6, pady=1
        )

    def _bm_run(self) -> None:
        readers = [n for n, v in self._bm_reader_vars.items() if v.get()]
        files = [p for p, v in self._bm_file_vars.items() if v.get()]
        if not readers:
            self._bm_status_lbl.configure(text="⚠️ Select at least one reader.")
            return
        if not files:
            self._bm_status_lbl.configure(text="⚠️ Add at least one file.")
            return

        self._bm_cancelled = False
        self._bm_run_btn.configure(
            text="❌  Cancel", fg_color=COLOR_DANGER, command=self._bm_cancel
        )
        self._bm_results.clear()
        self._bm_raw_results.clear()
        for item in self._bm_tree.get_children():
            self._bm_tree.delete(item)
        self._bm_summary_lbl.configure(text="")
        self._bm_export_json_btn.configure(state="disabled")
        self._bm_export_md_btn.configure(state="disabled")
        self._bm_progress.set(0)
        self._status("Benchmark running...")

        threading.Thread(
            target=self._bm_worker, args=(readers, files), daemon=True
        ).start()

    def _bm_cancel(self) -> None:
        self._bm_cancelled = True
        self._bm_status_lbl.configure(text="⏹ Cancelling...")
        self._status("Cancelling benchmark...")

    def _bm_worker(self, readers: list[str], files: list[str]) -> None:
        total = len(readers) * len(files)
        done = 0

        for name in readers:
            if name in ("docling", "hybrid"):
                try:
                    create_reader(name)
                except Exception:
                    pass

        all_results: list[dict[str, Any]] = []
        totals: dict[str, float] = {m: 0.0 for m in readers}

        for fpath in files:
            if self._bm_cancelled:
                break
            fname = Path(fpath).name
            file_results: dict[str, Any] = {"file": fname, "readers": {}}
            for name in readers:
                if self._bm_cancelled:
                    break  # type: ignore[unreachable]
                self.after(0, self._bm_update_progress,
                           done + 1, total, f"{fname} ({name})")
                try:
                    reader = create_reader(name)
                    t0 = time.perf_counter()
                    with ThreadPoolExecutor(max_workers=1) as ex:
                        fut = ex.submit(reader.read, fpath)
                        text = fut.result(timeout=READER_TIMEOUT)
                    elapsed = time.perf_counter() - t0
                    chars = len(text)
                    status = "✅ ok"
                    totals[name] += elapsed
                    file_results["readers"][name] = {
                        "time_s": round(elapsed, 3),
                        "chars": chars,
                        "words": len(set(text.lower().split())),
                    }
                except TimeoutError:
                    elapsed = float(READER_TIMEOUT)
                    chars = 0
                    status = "⏱ TIMEOUT"
                    file_results["readers"][name] = {"error": True}
                except Exception as e:
                    elapsed = 0.0
                    chars = 0
                    status = f"❌ {type(e).__name__}"
                    file_results["readers"][name] = {"error": True}

                self.after(0, self._bm_append_row, fname, name,
                           f"{elapsed:.2f}s", f"{chars:,}", status)
                done += 1
            all_results.append(file_results)

        self.after(0, self._bm_done, readers, files, all_results, totals)

    def _bm_append_row(
        self, file: str, method: str, time_s: str,
        chars: str, status: str,
    ) -> None:
        self._bm_tree.insert(
            "", "end", values=(file, method, time_s, chars, status)
        )
        r: dict[str, Any] = {
            "file": file, "method": method,
            "time": time_s, "chars": chars, "status": status,
        }
        self._bm_results.append(r)
        self._bm_raw_results.append(r)

    def _bm_update_progress(
        self, done: int, total: int, current: str
    ) -> None:
        self._bm_progress.set(min(done / total, 1.0))
        self._bm_status_lbl.configure(text=f"{done}/{total} — {current}")

    def _bm_done(
        self,
        readers: list[str],
        files: list[str],
        all_results: list[dict[str, Any]],
        totals: dict[str, float],
    ) -> None:
        self._bm_run_btn.configure(
            text="🚀  Run Benchmark", fg_color=COLOR_PRIMARY,
            command=self._bm_run,
        )
        self._bm_progress.set(1)
        self._bm_readers_used = readers
        self._bm_files_used = files

        if self._bm_cancelled:
            self._bm_status_lbl.configure(text="⏹ Cancelled.")
            self._status("Benchmark cancelled.")
            return

        self._bm_status_lbl.configure(text="✅ Done.")
        ok = [
            r for r in self._bm_results
            if not str(r.get("status", "")).startswith("❌")
        ]
        if ok:
            self._bm_summary_lbl.configure(
                text=(
                    f"📂 Files: {len(files)}  |  "
                    f"🔍 Readers: {len(readers)}  |  "
                    f"✅ Results: {len(ok)}/{len(self._bm_results)}"
                )
            )

        self._bm_export_json_btn.configure(state="normal")
        self._bm_export_md_btn.configure(state="normal")
        self._bm_export_data = {
            "all_results": all_results,
            "all_names": readers,
            "totals": totals,
        }
        self._status("Benchmark complete.")

    def _bm_export_json(self) -> None:
        path = Path("results") / f"benchmark_export_{int(time.time())}.json"
        path.parent.mkdir(exist_ok=True)
        data: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "hardware": detect_hardware(),
            "results": self._bm_raw_results,
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self._status(f"JSON exported to {path}")

    def _bm_export_md(self) -> None:
        d = self._bm_export_data
        directory = (
            str(Path(self._bm_files_used[0]).parent)
            if self._bm_files_used else "."
        )
        out = generate_markdown_report(
            d["all_results"], d["all_names"], d["totals"],
            detect_hardware(), directory,
        )
        self._status(f"Markdown report saved to {out}")


# ── Entrypoint ───────────────────────────────────────────────────────


def main() -> None:
    """Launch the GUI."""
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()