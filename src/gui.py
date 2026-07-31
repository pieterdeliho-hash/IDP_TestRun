"""Simple GUI for running the PDF reader benchmark."""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import tkinter as tk  # noqa: PLC0415
import tkinter.ttk as ttk  # noqa: PLC0415
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from src.benchmark import create_reader, discover_readers
from src.utils import ALL_EXTENSIONS

# Suppress noisy RapidOCR / Docling logs during GUI runs
logging.getLogger("RapidOCR").setLevel(logging.ERROR)
logging.getLogger("docling.models.stages.ocr.rapid_ocr_model").setLevel(logging.ERROR)

# Per-reader timeout (seconds) — Docling first-run model loading can be slow
READER_TIMEOUT = 180


class App(ctk.CTk):
    """Benchmark GUI — pick readers, pick files, hit Run."""

    def __init__(self) -> None:
        super().__init__()
        self.title("PDF Reader Benchmark")
        self.geometry("960x680")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # ── State ────────────────────────────────────────────────────
        self.results: list[dict[str, object]] = []
        self._cancelled = False

        # ── Layout ───────────────────────────────────────────────────
        self.grid_columnconfigure(0, weight=0)  # left panel
        self.grid_columnconfigure(1, weight=1)  # right panel

        self._build_left()
        self._build_right()

    # ── Left panel: readers + files ─────────────────────────────────

    def _build_left(self) -> None:
        panel = ctk.CTkFrame(self, width=260)
        panel.grid(row=0, column=0, sticky="ns", padx=10, pady=10)
        panel.grid_propagate(False)

        # ── Readers ──────────────────────────────────────────────────
        ctk.CTkLabel(panel, text="Readers", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=10, pady=(10, 0)
        )

        avail = discover_readers()
        self.reader_vars: dict[str, tk.BooleanVar] = {}
        all_on = tk.BooleanVar(value=True)

        bar = ctk.CTkFrame(panel)
        bar.pack(fill="x", padx=10, pady=(4, 0))

        ctk.CTkCheckBox(
            bar,
            text="All",
            variable=all_on,
            command=lambda: self._toggle_all_readers(all_on.get()),
        ).pack(side="left", padx=(4, 0))

        ctk.CTkCheckBox(
            bar,
            text="None",
            variable=tk.BooleanVar(),
            command=lambda: self._toggle_all_readers(False),
        ).pack(side="left", padx=(16, 0))

        reader_frame = ctk.CTkScrollableFrame(panel, width=240, height=130)
        reader_frame.pack(fill="x", padx=10, pady=(2, 0))

        for name in avail:
            var = tk.BooleanVar(value=True)
            self.reader_vars[name] = var
            ctk.CTkCheckBox(reader_frame, text=name, variable=var).pack(
                anchor="w", padx=6, pady=1
            )

        # ── Files ────────────────────────────────────────────────────
        ctk.CTkLabel(panel, text="Files", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=10, pady=(10, 0)
        )

        file_btns = ctk.CTkFrame(panel)
        file_btns.pack(fill="x", padx=10, pady=(4, 0))

        ctk.CTkButton(
            file_btns,
            text="Add Files",
            width=95,
            height=26,
            command=self._add_files,
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            file_btns,
            text="Add Folder",
            width=95,
            height=26,
            command=self._add_folder,
        ).pack(side="left")

        self.file_vars: dict[str, tk.BooleanVar] = {}

        self.file_frame = ctk.CTkScrollableFrame(panel, width=240, height=200)
        self.file_frame.pack(fill="both", expand=True, padx=10, pady=(2, 0))

        # ── Run / Cancel button ──────────────────────────────────────
        self.run_btn = ctk.CTkButton(
            panel, text="Run Benchmark", fg_color="#3a7bfd", command=self._run
        )
        self.run_btn.pack(padx=10, pady=(8, 4))

        self.progress = ctk.CTkProgressBar(panel, width=240)
        self.progress.pack(padx=10, pady=(0, 4))
        self.progress.set(0)

        self.status_lbl = ctk.CTkLabel(panel, text="", font=("Segoe UI", 10))
        self.status_lbl.pack(padx=10, pady=(0, 10))

    # ── Right panel: results table ──────────────────────────────────

    def _build_right(self) -> None:
        table_frame = ctk.CTkFrame(self)
        table_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.grid_rowconfigure(0, weight=1)
        table_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            table_frame, text="Results", font=("Segoe UI", 14, "bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 0))

        inner = ctk.CTkFrame(table_frame)
        inner.grid(row=1, column=0, sticky="nsew", padx=10, pady=(2, 8))
        inner.grid_rowconfigure(0, weight=1)
        inner.grid_columnconfigure(0, weight=1)

        # Treeview as table
        cols = ("file", "method", "time", "chars", "status")
        self.tree = ttk.Treeview(
            inner,
            columns=cols,
            show="headings",
            selectmode="none",
        )

        style = ttk.Style()
        style.configure("Treeview", font=("Consolas", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

        self.tree.heading("file", text="File")
        self.tree.heading("method", text="Method")
        self.tree.heading("time", text="Time")
        self.tree.heading("chars", text="Chars")
        self.tree.heading("status", text="Status")

        self.tree.column("file", width=200, minwidth=120)
        self.tree.column("method", width=120, minwidth=80)
        self.tree.column("time", width=80, minwidth=50, anchor="e")
        self.tree.column("chars", width=90, minwidth=60, anchor="e")
        self.tree.column("status", width=70, minwidth=50, anchor="center")

        sb = ctk.CTkScrollbar(inner, command=self.tree.yview)
        self.tree.configure(yscroll=sb.set)  # type: ignore[call-overload]

        sb.grid(row=0, column=1, sticky="ns")
        self.tree.grid(row=0, column=0, sticky="nsew")

        # Summary label
        self.summary_lbl = ctk.CTkLabel(table_frame, text="", font=("Segoe UI", 11))
        self.summary_lbl.grid(row=2, column=0, sticky="s", padx=10, pady=(0, 8))

    # ── Reader toggles ──────────────────────────────────────────────

    def _toggle_all_readers(self, state: bool) -> None:
        for var in self.reader_vars.values():
            var.set(state)

    # ── File selection ──────────────────────────────────────────────

    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select PDFs or images",
            filetypes=[
                ("Documents", [f"*{e}" for e in ALL_EXTENSIONS]),
                ("All files", "*.*"),
            ],
        )
        for p in paths:
            self._add_file(p)

    def _add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select folder")
        if not folder:
            return
        for ext in ALL_EXTENSIONS:
            for p in Path(folder).glob(f"**/*{ext}"):
                self._add_file(str(p))

    def _add_file(self, path: str) -> None:
        if path in self.file_vars:
            return
        name = Path(path).name
        var = tk.BooleanVar(value=True)
        self.file_vars[path] = var
        ctk.CTkCheckBox(self.file_frame, text=name, variable=var).pack(
            anchor="w", padx=6, pady=1
        )

    # ── Run benchmark ───────────────────────────────────────────────

    def _run(self) -> None:
        readers = [n for n, v in self.reader_vars.items() if v.get()]
        files = [p for p, v in self.file_vars.items() if v.get()]

        if not readers:
            self.status_lbl.configure(text="Select at least one reader.")
            return
        if not files:
            self.status_lbl.configure(text="Add at least one file.")
            return

        self._cancelled = False
        self.run_btn.configure(text="Cancel", fg_color="#e74c3c", command=self._cancel)
        self.results.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.summary_lbl.configure(text="")

        threading.Thread(target=self._worker, args=(readers, files), daemon=True).start()

    def _cancel(self) -> None:
        self._cancelled = True
        self.status_lbl.configure(text="Cancelling...")

    def _worker(
        self, readers: list[str], files: list[str], tesseract_cmd: str | None = None
    ) -> None:
        total = len(readers) * len(files)
        done = 0

        # Pre-warm: load Docling models on first docling call so the
        # "Loading weights" bar doesn't block the UI thread.
        for name in readers:
            if name in ("docling", "hybrid"):
                try:
                    create_reader(name, tesseract_cmd=tesseract_cmd)
                except Exception:
                    pass

        for fpath in files:
            if self._cancelled:
                break

            fname = Path(fpath).name
            for name in readers:
                if self._cancelled:
                    break  # type: ignore[unreachable]

                self.after(
                    0, self._update_progress, done + 1, total, f"{fname} ({name})"
                )

                try:
                    reader = create_reader(name, tesseract_cmd=tesseract_cmd)
                    start = time.perf_counter()
                    with ThreadPoolExecutor(max_workers=1) as ex:
                        future = ex.submit(reader.read, fpath)
                        text = future.result(timeout=READER_TIMEOUT)
                    elapsed = time.perf_counter() - start
                    chars = len(text)
                    status = "ok"
                except TimeoutError:
                    elapsed = float(READER_TIMEOUT)
                    chars = 0
                    status = "TIMEOUT"
                except Exception as e:
                    elapsed = 0.0
                    chars = 0
                    status = f"ERR: {type(e).__name__}"

                # Batch UI updates to avoid flooding the event queue
                self.after(
                    0,
                    self._append_row,
                    fname,
                    name,
                    f"{elapsed:.2f}s",
                    f"{chars:,}",
                    status,
                )
                done += 1

        self.after(0, self._done, readers, files)

    def _append_row(
        self, file: str, method: str, time_s: str, chars: str, status: str
    ) -> None:
        self.tree.insert("", "end", values=(file, method, time_s, chars, status))
        self.results.append(
            {"file": file, "method": method, "time": time_s, "chars": chars, "status": status}
        )

    def _update_progress(self, done: int, total: int, current: str) -> None:
        self.progress.set(min(done / total, 1.0))
        self.status_lbl.configure(text=f"{done}/{total} — {current}")

    def _done(self, readers: list[str], files: list[str]) -> None:
        self.run_btn.configure(text="Run Benchmark", fg_color="#3a7bfd", command=self._run)
        self.progress.set(1)

        if self._cancelled:
            self.status_lbl.configure(text="Cancelled.")
            return

        self.status_lbl.configure(text="Done.")

        # Summary
        ok = [r for r in self.results if not str(r.get("status", "")).startswith("ERR")]
        if ok:
            lines = [f"Files: {len(files)}  |  Readers: {len(readers)}  |  Results: {len(ok)}/{len(self.results)}"]
            self.summary_lbl.configure(text="  |  ".join(lines))


def main() -> None:
    """Launch the benchmark GUI."""
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
