
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable

import tkinter as tk
from tkinter import ttk, messagebox

from .pipeline import Job, write_job, JOB_FILENAME

@dataclass
class PickResult:
    folder: Path
    job: Job

class PickerApp(tk.Tk):
    def __init__(self, index: dict, pending_folders: list[Path]):
        super().__init__()
        self.title("DiscMapper — Pick Movie for Rip Folder")
        self.geometry("1000x600")

        self.index = index
        self.pending_folders = pending_folders

        self.selected_folder: Optional[Path] = None
        self.selected_movie: Optional[dict] = None

        self._build_ui()

    def _build_ui(self):
        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)

        panes = ttk.Panedwindow(root, orient=tk.HORIZONTAL)
        panes.pack(fill="both", expand=True)

        left = ttk.Frame(panes, padding=5)
        right = ttk.Frame(panes, padding=5)
        panes.add(left, weight=1)
        panes.add(right, weight=2)

        ttk.Label(left, text="Rip folders (choose one)").pack(anchor="w")
        self.folder_list = tk.Listbox(left, height=25)
        self.folder_list.pack(fill="both", expand=True)
        for p in self.pending_folders:
            self.folder_list.insert(tk.END, str(p))
        self.folder_list.bind("<<ListboxSelect>>", self._on_folder_select)

        self.folder_status = ttk.Label(left, text="")
        self.folder_status.pack(anchor="w", pady=(8,0))

        ttk.Label(right, text="Search CLZ movies").pack(anchor="w")
        self.search_var = tk.StringVar()
        entry = ttk.Entry(right, textvariable=self.search_var)
        entry.pack(fill="x")
        entry.bind("<KeyRelease>", lambda e: self._refresh_results())

        cols = ("title","year","imdb")
        self.tree = ttk.Treeview(right, columns=cols, show="headings", height=18)
        self.tree.heading("title", text="Title")
        self.tree.heading("year", text="Year")
        self.tree.heading("imdb", text="IMDb")
        self.tree.column("title", width=520)
        self.tree.column("year", width=70, anchor="center")
        self.tree.column("imdb", width=130, anchor="center")
        self.tree.pack(fill="both", expand=True, pady=(6,0))
        self.tree.bind("<<TreeviewSelect>>", self._on_movie_select)

        btns = ttk.Frame(right)
        btns.pack(fill="x", pady=10)

        self.assign_btn = ttk.Button(btns, text="Assign selected movie to folder", command=self._assign)
        self.assign_btn.pack(side="left")

        ttk.Button(btns, text="Close", command=self.destroy).pack(side="right")

        self._refresh_results()

    def _on_folder_select(self, event=None):
        sel = self.folder_list.curselection()
        self.selected_folder = Path(self.folder_list.get(sel[0])) if sel else None
        if self.selected_folder:
            job_path = self.selected_folder / JOB_FILENAME
            if job_path.exists():
                self.folder_status.config(text=f"Already assigned: {JOB_FILENAME} exists")
            else:
                self.folder_status.config(text="Not assigned yet")

    def _refresh_results(self):
        q = (self.search_var.get() or "").strip().lower()
        for i in self.tree.get_children():
            self.tree.delete(i)

        # Basic fuzzy-ish: all query tokens must appear in search_key
        tokens = [t for t in q.split() if t]
        results = []
        for rec in self.index.get("search", []):
            key = rec.get("search_key","")
            if all(t in key for t in tokens):
                results.append(rec)
            if len(results) >= 250:
                break

        for rec in results[:250]:
            self.tree.insert("", tk.END, values=(rec.get("title"), rec.get("year") or "", rec.get("imdb_id") or ""))

    def _on_movie_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            self.selected_movie = None
            return
        vals = self.tree.item(sel[0], "values")
        title, year, imdb_id = vals[0], vals[1], vals[2]
        self.selected_movie = {"title": title, "year": int(year) if str(year).isdigit() else None, "imdb_id": imdb_id or None}

    def _assign(self):
        if not self.selected_folder:
            messagebox.showerror("DiscMapper", "Select a rip folder on the left.")
            return
        if not self.selected_movie:
            messagebox.showerror("DiscMapper", "Select a movie on the right.")
            return
        job = Job(title=self.selected_movie["title"], year=self.selected_movie["year"], imdb_id=self.selected_movie["imdb_id"])
        write_job(self.selected_folder, job)
        messagebox.showinfo("DiscMapper", f"Assigned:\n{job.title} ({job.year or ''})\n→ {self.selected_folder}")
        self._on_folder_select()
