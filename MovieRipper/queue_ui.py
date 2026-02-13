from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

@dataclass
class QueueItem:
    clz_index: int
    title: str
    year: int | None
    imdb_id: str

class QueueBuilderApp(tk.Tk):
    def __init__(self, index: dict, default_save_path: Optional[Path] = None):
        super().__init__()
        self.title("MovieRipper — Build Queue (IMDb required)")
        self.geometry("1200x700")

        self.index = index
        self.default_save_path = default_save_path

        self.selected_movie: Optional[dict] = None
        self.queue: list[QueueItem] = []

        self._build_ui()

    def _build_ui(self):
        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)

        panes = ttk.Panedwindow(root, orient=tk.HORIZONTAL)
        panes.pack(fill="both", expand=True)

        left = ttk.Frame(panes, padding=5)
        right = ttk.Frame(panes, padding=5)
        panes.add(left, weight=3)
        panes.add(right, weight=2)

        # LEFT: search + results
        ttk.Label(left, text="Search master list (only rows with IMDb ID show)").pack(anchor="w")

        self.search_var = tk.StringVar()
        entry = ttk.Entry(left, textvariable=self.search_var)
        entry.pack(fill="x")
        entry.bind("<KeyRelease>", lambda e: self._refresh_results())

        cols = ("idx","title","year","imdb")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", height=22)
        self.tree.heading("idx", text="CLZ Index")
        self.tree.heading("title", text="Title")
        self.tree.heading("year", text="Year")
        self.tree.heading("imdb", text="IMDb")
        self.tree.column("idx", width=90, anchor="center")
        self.tree.column("title", width=640)
        self.tree.column("year", width=70, anchor="center")
        self.tree.column("imdb", width=130, anchor="center")
        self.tree.pack(fill="both", expand=True, pady=(6,0))
        self.tree.bind("<<TreeviewSelect>>", self._on_movie_select)

        left_btns = ttk.Frame(left)
        left_btns.pack(fill="x", pady=10)
        ttk.Button(left_btns, text="Add to queue →", command=self._add_to_queue).pack(side="left")
        ttk.Button(left_btns, text="Add & Next", command=self._add_and_next).pack(side="left", padx=(8,0))

        # RIGHT: queue
        ttk.Label(right, text="Queue (top = next disc you’ll insert)").pack(anchor="w")
        self.queue_list = tk.Listbox(right, height=26)
        self.queue_list.pack(fill="both", expand=True)

        qbtns = ttk.Frame(right)
        qbtns.pack(fill="x", pady=10)

        ttk.Button(qbtns, text="Move Up", command=lambda: self._move(-1)).pack(side="left")
        ttk.Button(qbtns, text="Move Down", command=lambda: self._move(1)).pack(side="left", padx=(8,0))
        ttk.Button(qbtns, text="Remove", command=self._remove).pack(side="left", padx=(8,0))

        ttk.Button(qbtns, text="Save Queue…", command=self._save).pack(side="right")
        ttk.Button(qbtns, text="Close", command=self.destroy).pack(side="right", padx=(8,0))

        self._refresh_results()

    def _eligible_records(self):
        # Only show movies with imdb_id + clz_index
        for rec in self.index.get("search", []):
            if not rec.get("imdb_id"):
                continue
            if rec.get("clz_index") is None or str(rec.get("clz_index")).strip() == "":
                continue
            yield rec

    def _refresh_results(self):
        q = (self.search_var.get() or "").strip().lower()
        tokens = [t for t in q.split() if t]

        for i in self.tree.get_children():
            self.tree.delete(i)

        results = []
        for rec in self._eligible_records():
            key = (rec.get("search_key") or "")
            if all(t in key for t in tokens):
                results.append(rec)
            if len(results) >= 300:
                break

        for rec in results[:300]:
            self.tree.insert("", tk.END, values=(
                rec.get("clz_index"),
                rec.get("title"),
                rec.get("year") or "",
                rec.get("imdb_id") or ""
            ))

    def _on_movie_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            self.selected_movie = None
            return
        vals = self.tree.item(sel[0], "values")
        self.selected_movie = {
            "clz_index": int(vals[0]),
            "title": vals[1],
            "year": int(vals[2]) if str(vals[2]).isdigit() else None,
            "imdb_id": vals[3]
        }

    def _add_to_queue(self):
        if not self.selected_movie:
            messagebox.showerror("MovieRipper", "Select a movie first.")
            return
        item = QueueItem(**self.selected_movie)
        # prevent dupes by clz_index
        if any(q.clz_index == item.clz_index for q in self.queue):
            messagebox.showinfo("MovieRipper", "That CLZ Index is already in the queue.")
            return
        self.queue.append(item)
        self.queue_list.insert(tk.END, self._label(item))

    def _add_and_next(self):
        self._add_to_queue()
        # move selection down one
        kids = self.tree.get_children()
        sel = self.tree.selection()
        if not sel:
            return
        idx = kids.index(sel[0])
        nxt = min(idx + 1, len(kids) - 1)
        self.tree.selection_set(kids[nxt])
        self.tree.see(kids[nxt])

    def _label(self, item: QueueItem) -> str:
        y = f" ({item.year})" if item.year else ""
        return f"{item.clz_index} — {item.title}{y} — {item.imdb_id}"

    def _move(self, delta: int):
        sel = self.queue_list.curselection()
        if not sel:
            return
        i = sel[0]
        j = i + delta
        if j < 0 or j >= len(self.queue):
            return
        self.queue[i], self.queue[j] = self.queue[j], self.queue[i]
        # redraw
        self.queue_list.delete(0, tk.END)
        for it in self.queue:
            self.queue_list.insert(tk.END, self._label(it))
        self.queue_list.selection_set(j)

    def _remove(self):
        sel = self.queue_list.curselection()
        if not sel:
            return
        i = sel[0]
        self.queue.pop(i)
        self.queue_list.delete(i)

    def _save(self):
        if not self.queue:
            messagebox.showerror("MovieRipper", "Queue is empty.")
            return
        initial = str(self.default_save_path) if self.default_save_path else "movie_queue.json"
        path = filedialog.asksaveasfilename(
            title="Save Queue JSON",
            initialfile=Path(initial).name,
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        data = {
            "built_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
            "items": [it.__dict__ for it in self.queue]
        }
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
        messagebox.showinfo("MovieRipper", f"Saved queue:\n{path}")
