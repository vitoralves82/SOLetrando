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

    def __init__(self, width=560, height=180):
        self._commands = queue.Queue()
        self._thread = None
        self._ready = threading.Event()
        self._width = int(width)
        self._height = int(height)

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

    def configure(self, width, height):
        """Redimensiona a caixa sem reiniciar o aplicativo."""
        self._commands.put(("configure", int(width), int(height)))

    def stop(self):
        self._commands.put(("stop",))

    def _run(self):
        try:
            import tkinter as tk
            from tkinter import ttk

            root = tk.Tk()
            root.withdraw()
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.configure(bg="#E9F5F1")

            frame = tk.Frame(root, bg="#E9F5F1", padx=14, pady=10)
            frame.pack(fill="both", expand=True)
            title = tk.Label(
                frame, text="SOLetrando", font=("Segoe UI Semibold", 12),
                bg="#E9F5F1", fg="#005847", anchor="w", cursor="fleur",
            )
            title.pack(fill="x")

            text_frame = tk.Frame(frame, bg="#E9F5F1")
            text_frame.pack(fill="both", expand=True, pady=(4, 0))
            detail = tk.Text(
                text_frame, font=("Segoe UI", 10), bg="#E9F5F1",
                fg="#20332E", wrap="word", relief="flat", borderwidth=0,
                highlightthickness=0, padx=0, pady=0, cursor="arrow",
            )
            scrollbar = ttk.Scrollbar(
                text_frame, orient="vertical", command=detail.yview
            )
            detail.configure(yscrollcommand=scrollbar.set)
            detail.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y", padx=(8, 0))
            detail.configure(state="disabled")

            drag_origin = {"x": 0, "y": 0}

            def start_drag(event):
                drag_origin["x"] = event.x_root - root.winfo_x()
                drag_origin["y"] = event.y_root - root.winfo_y()

            def drag(event):
                root.geometry(
                    f"+{event.x_root - drag_origin['x']}"
                    f"+{event.y_root - drag_origin['y']}"
                )

            title.bind("<ButtonPress-1>", start_drag)
            title.bind("<B1-Motion>", drag)

            def place_at_bottom_right(width, height):
                x = root.winfo_screenwidth() - width - 24
                y = root.winfo_screenheight() - height - 72
                root.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")

            place_at_bottom_right(self._width, self._height)
            hide_deadline = None
            self._ready.set()

            def set_text(message):
                # Mantem a posicao de leitura quando o usuario rolou para cima.
                _first, last = detail.yview()
                was_at_end = last >= 0.98
                detail.configure(state="normal")
                detail.delete("1.0", "end")
                detail.insert("1.0", message)
                detail.configure(state="disabled")
                if was_at_end:
                    detail.see("end")

            def poll():
                nonlocal hide_deadline
                try:
                    while True:
                        command = self._commands.get_nowait()
                        if command[0] == "stop":
                            root.destroy()
                            return
                        if command[0] == "configure":
                            _, width, height = command
                            self._width, self._height = width, height
                            place_at_bottom_right(width, height)
                            continue

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
                        text_frame.configure(bg=background)
                        title.configure(
                            text=f"SOLetrando  •  {labels.get(state, state)}",
                            bg=background, fg=accent,
                        )
                        detail.configure(bg=background)
                        set_text(message)
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


