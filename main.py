import csv
import json
import random
import threading
import time
import urllib.request
import urllib.error
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime

APP_DIR = Path(__file__).resolve().parent
SETTINGS_FILE = APP_DIR / "settings.json"
HISTORY_FILE = APP_DIR / "history.json"
DEFAULT_CSV = APP_DIR / "samples.csv"
OLLAMA_URL = "http://localhost:11434/api/chat"

DEFAULT_SETTINGS = {
    "model": "llama3.1:8b",
    "min_minutes": 25,
    "max_minutes": 35,
    "topic": "Web3 and crypto community",
    "instruction": "Write a natural, human-sounding X post. Avoid exaggerated claims, spam, and repetitive wording. Keep it concise.",
    "language": "English",
    "min_chars": 220,
    "max_chars": 260,
    "auto_start": False
}

def read_json(path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback

def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def load_samples(path):
    samples = []
    if not path.exists():
        return samples
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Normalize headers so harmless spacing/case differences (for
            # example, `id, text`) don't make valid rows disappear.
            normalized = {
                (key or "").strip().lower(): value
                for key, value in row.items()
            }
            text = (normalized.get("text") or normalized.get("post") or normalized.get("sample") or "").strip()
            if text:
                samples.append(text)
    return samples

def ollama_chat(model, messages):
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.85}
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=180) as response:
        result = json.loads(response.read().decode("utf-8"))
    return result.get("message", {}).get("content", "").strip()

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Hasib X Post Assistant")
        self.root.geometry("790x760")
        self.root.minsize(700, 650)
        self.settings = read_json(SETTINGS_FILE, DEFAULT_SETTINGS.copy())
        self.history = read_json(HISTORY_FILE, [])
        self.samples_path = Path(self.settings.get("samples_path", str(DEFAULT_CSV)))
        self.running = False
        self.timer_id = None
        self.next_post_at = None
        self.busy = False
        self._build_ui()
        self._refresh_sample_count()
        self._set_status("Ready. Install/run Ollama and download a model to generate posts.")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Hasib X Post Assistant", font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Local AI drafts posts from your examples + instructions. You publish manually on X.",
                  wraplength=740).pack(anchor="w", pady=(2, 12))

        sample_frame = ttk.LabelFrame(outer, text="Sample posts (CSV)", padding=10)
        sample_frame.pack(fill="x", **pad)
        self.csv_var = tk.StringVar(value=str(self.samples_path))
        ttk.Entry(sample_frame, textvariable=self.csv_var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(sample_frame, text="Choose CSV…", command=self.choose_csv).pack(side="left")
        self.sample_count_label = ttk.Label(sample_frame, text="")
        self.sample_count_label.pack(side="left", padx=(10, 0))

        settings = ttk.LabelFrame(outer, text="Generation settings", padding=10)
        settings.pack(fill="x", **pad)
        settings.columnconfigure(1, weight=1)
        settings.columnconfigure(3, weight=1)

        ttk.Label(settings, text="Topic").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.topic_var = tk.StringVar(value=self.settings.get("topic", DEFAULT_SETTINGS["topic"]))
        ttk.Entry(settings, textvariable=self.topic_var).grid(row=0, column=1, columnspan=3, sticky="ew", padx=4, pady=4)

        ttk.Label(settings, text="Instructions").grid(row=1, column=0, sticky="nw", padx=4, pady=4)
        self.instruction_text = tk.Text(settings, height=3, wrap="word")
        self.instruction_text.grid(row=1, column=1, columnspan=3, sticky="ew", padx=4, pady=4)
        self.instruction_text.insert("1.0", self.settings.get("instruction", DEFAULT_SETTINGS["instruction"]))

        ttk.Label(settings, text="Language").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self.language_var = tk.StringVar(value=self.settings.get("language", "English"))
        ttk.Combobox(settings, textvariable=self.language_var, values=["English", "Bangla", "Banglish"], state="readonly", width=14).grid(row=2, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(settings, text="Ollama model").grid(row=2, column=2, sticky="e", padx=4, pady=4)
        self.model_var = tk.StringVar(value=self.settings.get("model", "llama3.2:3b"))
        ttk.Entry(settings, textvariable=self.model_var, width=18).grid(row=2, column=3, sticky="ew", padx=4, pady=4)

        ttk.Label(settings, text="Random interval (minutes)").grid(row=3, column=0, sticky="w", padx=4, pady=4)
        interval_frame = ttk.Frame(settings)
        interval_frame.grid(row=3, column=1, sticky="w", padx=4, pady=4)
        self.min_var = tk.StringVar(value=str(self.settings.get("min_minutes", 25)))
        self.max_var = tk.StringVar(value=str(self.settings.get("max_minutes", 35)))
        ttk.Entry(interval_frame, textvariable=self.min_var, width=5).pack(side="left")
        ttk.Label(interval_frame, text=" to ").pack(side="left")
        ttk.Entry(interval_frame, textvariable=self.max_var, width=5).pack(side="left")

        ttk.Label(settings, text="Min characters").grid(row=4, column=0, sticky="w", padx=4, pady=4)
        self.min_chars_var = tk.StringVar(value=str(self.settings.get("min_chars", 220)))
        ttk.Entry(settings, textvariable=self.min_chars_var, width=8).grid(row=4, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(settings, text="Max characters").grid(row=4, column=2, sticky="e", padx=4, pady=4)
        self.max_chars_var = tk.StringVar(value=str(self.settings.get("max_chars", 260)))
        ttk.Entry(settings, textvariable=self.max_chars_var, width=8).grid(row=4, column=3, sticky="w", padx=4, pady=4)

        actions = ttk.Frame(outer)
        actions.pack(fill="x", **pad)
        ttk.Button(actions, text="Generate now", command=self.generate_now).pack(side="left")
        self.start_button = ttk.Button(actions, text="Start reminders", command=self.start)
        self.start_button.pack(side="left", padx=8)
        self.stop_button = ttk.Button(actions, text="Stop reminders", command=self.stop, state="disabled")
        self.stop_button.pack(side="left")
        ttk.Button(actions, text="Save settings", command=self.save_settings).pack(side="right")

        post_frame = ttk.LabelFrame(outer, text="Generated post", padding=10)
        post_frame.pack(fill="both", expand=True, **pad)
        self.post_text = tk.Text(post_frame, height=8, wrap="word", font=("Segoe UI", 11))
        self.post_text.pack(fill="both", expand=True)
        post_actions = ttk.Frame(post_frame)
        post_actions.pack(fill="x", pady=(8, 0))
        ttk.Button(post_actions, text="Copy post", command=self.copy_post).pack(side="left")
        ttk.Button(post_actions, text="Generate another", command=self.generate_now).pack(side="left", padx=8)
        self.char_label = ttk.Label(post_actions, text="0 characters")
        self.char_label.pack(side="right")

        self.status_var = tk.StringVar()
        ttk.Label(outer, textvariable=self.status_var, wraplength=740).pack(anchor="w", pady=(8, 0))
        ttk.Label(outer, text="This app does not log in to X or publish automatically. Review each draft before posting.",
                  foreground="#555555", wraplength=740).pack(anchor="w", pady=(5, 0))

        self.post_text.bind("<KeyRelease>", self.update_char_count)

    def choose_csv(self):
        path = filedialog.askopenfilename(
            title="Choose sample posts CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if path:
            self.samples_path = Path(path)
            self.csv_var.set(path)
            self._refresh_sample_count()

    def _refresh_sample_count(self):
        samples = load_samples(Path(self.csv_var.get()))
        self.sample_count_label.config(text=f"{len(samples)} samples")

    def save_settings(self, quiet=False):
        try:
            minimum = int(self.min_var.get())
            maximum = int(self.max_var.get())
            min_chars = int(self.min_chars_var.get())
            max_chars = int(self.max_chars_var.get())
            if minimum < 1 or maximum < minimum:
                raise ValueError("Interval must be positive, and maximum must be at least minimum.")
            if min_chars < 220:
                raise ValueError("Minimum characters should be at least 220.")
            if max_chars < min_chars:
                raise ValueError("Maximum characters must be at least the minimum character count.")
            self.samples_path = Path(self.csv_var.get()).expanduser()
            self.settings = {
                "model": self.model_var.get().strip() or "llama3.2:3b",
                "min_minutes": minimum,
                "max_minutes": maximum,
                "topic": self.topic_var.get().strip(),
                "instruction": self.instruction_text.get("1.0", "end").strip(),
                "language": self.language_var.get(),
                "min_chars": min_chars,
                "max_chars": max_chars,
                "samples_path": str(self.samples_path),
                "auto_start": False
            }
            write_json(SETTINGS_FILE, self.settings)
            if not quiet:
                self._set_status("Settings saved.")
            self._refresh_sample_count()
            return True
        except Exception as exc:
            if not quiet:
                messagebox.showerror("Invalid settings", str(exc))
            return False

    def _set_status(self, message):
        self.status_var.set(message)

    def update_char_count(self, event=None):
        value = self.post_text.get("1.0", "end-1c")
        self.char_label.config(text=f"{len(value)} characters")

    def copy_post(self):
        value = self.post_text.get("1.0", "end-1c").strip()
        if not value:
            messagebox.showinfo("Nothing to copy", "Generate a post first.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.root.update()
        self._set_status("Post copied. Paste it into X and publish it manually.")

    def generate_now(self):
        if self.busy:
            self._set_status("A post is already being generated. Please wait.")
            return
        if not self.save_settings(quiet=True):
            messagebox.showerror("Settings", "Please check the interval and character limit.")
            return
        samples = load_samples(self.samples_path)
        if not samples:
            messagebox.showerror("CSV needed", "Choose a CSV with a 'text' column, and add at least one sample post.")
            return
        self.busy = True
        self._set_status("Generating a new draft with local Ollama…")
        threading.Thread(target=self._generate_worker, args=(samples,), daemon=True).start()

    def _generate_worker(self, samples):
        try:
            sample_text = "\n".join(f"- {s}" for s in random.sample(samples, min(12, len(samples))))
            recent = [x.get("text", "") for x in self.history[-15:]]
            recent_text = "\n".join(f"- {s}" for s in recent) if recent else "(none)"
            prompt = f"""Create exactly ONE original X post.
Topic: {self.settings['topic']}
Language: {self.settings['language']}
User instructions: {self.settings['instruction']}
Length: {self.settings['min_chars']} to {self.settings['max_chars']} characters, including spaces.
Use the examples to learn tone and style, not to copy sentences verbatim.
Avoid repeating recent generated posts. Do not invent project facts, metrics, promises, or financial guarantees.
Return only the post text, without quotation marks or explanation.
SAMPLE POSTS:
{sample_text}
RECENTLY GENERATED POSTS TO AVOID:
{recent_text}
"""
            content = ollama_chat(
                self.settings["model"],
                [
                    {"role": "system", "content": "You are a careful social-media copywriter. Follow the user's constraints and output only one draft."},
                    {"role": "user", "content": prompt}
                ]
            )
            content = content.strip().strip('"').strip()
            if len(content) > self.settings["max_chars"]:
                content = content[:self.settings["max_chars"]].rsplit(" ", 1)[0].rstrip()
            if not content:
                raise RuntimeError("Ollama returned an empty draft.")
            self.root.after(0, self._show_generated, content)
        except urllib.error.URLError:
            self.root.after(0, self._generation_error, "Can't connect to Ollama. Install/open Ollama and download the selected model.")
        except Exception as exc:
            self.root.after(0, self._generation_error, f"Could not generate post: {exc}")
        finally:
            self.busy = False

    def _show_generated(self, content):
        self.post_text.delete("1.0", "end")
        self.post_text.insert("1.0", content)
        self.update_char_count()
        self.history.append({"text": content, "created_at": datetime.now().isoformat(timespec="seconds")})
        self.history = self.history[-500:]
        write_json(HISTORY_FILE, self.history)
        self._set_status("Draft ready. Review it, then click Copy post to publish manually on X.")
        self._notify("Your X post draft is ready", content)

    def _generation_error(self, message):
        self._set_status(message)
        messagebox.showerror("Generation failed", message)

    def _notify(self, title, body):
        # Tk popup keeps notification functional without third-party packages.
        popup = tk.Toplevel(self.root)
        popup.title(title)
        popup.geometry("440x240")
        popup.attributes("-topmost", True)
        frame = ttk.Frame(popup, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=title, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        box = tk.Text(frame, height=5, wrap="word")
        box.pack(fill="both", expand=True, pady=8)
        box.insert("1.0", body)
        box.config(state="disabled")
        row = ttk.Frame(frame)
        row.pack(fill="x")
        ttk.Button(row, text="Copy post", command=lambda: self._copy_from_popup(body, popup)).pack(side="left")
        ttk.Button(row, text="Open main window", command=popup.destroy).pack(side="right")

    def _copy_from_popup(self, body, popup):
        self.root.clipboard_clear()
        self.root.clipboard_append(body)
        self.root.update()
        self._set_status("Post copied from notification. Paste into X and publish manually.")
        popup.destroy()

    def start(self):
        if not self.save_settings(quiet=True):
            messagebox.showerror("Settings", "Please check the interval and character limit.")
            return
        if not load_samples(self.samples_path):
            messagebox.showerror("CSV needed", "Add sample posts to your CSV before starting.")
            return
        if self.running:
            return
        self.running = True
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self._schedule_next(first=True)

    def _schedule_next(self, first=False):
        if not self.running:
            return
        minimum = int(self.settings["min_minutes"])
        maximum = int(self.settings["max_minutes"])
        minutes = random.randint(minimum, maximum)
        self.next_post_at = time.time() + minutes * 60
        self._set_status(f"Reminders running. Next draft in about {minutes} minutes; this app must stay open.")
        self.timer_id = self.root.after(minutes * 60 * 1000, self._scheduled_generate)

    def _scheduled_generate(self):
        if not self.running:
            return
        self.generate_now()
        # Schedule the next reminder interval from this trigger; generation can take additional time.
        self._schedule_next()

    def stop(self):
        self.running = False
        if self.timer_id is not None:
            try:
                self.root.after_cancel(self.timer_id)
            except Exception:
                pass
            self.timer_id = None
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self._set_status("Reminders stopped.")

    def on_close(self):
        self.stop()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:
        pass
    App(root)
    root.mainloop()
