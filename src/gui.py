"""GUI for the PDF reader — read, compare, and benchmark document readers."""

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

# Suppress noisy logs during GUI runs
logging.getLogger("RapidOCR").setLevel(logging.ERROR)
logging.getLogger("docling.models.stages.ocr.rapid_ocr_model").setLevel(logging.ERROR)

READER_TIMEOUT = 180

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


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
    """Three-tab GUI: Read, Compare, Benchmark."""

    def __init__(self) -> None:
        super().__init__()
        hw = detect_hardware()
        gpu_str = hw["gpu"] if hw["gpu"] != "none" else ""
        title = "PDF Reader" + (f" | {gpu_str}" if gpu_str else "")
        self.title(title)
        self.geometry("1100x720")

        # Tabview
        self.tabview = ctk.CTkTabview(self, height=700)
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._tab_read = self.tabview.add("Read")
        self._tab_compare = self.tabview.add("Compare")
        self._tab_batch = self.tabview.add("Batch")
        self._tab_benchmark = self.tabview.add("Benchmark")

        self._build_read()
        self._build_compare()
        self._build_batch()
        self._build_benchmark()

        # Graceful shutdown on window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._closing = False

    def _on_close(self) -> None:
        """Cancel in-flight work and quit cleanly."""
        self._closing = True
        self._bm_cancelled = True
        self.destroy()

    # ──────────────────────────────────────────────────────────────────
    # Tab 1: READ — open a file with one reader, see the text
    # ──────────────────────────────────────────────────────────────────

    def _build_read(self) -> None:
        tab = self._tab_read
        tab.grid_rowconfigure(0, weight=0)
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        # Top controls
        ctrl = ctk.CTkFrame(tab)
        ctrl.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        ctk.CTkButton(ctrl, text="Open File", width=90, command=self._read_open).grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )

        self._read_file_lbl = ctk.CTkLabel(
            ctrl, text="(no file)", font=("Segoe UI", 11)
        )
        self._read_file_lbl.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        readers = list(discover_readers())
        self._read_reader_var = ctk.StringVar(value=readers[0] if readers else "")
        self._read_reader_menu = ctk.CTkOptionMenu(
            ctrl,
            values=readers,
            variable=self._read_reader_var,
            width=130,
        )
        self._read_reader_menu.grid(row=0, column=2, padx=5, pady=5)

        self._read_btn = ctk.CTkButton(
            ctrl, text="Read", width=70, command=self._read_run
        )
        self._read_btn.grid(row=0, column=3, padx=5, pady=5)

        self._read_save_btn = ctk.CTkButton(
            ctrl, text="Save .txt", width=80, state="disabled", command=self._read_save
        )
        self._read_save_btn.grid(row=0, column=4, padx=5, pady=5)

        self._read_info_lbl = ctk.CTkLabel(ctrl, text="", font=("Segoe UI", 10))
        self._read_info_lbl.grid(row=0, column=5, padx=5, pady=5, sticky="e")

        # Text display
        outer = ctk.CTkScrollableFrame(tab, width=1080, height=600)
        outer.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        self._read_text = ctk.CTkTextbox(outer, wrap="word")
        self._read_text.pack(fill="both", expand=True)

        self._read_current_text: str = ""
        self._read_current_file: str = ""

    def _read_open(self) -> None:
        path = filedialog.askopenfilename(
            title="Select a PDF or image",
            filetypes=[("Documents", [f"*{e}" for e in ALL_EXTENSIONS]), ("All", "*.*")],
        )
        if path:
            self._read_current_file = path
            self._read_file_lbl.configure(text=Path(path).name)

    def _read_run(self) -> None:
        if not self._read_current_file:
            messagebox.showwarning("No file", "Open a file first.")
            return
        name = self._read_reader_var.get()
        self._read_btn.configure(state="disabled")
        threading.Thread(
            target=self._read_worker, args=(name,), daemon=True
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
                name=name, text="", elapsed=0, error=f"{type(e).__name__}: {e}"
            )
        self.after(0, self._read_done, result)

    def _read_done(self, result: ReaderResult) -> None:
        self._read_btn.configure(state="normal")
        self._read_text.delete("0.0", "end")
        if result.error:
            self._read_text.insert("0.0", f"ERROR: {result.error}")
            self._read_save_btn.configure(state="disabled")
        else:
            self._read_current_text = result.text
            self._read_text.insert("0.0", result.text)
            self._read_save_btn.configure(state="normal")
        self._read_info_lbl.configure(
            text=f"{result.elapsed:.2f}s  |  {len(result.text):,} chars"
        )

    def _read_save(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("All", "*.*")],
        )
        if path:
            Path(path).write_text(self._read_current_text, encoding="utf-8")

    # ──────────────────────────────────────────────────────────────────
    # Tab 2: COMPARE — run multiple readers, see side-by-side text
    # ──────────────────────────────────────────────────────────────────

    def _build_compare(self) -> None:
        tab = self._tab_compare
        tab.grid_rowconfigure(0, weight=0)
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        # Controls
        ctrl = ctk.CTkFrame(tab)
        ctrl.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        ctk.CTkButton(ctrl, text="Open File", width=90, command=self._cmp_open).grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )

        self._cmp_file_lbl = ctk.CTkLabel(
            ctrl, text="(no file)", font=("Segoe UI", 11)
        )
        self._cmp_file_lbl.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # Reader checkboxes
        avail = discover_readers()
        self._cmp_reader_vars: dict[str, ctk.StringVar] = {}
        for i, name in enumerate(avail):
            var = ctk.StringVar(value=name)
            self._cmp_reader_vars[name] = var
            ctk.CTkCheckBox(ctrl, text=name, variable=var).grid(
                row=0, column=2 + i, padx=3, pady=5, sticky="w"
            )

        self._cmp_btn = ctk.CTkButton(
            ctrl, text="Compare", width=90, command=self._cmp_run
        )
        self._cmp_btn.grid(row=0, column=10, padx=5, pady=5, sticky="e")

        self._cmp_status_lbl = ctk.CTkLabel(ctrl, text="", font=("Segoe UI", 10))
        self._cmp_status_lbl.grid(row=0, column=11, padx=5, pady=5, sticky="e")

        # Overlap stats label (appears after compare)
        self._cmp_overlap_lbl = ctk.CTkLabel(
            ctrl, text="", font=("Segoe UI", 10)
        )
        self._cmp_overlap_lbl.grid(row=1, column=0, columnspan=12,
                                    padx=5, pady=(0, 5), sticky="w")

        # Scrollable area for result panes
        self._cmp_outer = ctk.CTkScrollableFrame(tab, width=1080, height=600)
        self._cmp_outer.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        self._cmp_panes: dict[str, ctk.CTkTextbox] = {}

    def _cmp_open(self) -> None:
        path = filedialog.askopenfilename(
            title="Select a PDF or image",
            filetypes=[("Documents", [f"*{e}" for e in ALL_EXTENSIONS]), ("All", "*.*")],
        )
        if path:
            self._cmp_file_lbl.configure(text=Path(path).name)
            self._cmp_current_file = path

    # Guard for first-call
    _cmp_current_file: str = ""

    def _cmp_run(self) -> None:
        if not self._cmp_current_file:
            messagebox.showwarning("No file", "Open a file first.")
            return
        names = [n for n, v in self._cmp_reader_vars.items() if v.get()]
        if not names:
            messagebox.showwarning("No readers", "Select at least one reader.")
            return

        # Clear old panes
        for pane in self._cmp_panes.values():
            pane.destroy()
        self._cmp_panes.clear()

        self._cmp_btn.configure(state="disabled")
        self._cmp_overlap_lbl.configure(text="")
        self._cmp_status_lbl.configure(text=f"Running {len(names)} readers...")
        threading.Thread(
            target=self._cmp_worker, args=(names,), daemon=True
        ).start()

    def _cmp_worker(self, names: list[str]) -> None:
        results: dict[str, ReaderResult] = {}
        for name in names:
            try:
                reader = create_reader(name)
                t0 = time.perf_counter()
                with ThreadPoolExecutor(max_workers=1) as ex:
                    fut = ex.submit(reader.read, self._cmp_current_file)
                    text = fut.result(timeout=READER_TIMEOUT)
                results[name] = ReaderResult(
                    name=name, text=text, elapsed=time.perf_counter() - t0
                )
            except TimeoutError:
                results[name] = ReaderResult(
                    name=name, text="", elapsed=READER_TIMEOUT, error="TIMEOUT"
                )
            except Exception as e:
                results[name] = ReaderResult(
                    name=name, text="", elapsed=0, error=f"{type(e).__name__}: {e}"
                )
        self.after(0, self._cmp_done, results)

    def _cmp_done(self, results: dict[str, ReaderResult]) -> None:
        self._cmp_btn.configure(state="normal")
        idx = 0
        cols = 2
        for name, r in results.items():
            col = idx % cols
            row = idx // cols
            frame = ctk.CTkFrame(self._cmp_outer)
            frame.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
            frame.grid_rowconfigure(1, weight=1)
            frame.grid_columnconfigure(0, weight=1)

            info = ctk.CTkLabel(
                frame,
                text=f"{name}  |  {r.elapsed:.2f}s  |  {len(r.text):,} chars",
                font=("Segoe UI", 10, "bold"),
            )
            info.grid(row=0, column=0, sticky="w", padx=4, pady=2)

            txt = ctk.CTkTextbox(frame, wrap="word", height=200)
            txt.grid(row=1, column=0, sticky="nsew", padx=4, pady=2)
            txt.insert("0.0", r.text if not r.error else f"ERROR: {r.error}")
            self._cmp_panes[name] = txt
            idx += 1

        ok = [r for r in results.values() if not r.error]
        self._cmp_status_lbl.configure(
            text=f"Done. {len(ok)}/{len(results)} succeeded."
        )

        # Word overlap stats (baseline = largest unique word set)
        texts = {r.name: r.text for r in results.values() if not r.error}
        if len(texts) >= 2:
            stats = word_stats(texts)
            baseline = max(texts, key=lambda n: len(set(texts[n].lower().split())))
            parts = [f"Baseline: {baseline}"]
            for name, s in stats.items():
                pct = s["common"] / s["total_base"] * 100 if s["total_base"] else 0
                parts.append(f"{name}={pct:.0f}% overlap")
            self._cmp_overlap_lbl.configure(text="  |  ".join(parts))
        else:
            self._cmp_overlap_lbl.configure(text="")

    # ──────────────────────────────────────────────────────────────────
    # Tab 3: BATCH — extract an entire folder with one reader, save all
    # ──────────────────────────────────────────────────────────────────

    def _build_batch(self) -> None:
        tab = self._tab_batch
        tab.grid_rowconfigure(0, weight=0)
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        ctrl = ctk.CTkFrame(tab)
        ctrl.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        ctk.CTkButton(ctrl, text="Select Folder", width=100,
                       command=self._batch_select).grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )

        self._batch_dir_lbl = ctk.CTkLabel(
            ctrl, text="(no folder)", font=("Segoe UI", 11)
        )
        self._batch_dir_lbl.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        self._batch_count_lbl = ctk.CTkLabel(
            ctrl, text="", font=("Segoe UI", 10)
        )
        self._batch_count_lbl.grid(row=0, column=2, padx=5, pady=5, sticky="w")

        readers = list(discover_readers())
        self._batch_reader_var = ctk.StringVar(
            value=readers[0] if readers else ""
        )
        self._batch_reader_menu = ctk.CTkOptionMenu(
            ctrl, values=readers, variable=self._batch_reader_var, width=130,
        )
        self._batch_reader_menu.grid(row=0, column=3, padx=5, pady=5)

        self._batch_btn = ctk.CTkButton(
            ctrl, text="Extract All", width=100, command=self._batch_run
        )
        self._batch_btn.grid(row=0, column=4, padx=5, pady=5)

        self._batch_save_btn = ctk.CTkButton(
            ctrl, text="Save All .txt", width=110, state="disabled",
            command=self._batch_save,
        )
        self._batch_save_btn.grid(row=0, column=5, padx=5, pady=5)

        self._batch_status_lbl = ctk.CTkLabel(
            ctrl, text="", font=("Segoe UI", 10)
        )
        self._batch_status_lbl.grid(row=0, column=6, padx=5, pady=5, sticky="e")

        # Results table
        inner = ctk.CTkFrame(tab)
        inner.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        inner.grid_rowconfigure(0, weight=1)
        inner.grid_columnconfigure(0, weight=1)

        cols = ("file", "time", "chars", "status")
        self._batch_tree = ttk.Treeview(inner, columns=cols, show="headings")
        style = ttk.Style()
        style.configure("Treeview", font=("Consolas", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        headings = [("file", "File", 300, "w"), ("time", "Time", 80, "e"),
                     ("chars", "Chars", 90, "e"), ("status", "Status", 80, "center")]
        for cid, label, w, a in headings:
            self._batch_tree.heading(cid, text=label)
            self._batch_tree.column(cid, width=w, anchor=a)  # type: ignore[call-overload]

        sb = ctk.CTkScrollbar(inner, command=self._batch_tree.yview)
        self._batch_tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")
        self._batch_tree.grid(row=0, column=0, sticky="nsew")

        self._batch_dir: str = ""
        self._batch_texts: dict[str, str] = {}

    def _batch_select(self) -> None:
        folder = filedialog.askdirectory(title="Select folder with PDFs/images")
        if not folder:
            return
        self._batch_dir = folder
        self._batch_dir_lbl.configure(text=folder)
        docs = find_documents(folder)
        self._batch_count_lbl.configure(text=f"{len(docs)} files found")
        # Clear old table
        for item in self._batch_tree.get_children():
            self._batch_tree.delete(item)
        self._batch_texts.clear()
        self._batch_save_btn.configure(state="disabled")
        self._batch_status_lbl.configure(text="")

    def _batch_run(self) -> None:
        if not self._batch_dir:
            messagebox.showwarning("No folder", "Select a folder first.")
            return
        name = self._batch_reader_var.get()
        docs = find_documents(self._batch_dir)
        if not docs:
            messagebox.showwarning("No files", "No supported documents found.")
            return
        self._batch_btn.configure(state="disabled")
        threading.Thread(
            target=self._batch_worker, args=(name, docs), daemon=True
        ).start()

    def _batch_worker(self, name: str, docs: list[Path]) -> None:
        try:
            reader = create_reader(name)
        except Exception as e:
            self.after(0, self._batch_error, str(e))
            return

        results: list[tuple[str, float, int, str]] = []
        texts: dict[str, str] = {}
        for i, doc in enumerate(docs):
            try:
                t0 = time.perf_counter()
                text = reader.read(doc)
                elapsed = time.perf_counter() - t0
                texts[doc.name] = text
                results.append((doc.name, elapsed, len(text), "ok"))
            except Exception as e:
                results.append((doc.name, 0.0, 0, f"ERR: {type(e).__name__}"))
            self.after(0, self._batch_update_row,
                       doc.name, results[-1][1], results[-1][2],
                       results[-1][3], i + 1, len(docs))

        self.after(0, self._batch_done, texts, results)

    def _batch_update_row(self, name: str, elapsed: float,
                          chars: int, status: str, done: int, total: int) -> None:
        self._batch_tree.insert("", "end",
                                values=(name, f"{elapsed:.2f}s",
                                        f"{chars:,}", status))
        self._batch_status_lbl.configure(text=f"{done}/{total}")

    def _batch_done(self, texts: dict[str, str],
                    results: list[tuple[str, float, int, str]]) -> None:
        self._batch_btn.configure(state="normal")
        self._batch_texts = texts
        ok = sum(1 for r in results if r[3] == "ok")
        self._batch_status_lbl.configure(
            text=f"Done. {ok}/{len(results)} succeeded."
        )
        if ok:
            self._batch_save_btn.configure(state="normal")

    def _batch_error(self, msg: str) -> None:
        self._batch_btn.configure(state="normal")
        self._batch_status_lbl.configure(text=f"Error: {msg}")

    def _batch_save(self) -> None:
        if not self._batch_texts:
            return
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
        messagebox.showinfo("Batch save", f"Saved {saved} text files to {out_path}")

    # ──────────────────────────────────────────────────────────────────
    # Tab 4: BENCHMARK — full benchmark with table + export
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
        panel = ctk.CTkFrame(tab, width=250)
        panel.grid(row=0, column=0, sticky="ns", padx=10, pady=10)
        panel.grid_propagate(False)

        ctk.CTkLabel(panel, text="Readers", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=10, pady=(10, 0)
        )

        avail = discover_readers()
        self._bm_reader_vars: dict[str, tk.BooleanVar] = {}
        all_on = tk.BooleanVar(value=True)

        bar = ctk.CTkFrame(panel)
        bar.pack(fill="x", padx=10, pady=(4, 0))

        ctk.CTkCheckBox(
            bar, text="All", variable=all_on,
            command=lambda: self._bm_toggle_all(all_on.get()),
        ).pack(side="left", padx=(4, 0))

        ctk.CTkCheckBox(
            bar, text="None", variable=tk.BooleanVar(),
            command=lambda: self._bm_toggle_all(False),
        ).pack(side="left", padx=(16, 0))

        reader_frame = ctk.CTkScrollableFrame(panel, width=230, height=120)
        reader_frame.pack(fill="x", padx=10, pady=(2, 0))

        for name in avail:
            var = tk.BooleanVar(value=True)
            self._bm_reader_vars[name] = var
            ctk.CTkCheckBox(reader_frame, text=name, variable=var).pack(
                anchor="w", padx=6, pady=1
            )

        ctk.CTkLabel(panel, text="Files", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=10, pady=(10, 0)
        )

        file_btns = ctk.CTkFrame(panel)
        file_btns.pack(fill="x", padx=10, pady=(4, 0))

        ctk.CTkButton(file_btns, text="Add Files", width=90, height=26,
                       command=self._bm_add_files).pack(side="left", padx=(0, 4))
        ctk.CTkButton(file_btns, text="Add Folder", width=90, height=26,
                       command=self._bm_add_folder).pack(side="left")

        self._bm_file_vars: dict[str, tk.BooleanVar] = {}
        self._bm_file_frame = ctk.CTkScrollableFrame(panel, width=230, height=180)
        self._bm_file_frame.pack(fill="both", expand=True, padx=10, pady=(2, 0))

        self._bm_run_btn = ctk.CTkButton(
            panel, text="Run Benchmark", fg_color="#3a7bfd", command=self._bm_run
        )
        self._bm_run_btn.pack(padx=10, pady=(8, 4))

        self._bm_progress = ctk.CTkProgressBar(panel, width=230)
        self._bm_progress.pack(padx=10, pady=(0, 4))
        self._bm_progress.set(0)

        self._bm_status_lbl = ctk.CTkLabel(panel, text="", font=("Segoe UI", 10))
        self._bm_status_lbl.pack(padx=10, pady=(0, 10))

        # Export buttons
        export_frame = ctk.CTkFrame(panel)
        export_frame.pack(fill="x", padx=10, pady=(0, 6))

        self._bm_export_json_btn = ctk.CTkButton(
            export_frame, text="Export JSON", width=95, height=24,
            state="disabled", command=self._bm_export_json,
        )
        self._bm_export_json_btn.pack(side="left", padx=(0, 4))

        self._bm_export_md_btn = ctk.CTkButton(
            export_frame, text="Export Markdown", width=95, height=24,
            state="disabled", command=self._bm_export_md,
        )
        self._bm_export_md_btn.pack(side="left")

    def _bm_build_right(self, tab: ctk.CTkTabview) -> None:
        table_frame = ctk.CTkFrame(tab)
        table_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        tab.grid_rowconfigure(0, weight=1)
        table_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(table_frame, text="Results",
                      font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(8, 0)
        )

        inner = ctk.CTkFrame(table_frame)
        inner.grid(row=1, column=0, sticky="nsew", padx=10, pady=(2, 8))
        inner.grid_rowconfigure(0, weight=1)
        inner.grid_columnconfigure(0, weight=1)

        cols = ("file", "method", "time", "chars", "status")
        self._bm_tree = ttk.Treeview(inner, columns=cols, show="headings",
                                      selectmode="none")

        style = ttk.Style()
        style.configure("Treeview", font=("Consolas", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

        headings = [("file", "File", 200, "w"), ("method", "Method", 120, "w"),
                     ("time", "Time", 80, "e"), ("chars", "Chars", 90, "e"),
                     ("status", "Status", 80, "center")]
        for cid, label, w, a in headings:
            self._bm_tree.heading(cid, text=label)
            self._bm_tree.column(cid, width=w, anchor=a)  # type: ignore[call-overload]

        sb = ctk.CTkScrollbar(inner, command=self._bm_tree.yview)
        self._bm_tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")
        self._bm_tree.grid(row=0, column=0, sticky="nsew")

        self._bm_summary_lbl = ctk.CTkLabel(table_frame, text="",
                                             font=("Segoe UI", 11))
        self._bm_summary_lbl.grid(row=2, column=0, sticky="s",
                                   padx=10, pady=(0, 8))

        # Internal state for export
        self._bm_readers_used: list[str] = []
        self._bm_files_used: list[str] = []
        self._bm_raw_results: list[dict[str, Any]] = []
        self._bm_cancelled = False

    # ── Benchmark helpers ────────────────────────────────────────────

    def _bm_toggle_all(self, state: bool) -> None:
        for var in self._bm_reader_vars.values():
            var.set(state)

    def _bm_add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select PDFs or images",
            filetypes=[("Documents", [f"*{e}" for e in ALL_EXTENSIONS]),
                       ("All files", "*.*")],
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
        ctk.CTkCheckBox(self._bm_file_frame, text=name, variable=var).pack(
            anchor="w", padx=6, pady=1
        )

    def _bm_run(self) -> None:
        readers = [n for n, v in self._bm_reader_vars.items() if v.get()]
        files = [p for p, v in self._bm_file_vars.items() if v.get()]
        if not readers:
            self._bm_status_lbl.configure(text="Select at least one reader.")
            return
        if not files:
            self._bm_status_lbl.configure(text="Add at least one file.")
            return

        self._bm_cancelled = False
        self._bm_run_btn.configure(text="Cancel", fg_color="#e74c3c",
                                    command=self._bm_cancel)
        self._bm_results.clear()
        self._bm_raw_results.clear()
        for item in self._bm_tree.get_children():
            self._bm_tree.delete(item)
        self._bm_summary_lbl.configure(text="")
        self._bm_export_json_btn.configure(state="disabled")
        self._bm_export_md_btn.configure(state="disabled")

        threading.Thread(
            target=self._bm_worker, args=(readers, files), daemon=True
        ).start()

    def _bm_cancel(self) -> None:
        self._bm_cancelled = True
        self._bm_status_lbl.configure(text="Cancelling...")

    def _bm_worker(self, readers: list[str], files: list[str]) -> None:
        total = len(readers) * len(files)
        done = 0

        # Pre-warm Docling
        for name in readers:
            if name in ("docling", "hybrid"):
                try:
                    create_reader(name)
                except Exception:
                    pass

        # Collect structured results for export
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
                self.after(0, self._bm_update_progress, done + 1, total,
                           f"{fname} ({name})")
                try:
                    reader = create_reader(name)
                    t0 = time.perf_counter()
                    with ThreadPoolExecutor(max_workers=1) as ex:
                        fut = ex.submit(reader.read, fpath)
                        text = fut.result(timeout=READER_TIMEOUT)
                    elapsed = time.perf_counter() - t0
                    chars = len(text)
                    status = "ok"
                    totals[name] += elapsed
                    file_results["readers"][name] = {
                        "time_s": round(elapsed, 3), "chars": chars,
                        "words": len(set(text.lower().split())),
                    }
                except TimeoutError:
                    elapsed = float(READER_TIMEOUT)
                    chars = 0
                    status = "TIMEOUT"
                    file_results["readers"][name] = {"error": True}
                except Exception as e:
                    elapsed = 0.0
                    chars = 0
                    status = f"ERR: {type(e).__name__}"
                    file_results["readers"][name] = {"error": True}

                self.after(0, self._bm_append_row, fname, name,
                           f"{elapsed:.2f}s", f"{chars:,}", status)
                done += 1
            all_results.append(file_results)

        self.after(0, self._bm_done, readers, files, all_results, totals)

    def _bm_append_row(self, file: str, method: str, time_s: str,
                       chars: str, status: str) -> None:
        self._bm_tree.insert("", "end", values=(file, method, time_s, chars, status))
        r: dict[str, Any] = {
            "file": file, "method": method,
            "time": time_s, "chars": chars, "status": status,
        }
        self._bm_results.append(r)
        self._bm_raw_results.append(r)

    def _bm_update_progress(self, done: int, total: int, current: str) -> None:
        self._bm_progress.set(min(done / total, 1.0))
        self._bm_status_lbl.configure(text=f"{done}/{total} — {current}")

    def _bm_done(self, readers: list[str], files: list[str],
                 all_results: list[dict[str, Any]],
                 totals: dict[str, float]) -> None:
        self._bm_run_btn.configure(text="Run Benchmark", fg_color="#3a7bfd",
                                    command=self._bm_run)
        self._bm_progress.set(1)
        self._bm_readers_used = readers
        self._bm_files_used = files

        if self._bm_cancelled:
            self._bm_status_lbl.configure(text="Cancelled.")
            return

        self._bm_status_lbl.configure(text="Done.")
        ok = [r for r in self._bm_results
              if not str(r.get("status", "")).startswith("ERR")]
        if ok:
            self._bm_summary_lbl.configure(
                text=f"Files: {len(files)}  |  Readers: {len(readers)}  "
                     f"|  Results: {len(ok)}/{len(self._bm_results)}"
            )

        # Enable export
        self._bm_export_json_btn.configure(state="normal")
        self._bm_export_md_btn.configure(state="normal")

        # Store for export
        self._bm_export_data = {
            "all_results": all_results,
            "all_names": readers,
            "totals": totals,
        }

    def _bm_export_json(self) -> None:
        path = Path("results") / f"benchmark_export_{int(time.time())}.json"
        path.parent.mkdir(exist_ok=True)
        data: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "hardware": detect_hardware(),
            "results": self._bm_raw_results,
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        messagebox.showinfo("Export", f"JSON saved to {path}")

    def _bm_export_md(self) -> None:
        d = self._bm_export_data
        directory = (str(Path(self._bm_files_used[0]).parent)
                     if self._bm_files_used else ".")
        out = generate_markdown_report(
            d["all_results"],
            d["all_names"],
            d["totals"],
            detect_hardware(),
            directory,
        )
        messagebox.showinfo("Export", f"Markdown report saved to {out}")


# ── Entrypoint ───────────────────────────────────────────────────────


def main() -> None:
    """Launch the GUI."""
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