def show_settings_window(config, on_save, model_options=None, actions=None):
    """Abre as configuracoes, a ajuda e as ferramentas do aplicativo."""
    global _settings_open
    with _settings_lock:
        if _settings_open:
            return False
        _settings_open = True

    model_options = list(model_options or [])
    actions = dict(actions or {})
    snapshot = {
        "model": str(config.get("model", "large-v3-turbo")),
        "overlay_width": int(config.get("overlay_width", 560)),
        "overlay_height": int(config.get("overlay_height", 180)),
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
            from tkinter import messagebox, scrolledtext, ttk
            from soletrando_text import parse_corrections

            root = tk.Tk()
            root.title("Configurações do SOLetrando")
            root.geometry("760x620")
            root.minsize(680, 540)
            root.configure(bg="#F7FAF9")

            style = ttk.Style(root)
            try:
                style.theme_use("vista")
            except tk.TclError:
                pass
            style.configure("TNotebook", background="#F7FAF9", borderwidth=0)
            style.configure("TNotebook.Tab", padding=(14, 7))

            container = tk.Frame(root, bg="#F7FAF9", padx=24, pady=18)
            container.pack(fill="both", expand=True)
            tk.Label(
                container, text="SOLetrando", font=("Segoe UI Semibold", 19),
                bg="#F7FAF9", fg="#005847", anchor="w",
            ).pack(fill="x")
            tk.Label(
                container,
                text="Personalize o ditado, consulte a ajuda e acesse o diagnóstico.",
                font=("Segoe UI", 10), bg="#F7FAF9", fg="#40544E", anchor="w",
            ).pack(fill="x", pady=(2, 14))

            notebook = ttk.Notebook(container)
            notebook.pack(fill="both", expand=True)
            general_tab = ttk.Frame(notebook, padding=18)
            vocabulary_tab = ttk.Frame(notebook, padding=18)
            help_tab = ttk.Frame(notebook, padding=18)
            tools_tab = ttk.Frame(notebook, padding=18)
            notebook.add(general_tab, text="Geral")
            notebook.add(vocabulary_tab, text="Vocabulário")
            notebook.add(help_tab, text="Como usar")
            notebook.add(tools_tab, text="Diagnóstico")

            preview_var = tk.BooleanVar(value=snapshot["live_preview_enabled"])
            history_var = tk.BooleanVar(value=snapshot["save_history"])
            log_var = tk.BooleanVar(value=snapshot["log_transcripts"])
            width_var = tk.StringVar(value=str(snapshot["overlay_width"]))
            height_var = tk.StringVar(value=str(snapshot["overlay_height"]))

            ttk.Label(
                general_tab, text="Reconhecimento",
                font=("Segoe UI Semibold", 11),
            ).grid(row=0, column=0, columnspan=2, sticky="w")
            ttk.Label(general_tab, text="Modelo de transcrição").grid(
                row=1, column=0, sticky="w", pady=(12, 4)
            )
            model_by_label = {label: key for label, key in model_options}
            label_by_model = {key: label for label, key in model_options}
            current_model_label = label_by_model.get(
                snapshot["model"], snapshot["model"]
            )
            model_var = tk.StringVar(value=current_model_label)
            model_combo = ttk.Combobox(
                general_tab, textvariable=model_var, state="readonly",
                values=list(model_by_label) or [current_model_label], width=38,
            )
            model_combo.grid(row=1, column=1, sticky="ew", pady=(12, 4))
            ttk.Label(
                general_tab,
                text="A troca é aplicada após salvar e pode levar alguns segundos.",
                foreground="#60716C",
            ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 18))

            ttk.Separator(general_tab).grid(
                row=3, column=0, columnspan=2, sticky="ew", pady=(0, 16)
            )
            ttk.Label(
                general_tab, text="Caixa de prévia",
                font=("Segoe UI Semibold", 11),
            ).grid(row=4, column=0, columnspan=2, sticky="w")
            ttk.Label(general_tab, text="Largura em pixels").grid(
                row=5, column=0, sticky="w", pady=(12, 4)
            )
            ttk.Spinbox(
                general_tab, from_=360, to=1000, increment=20,
                textvariable=width_var, width=12,
            ).grid(row=5, column=1, sticky="w", pady=(12, 4))
            ttk.Label(general_tab, text="Altura em pixels").grid(
                row=6, column=0, sticky="w", pady=4
            )
            ttk.Spinbox(
                general_tab, from_=120, to=600, increment=20,
                textvariable=height_var, width=12,
            ).grid(row=6, column=1, sticky="w", pady=4)
            ttk.Label(
                general_tab,
                text="Faixas permitidas: 360–1000 px de largura e 120–600 px de altura.",
                foreground="#60716C",
            ).grid(row=7, column=0, columnspan=2, sticky="w", pady=(2, 14))
            ttk.Checkbutton(
                general_tab, text="Mostrar prévia do texto durante o ditado",
                variable=preview_var,
            ).grid(row=8, column=0, columnspan=2, sticky="w", pady=2)
            ttk.Checkbutton(
                general_tab, text="Guardar histórico local dos ditados",
                variable=history_var,
            ).grid(row=9, column=0, columnspan=2, sticky="w", pady=2)
            ttk.Checkbutton(
                general_tab, text="Incluir o texto integral no registro técnico",
                variable=log_var,
            ).grid(row=10, column=0, columnspan=2, sticky="w", pady=2)
            general_tab.columnconfigure(1, weight=1)

            ttk.Label(
                vocabulary_tab, text="Vocabulário preferencial",
                font=("Segoe UI Semibold", 11),
            ).pack(fill="x")
            ttk.Label(
                vocabulary_tab,
                text="Um termo por linha. Exemplo: EnvironPact, PROCLIM, Camarupim.",
                foreground="#60716C",
            ).pack(fill="x", pady=(2, 5))
            vocabulary = scrolledtext.ScrolledText(
                vocabulary_tab, height=7, font=("Segoe UI", 10), wrap="word",
                relief="solid", borderwidth=1,
            )
            vocabulary.pack(fill="both", expand=True)
            vocabulary.insert("1.0", "\n".join(snapshot["vocabulary"]))

            ttk.Label(
                vocabulary_tab, text="Correções automáticas",
                font=("Segoe UI Semibold", 11),
            ).pack(fill="x", pady=(14, 0))
            ttk.Label(
                vocabulary_tab, text="Uma por linha: texto ouvido = texto correto.",
                foreground="#60716C",
            ).pack(fill="x", pady=(2, 5))
            corrections = scrolledtext.ScrolledText(
                vocabulary_tab, height=7, font=("Segoe UI", 10), wrap="word",
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

            guide = (
                "COMEÇAR A DITAR\n"
                "1. Coloque o cursor no campo que receberá o texto.\n"
                "2. Pressione a tecla configurada para iniciar.\n"
                "3. Fale normalmente e acompanhe a prévia.\n"
                "4. Pressione a mesma tecla para concluir e inserir o texto.\n\n"
                "PRÉVIA E HISTÓRICO\n"
                "A barra lateral da caixa permite rever trechos anteriores. O texto "
                "final também fica disponível em Copiar último ditado.\n\n"
                "VOCABULÁRIO E CORREÇÕES\n"
                "Use Vocabulário preferencial para nomes próprios e termos técnicos. "
                "Use Correções automáticas para erros recorrentes, por exemplo: "
                "pro clima = PROCLIM.\n\n"
                "PRIVACIDADE E DIAGNÓSTICO\n"
                "O histórico é local. O registro técnico não contém o texto completo, "
                "a menos que essa opção seja marcada. Em caso de falha, abra o registro "
                "técnico na aba Diagnóstico."
            )
            guide_text = scrolledtext.ScrolledText(
                help_tab, font=("Segoe UI", 10), wrap="word", relief="flat",
                background="#FFFFFF", padx=12, pady=10,
            )
            guide_text.pack(fill="both", expand=True)
            guide_text.insert("1.0", guide)
            guide_text.configure(state="disabled")

            ttk.Label(
                tools_tab, text="Arquivos e suporte",
                font=("Segoe UI Semibold", 11),
            ).pack(anchor="w")
            ttk.Label(
                tools_tab,
                text="Use estas opções para consultar dados locais ou remover o aplicativo.",
                foreground="#60716C",
            ).pack(anchor="w", pady=(2, 16))

            def action_button(label, action_name):
                callback = actions.get(action_name)
                button = ttk.Button(
                    tools_tab, text=label,
                    command=callback if callback else lambda: None,
                )
                button.pack(fill="x", pady=4)
                if callback is None:
                    button.state(["disabled"])

            action_button("Abrir registro técnico", "open_log")
            action_button("Abrir histórico de ditados", "open_history")
            action_button("Abrir pasta do SOLetrando", "open_folder")
            ttk.Separator(tools_tab).pack(fill="x", pady=16)
            action_button("Desinstalar SOLetrando...", "uninstall")

            buttons = tk.Frame(container, bg="#F7FAF9")
            buttons.pack(fill="x", pady=(14, 0))

            def save():
                try:
                    parsed = parse_corrections(corrections.get("1.0", "end"))
                    width = int(width_var.get())
                    height = int(height_var.get())
                    if not 360 <= width <= 1000 or not 120 <= height <= 600:
                        raise ValueError(
                            "Use largura entre 360 e 1000 e altura entre 120 e 600."
                        )
                except ValueError as error:
                    messagebox.showerror(
                        "Configuração inválida", str(error), parent=root
                    )
                    return
                values = {
                    "model": model_by_label.get(model_var.get(), snapshot["model"]),
                    "overlay_width": width,
                    "overlay_height": height,
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
            ttk.Button(buttons, text="Salvar", command=save).pack(
                side="right", padx=(0, 8)
            )
            root.protocol("WM_DELETE_WINDOW", root.destroy)
            root.mainloop()
        finally:
            with _settings_lock:
                _settings_open = False

    threading.Thread(target=run, name="soletrando-settings", daemon=True).start()
    return True
