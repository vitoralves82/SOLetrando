"""Janelas leves de estado e configuracao do SOLetrando."""

import queue
import threading
import time


COLORS = {
    "idle": ("#E9F5F1", "#005847"),
    "recording": ("#E8F7EE", "#147D3F"),
    "transcribing": ("#FFF4E8", "#B85B0B"),
    "done": ("#E9F5F1", "#005847"),
    "error": ("#FDECEC", "#A12622"),
}


class StatusOverlay:
    """Indicador flutuante controlado por uma fila segura entre threads."""

    def __init__(self):
        self._commands = queue.Queue()
        self._thread = None
        self._ready = threading.Event()

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run, name="soletrando-status", daemon=True
        )
        self._thread.start()
        self._ready.wait(3)

    def set_state(self, state, detail="", hide_after=None):
        self._commands.put(("state", state, str(detail), hide_after))

    def stop(self):
        self._commands.put(("stop",))

    def _run(self):
        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.configure(bg="#E9F5F1")

            frame = tk.Frame(root, bg="#E9F5F1", padx=16, pady=12)
            frame.pack(fill="both", expand=True)
            title = tk.Label(
                frame, text="SOLetrando", font=("Segoe UI Semibold", 12),
                bg="#E9F5F1", fg="#005847", anchor="w",
            )
            title.pack(fill="x")
            detail = tk.Label(
                frame, text="", font=("Segoe UI", 10), bg="#E9F5F1",
                fg="#20332E", anchor="w", justify="left", wraplength=410,
            )
            detail.pack(fill="x", pady=(3, 0))

            root.update_idletasks()
            width, height = 460, 92
            x = root.winfo_screenwidth() - width - 24
            y = root.winfo_screenheight() - height - 72
            root.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")

            hide_deadline = None
            self._ready.set()

            def poll():
                nonlocal hide_deadline
                try:
                    while True:
                        command = self._commands.get_nowait()
                        if command[0] == "stop":
                            root.destroy()
                            return
                        _, state, message, hide_after = command
                        background, accent = COLORS.get(state, COLORS["idle"])
                        labels = {
                            "idle": "Pronto para ditar",
                            "recording": "Gravando",
                            "transcribing": "Transcrevendo",
                            "done": "Texto pronto",
                            "error": "Atenção necessária",
                        }
                        frame.configure(bg=background)
                        title.configure(
                            text=f"SOLetrando  •  {labels.get(state, state)}",
                            bg=background, fg=accent,
                        )
                        detail.configure(text=message, bg=background)
                        root.deiconify()
                        root.lift()
                        hide_deadline = (
                            time.monotonic() + hide_after if hide_after else None
                        )
                except queue.Empty:
                    pass

                if hide_deadline and time.monotonic() >= hide_deadline:
                    root.withdraw()
                    hide_deadline = None
                root.after(80, poll)

            root.after(80, poll)
            root.mainloop()
        except Exception:
            self._ready.set()


_settings_lock = threading.Lock()
_settings_open = False


