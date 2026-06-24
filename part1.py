import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import requests
import threading
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


DB_FILE = "countries.db"
API_URL = "https://api.worldbank.org/v2/country?format=json&per_page=300"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS countries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            capital TEXT,
            region TEXT,
            population INTEGER
        )
    """)
    conn.commit()
    conn.close()


def clear_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM countries")
    conn.commit()
    conn.close()


def insert_countries(data):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    entries = data[1] if isinstance(data, list) and len(data) > 1 else []
    for item in entries:
        if not isinstance(item, dict):
            continue
        name = item.get("name", "N/A") or "N/A"
        capital = item.get("capitalCity", "N/A") or "N/A"
        region_field = item.get("region", {})
        region = region_field.get("value", "N/A") if isinstance(region_field, dict) else "N/A"
        if not region or region == "Aggregates":
            continue
        population = 0
        c.execute(
            "INSERT INTO countries (name, capital, region, population) VALUES (?, ?, ?, ?)",
            (name, capital, region, population)
        )
    conn.commit()
    conn.close()


def fetch_from_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT name, capital, region, population FROM countries ORDER BY name")
    rows = c.fetchall()
    conn.close()
    return rows


def get_avg_population():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM countries")
    result = c.fetchone()[0]
    conn.close()
    return result


def get_count():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM countries")
    result = c.fetchone()[0]
    conn.close()
    return result


def get_region_counts():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT region, COUNT(*) FROM countries GROUP BY region ORDER BY COUNT(*) DESC")
    rows = c.fetchall()
    conn.close()
    return rows


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Countries Explorer")
        self.geometry("950x650")
        self.configure(bg="#f0f4f8")
        init_db()
        self._build_menu()
        self._build_ui()

    def _build_menu(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        data_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Data", menu=data_menu)
        data_menu.add_command(label="Download data", command=self._download_thread)
        data_menu.add_command(label="Clear database", command=self._clear)
        data_menu.add_separator()
        data_menu.add_command(label="Quit", command=self.destroy)

        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Show chart", command=self._show_chart)
        view_menu.add_command(label="Show country count", command=self._show_count)

        options_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Options", menu=options_menu)
        options_menu.add_command(label="Light theme", command=lambda: self._set_theme("#f0f4f8"))
        options_menu.add_command(label="Dark theme", command=lambda: self._set_theme("#1e1e2e"))

    def _build_ui(self):
        top = tk.Frame(self, bg="#f0f4f8")
        top.pack(fill=tk.X, padx=12, pady=8)

        tk.Button(top, text="Download", command=self._download_thread,
                  bg="#4c8bf5", fg="white", relief="flat", padx=10, pady=4).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="Clear DB", command=self._clear,
                  bg="#e05252", fg="white", relief="flat", padx=10, pady=4).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="Show chart", command=self._show_chart,
                  bg="#27ae60", fg="white", relief="flat", padx=10, pady=4).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="Count by region", command=self._show_count,
                  bg="#8e44ad", fg="white", relief="flat", padx=10, pady=4).pack(side=tk.LEFT, padx=4)

        cols = ("Name", "Capital", "Region", "Population")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=20)
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=200 if col != "Population" else 100)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        self.chart_frame = tk.Frame(self, bg="#f0f4f8")
        self.chart_frame.pack(fill=tk.BOTH, padx=12, pady=4)

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self.status_var, anchor="w",
                 bg="#d0d8e4", relief="sunken").pack(fill=tk.X, side=tk.BOTTOM)

        self._refresh_table()

    def _set_theme(self, bg):
        self.configure(bg=bg)
        self.status_var.set("Theme applied.")

    def _refresh_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for row in fetch_from_db():
            self.tree.insert("", tk.END, values=row)

    def _clear(self):
        clear_db()
        self._refresh_table()
        self.status_var.set("Database cleared.")

    def _download_thread(self):
        if get_count() > 0:
            if not messagebox.askyesno("Warning", "Database is not empty. Overwrite?"):
                return
            clear_db()
        self.status_var.set("Downloading...")
        threading.Thread(target=self._download, daemon=True).start()

    def _download(self):
        try:
            response = requests.get(API_URL, timeout=15)
            response.raise_for_status()
            data = response.json()
            insert_countries(data)
            count = get_count()
            self.after(0, self._refresh_table)
            self.after(0, lambda: self.status_var.set(f"Downloaded {count} countries."))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
            self.after(0, lambda: self.status_var.set("Download failed."))

    def _show_count(self):
        rows = get_region_counts()
        if not rows:
            messagebox.showwarning("No data", "Download data first.")
            return
        text = "\n".join(f"{r}: {n} countries" for r, n in rows)
        total = sum(n for _, n in rows)
        messagebox.showinfo("Countries by region", f"Total: {total}\n\n{text}")
        self.status_var.set(f"Total: {total} countries in DB.")

    def _show_chart(self):
        rows = get_region_counts()
        if not rows:
            messagebox.showwarning("No data", "Download data first.")
            return

        for widget in self.chart_frame.winfo_children():
            widget.destroy()

        regions = [r[0] for r in rows]
        counts = [r[1] for r in rows]

        fig, ax = plt.subplots(figsize=(9, 3))
        ax.bar(regions, counts, color="#4c8bf5")
        ax.set_xlabel("Region")
        ax.set_ylabel("Number of countries")
        ax.set_title("Countries per region (World Bank)")
        plt.xticks(rotation=20, ha="right", fontsize=8)
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        plt.close(fig)
        self.status_var.set("Chart displayed.")


if __name__ == "__main__":
    app = App()
    app.mainloop()