def show_settings_window(config, on_save):
    """Abre uma janela clara para vocabulario e comportamento do ditado."""
    global _settings_open
    with _settings_lock:
        if _settings_open:
            return False
        _settings_open = True

    snapshot = {
        "vocabulary": list(config.get("vocabulary", [])),
        "corrections": dict(config.get("corrections", {})),
        "live_preview_enabled": bool(config.get("live_preview_enabled", True)),
        "save_history": bool(config.get("save_history", True)),
        "log_transcripts": bool(config.get("log_transcripts", False)),
    }

    def run():
        global _settings_open
        try:
            import tkinter as tk
            from tkinter import messagebox, ttk
            from soletrando_text import parse_corrections

            root = tk.Tk()
            root.title("Configurações do SOLetrando")
            root.geometry("680x650")
            root.minsize(600, 560)
            root.configure(bg="#F7FAF9")

            style = ttk.Style(root)
            try:
                style.theme_use("vista")
            except tk.TclError:
                pass

            container = tk.Frame(root, bg="#F7FAF9", padx=24, pady=20)
            container.pack(fill="both", expand=True)
            tk.Label(
                container, text="SOLetrando", font=("Segoe UI Semibold", 19),
                bg="#F7FAF9", fg="#005847", anchor="w",
            ).pack(fill="x")
            tk.Label(
                container,
                text="Personalize o reconhecimento e o histórico dos seus ditados.",
                font=("Segoe UI", 10), bg="#F7FAF9", fg="#40544E", anchor="w",
            ).pack(fill="x", pady=(2, 18))

            tk.Label(
                container, text="Vocabulário preferencial",
                font=("Segoe UI Semibold", 11), bg="#F7FAF9", fg="#20332E",
                anchor="w",
            ).pack(fill="x")
            tk.Label(
                container, text="Um termo por linha. Exemplo: EnvironPact, PROCLIM, Camarupim.",
                font=("Segoe UI", 9), bg="#F7FAF9", fg="#60716C", anchor="w",
            ).pack(fill="x", pady=(0, 5))
            vocabulary = tk.Text(
                container, height=8, font=("Segoe UI", 10), wrap="word",
                relief="solid", borderwidth=1,
            )
            vocabulary.pack(fill="both", expand=True)
            vocabulary.insert("1.0", "\n".join(snapshot["vocabulary"]))

            tk.Label(
                container, text="Correções automáticas",
                font=("Segoe UI Semibold", 11), bg="#F7FAF9", fg="#20332E",
                anchor="w",
            ).pack(fill="x", pady=(16, 0))
            tk.Label(
                container, text="Uma por linha: texto ouvido = texto correto.",
                font=("Segoe UI", 9), bg="#F7FAF9", fg="#60716C", anchor="w",
            ).pack(fill="x", pady=(0, 5))
            corrections = tk.Text(
                container, height=8, font=("Segoe UI", 10), wrap="word",
                relief="solid", borderwidth=1,
            )
            corrections.pack(fill="both", expand=True)
            corrections.insert(
                "1.0",
                "\n".join(
                    f"{source} = {target}"
                    for source, target in snapshot["corrections"].items()
                ),
            )

            preview_var = tk.BooleanVar(value=snapshot["live_preview_enabled"])
            history_var = tk.BooleanVar(value=snapshot["save_history"])
            log_var = tk.BooleanVar(value=snapshot["log_transcripts"])
            ttk.Checkbutton(
                container, text="Mostrar prévia do texto durante o ditado",
                variable=preview_var,
            ).pack(anchor="w", pady=(16, 2))
            ttk.Checkbutton(
                container, text="Guardar histórico local dos ditados",
                variable=history_var,
            ).pack(anchor="w", pady=2)
            ttk.Checkbutton(
                container, text="Incluir o texto integral no registro técnico",
                variable=log_var,
            ).pack(anchor="w", pady=2)

            buttons = tk.Frame(container, bg="#F7FAF9")
            buttons.pack(fill="x", pady=(18, 0))

            def save():
                try:
                    parsed = parse_corrections(corrections.get("1.0", "end"))
                except ValueError as error:
                    messagebox.showerror("Correções inválidas", str(error), parent=root)
                    return
                values = {
                    "vocabulary": [
                        line.strip()
                        for line in vocabulary.get("1.0", "end").splitlines()
                        if line.strip()
                    ],
                    "corrections": parsed,
                    "live_preview_enabled": preview_var.get(),
                    "save_history": history_var.get(),
                    "log_transcripts": log_var.get(),
                }
                on_save(values)
                root.destroy()

            ttk.Button(buttons, text="Cancelar", command=root.destroy).pack(side="right")
            ttk.Button(buttons, text="Salvar", command=save).pack(side="right", padx=(0, 8))
            root.mainloop()
        finally:
            with _settings_lock:
                _settings_open = False

    threading.Thread(target=run, name="soletrando-settings", daemon=True).start()
    return True
