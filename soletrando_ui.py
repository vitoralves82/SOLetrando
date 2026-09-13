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
    "preview": ("#F2F7F5", "#005847"),
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

    def set_state(self, state, detail="", hide_after=None, force_show=False):
        self._commands.put(
            ("state", state, str(detail), hide_after, bool(force_show))
        )

    def configure(self, width, height):
        """Redimensiona a caixa sem reiniciar o aplicativo."""
        self._commands.put(("configure", int(width), int(height)))

    def hide(self):
        """Oculta a caixa ate o inicio da proxima gravacao."""
        self._commands.put(("hide",))

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

            frame = tk.Frame(root, bg="#E9F5F1", padx=10, pady=6)
            frame.pack(fill="both", expand=True)
            header = tk.Frame(frame, bg="#E9F5F1")
            header.pack(fill="x")
            badge = tk.Canvas(
                header, width=16, height=16, bg="#E9F5F1",
                highlightthickness=0, borderwidth=0,
            )
            badge.pack(side="left", padx=(0, 6))
            badge_circle = badge.create_oval(
                1, 1, 15, 15, fill="#005847", outline=""
            )
            badge.create_text(
                8, 8, text="S", fill="#FFFFFF",
                font=("Segoe UI Semibold", 7),
            )
            title = tk.Label(
                header, text="SOLetrando", font=("Segoe UI Semibold", 10),
                bg="#E9F5F1", fg="#005847", anchor="w", cursor="fleur",
            )
            title.pack(side="left", fill="x", expand=True)
            close_button = tk.Button(
                header, text="×", font=("Segoe UI", 10), bg="#E9F5F1",
                fg="#74837E", activebackground="#E9F5F1",
                activeforeground="#20332E", relief="flat", borderwidth=0,
                highlightthickness=0, padx=3, pady=0, takefocus=0,
            )
            close_button.pack(side="right")

            text_frame = tk.Frame(frame, bg="#E9F5F1")
            text_frame.pack(fill="both", expand=True, pady=(4, 0))
            detail = tk.Text(
                text_frame, font=("Segoe UI", 10), bg="#E9F5F1",
                fg="#20332E", wrap="word", relief="flat", borderwidth=0,
                highlightthickness=0, padx=0, pady=0, cursor="arrow",
                width=1, height=1, takefocus=0,
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

            # O Tk usa pixels logicos. Convertemos para que os valores das
            # configuracoes representem aproximadamente pixels reais na tela.
            dpi_scale = max(1.0, root.winfo_fpixels("1i") / 96.0)

            def place_at_bottom_right(width, height):
                logical_width = max(150, round(width / dpi_scale))
                logical_height = max(55, round(height / dpi_scale))
                x = root.winfo_screenwidth() - logical_width - 16
                y = root.winfo_screenheight() - logical_height - 48
                root.geometry(
                    f"{logical_width}x{logical_height}+{max(0, x)}+{max(0, y)}"
                )

            place_at_bottom_right(self._width, self._height)
            hide_deadline = None
            current_state = None
            dismissed = False

            window_handle = None
            if __import__("os").name == "nt":
                try:
                    import ctypes

                    user32 = ctypes.windll.user32
                    user32.GetParent.restype = ctypes.c_void_p
                    user32.GetParent.argtypes = [ctypes.c_void_p]
                    user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
                    user32.SetWindowLongW.argtypes = [
                        ctypes.c_void_p, ctypes.c_int, ctypes.c_long
                    ]
                    window_handle = root.winfo_id()
                    parent_handle = user32.GetParent(window_handle)
                    if parent_handle:
                        window_handle = parent_handle
                    GWL_EXSTYLE = -20
                    WS_EX_TOOLWINDOW = 0x00000080
                    WS_EX_NOACTIVATE = 0x08000000
                    current_style = user32.GetWindowLongW(
                        window_handle, GWL_EXSTYLE
                    )
                    user32.SetWindowLongW(
                        window_handle, GWL_EXSTYLE,
                        current_style | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
                    )
                except Exception:
                    window_handle = None

            def show_without_focus():
                root.deiconify()
                if window_handle:
                    try:
                        import ctypes

                        SW_SHOWNOACTIVATE = 4
                        HWND_TOPMOST = ctypes.c_void_p(-1)
                        SWP_NOSIZE = 0x0001
                        SWP_NOMOVE = 0x0002
                        SWP_NOACTIVATE = 0x0010
                        user32 = ctypes.windll.user32
                        user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
                        user32.SetWindowPos.argtypes = [
                            ctypes.c_void_p, ctypes.c_void_p,
                            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                            ctypes.c_uint,
                        ]
                        user32.ShowWindow(
                            window_handle, SW_SHOWNOACTIVATE
                        )
                        user32.SetWindowPos(
                            window_handle, HWND_TOPMOST, 0, 0, 0, 0,
                            SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE,
                        )
                        return
                    except Exception:
                        pass
                root.lift()

            def dismiss():
                nonlocal dismissed, hide_deadline
                dismissed = True
                hide_deadline = None
                root.withdraw()

            close_button.configure(command=dismiss)
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
                nonlocal hide_deadline, current_state, dismissed
                try:
                    while True:
                        command = self._commands.get_nowait()
                        if command[0] == "stop":
                            root.destroy()
                            return
                        if command[0] == "hide":
                            dismiss()
                            continue
                        if command[0] == "configure":
                            _, width, height = command
                            self._width, self._height = width, height
                            place_at_bottom_right(width, height)
                            continue

                        _, state, message, hide_after, force_show = command
                        state_changed = state != current_state
                        if state == "recording" and state_changed:
                            dismissed = False
                        if force_show:
                            dismissed = False
                        current_state = state
                        background, accent = COLORS.get(state, COLORS["idle"])
                        labels = {
                            "idle": "Pronto para ditar",
                            "recording": "Gravando",
                            "transcribing": "Transcrevendo",
                            "done": "Texto pronto",
                            "error": "Atenção necessária",
                            "preview": "Prévia de tamanho",
                        }
                        frame.configure(bg=background)
                        header.configure(bg=background)
                        badge.configure(bg=background)
                        badge.itemconfigure(badge_circle, fill=accent)
                        text_frame.configure(bg=background)
                        title.configure(
                            text=f"SOLetrando  •  {labels.get(state, state)}",
                            bg=background, fg=accent,
                        )
                        close_button.configure(
                            bg=background, activebackground=background
                        )
                        detail.configure(bg=background)
                        set_text(message)
                        if state_changed:
                            if hide_after is None:
                                hide_deadline = None
                            elif hide_after <= 0:
                                dismissed = True
                                hide_deadline = None
                                root.withdraw()
                            else:
                                hide_deadline = time.monotonic() + hide_after
                        if not dismissed:
                            show_without_focus()
                except queue.Empty:
                    pass

                if hide_deadline and time.monotonic() >= hide_deadline:
                    dismiss()
                root.after(80, poll)

            root.after(80, poll)
            root.mainloop()
        except Exception:
            self._ready.set()


_settings_lock = threading.Lock()
_settings_open = False


def _set_window_icon(root):
    """Aplica o icone oficial tanto no codigo-fonte quanto no executavel."""
    try:
        import sys
        from pathlib import Path

        candidates = [Path(sys.executable).parent / "soletrando.ico"]
        candidates.append(Path(__file__).parent / "soletrando.ico")
        for icon_path in candidates:
            if icon_path.exists():
                root.iconbitmap(default=str(icon_path))
                return
    except Exception:
        pass


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
        "overlay_width": int(config.get("overlay_width", 320)),
        "overlay_height": int(config.get("overlay_height", 110)),
        "overlay_recording_seconds": float(
            config.get("overlay_recording_seconds", 0.0)
        ),
        "overlay_done_seconds": float(config.get("overlay_done_seconds", 1.0)),
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
            root.geometry("760x650")
            root.minsize(680, 590)
            root.configure(bg="#F4F7F6")
            _set_window_icon(root)

            style = ttk.Style(root)
            try:
                style.theme_use("clam")
            except tk.TclError:
                pass
            style.configure("TFrame", background="#FFFFFF")
            style.configure("TLabel", background="#FFFFFF", foreground="#20332E")
            style.configure(
                "TCheckbutton", background="#FFFFFF", foreground="#20332E"
            )
            style.map(
                "TCheckbutton", background=[("active", "#FFFFFF")]
            )
            style.configure("TNotebook", background="#F4F7F6", borderwidth=0)
            style.configure(
                "TNotebook.Tab", padding=(16, 8), background="#E5ECE9",
                foreground="#31443E",
            )
            style.map(
                "TNotebook.Tab",
                background=[("selected", "#005847")],
                foreground=[("selected", "#FFFFFF")],
            )
            style.configure(
                "Accent.TButton", background="#005847", foreground="#FFFFFF",
                padding=(16, 7), borderwidth=0,
            )
            style.map(
                "Accent.TButton", background=[("active", "#00705A")]
            )

            tk.Frame(root, bg="#E07D28", height=4).pack(fill="x")
            container = tk.Frame(root, bg="#F4F7F6", padx=24, pady=18)
            container.pack(fill="both", expand=True)
            tk.Label(
                container, text="SOLetrando", font=("Segoe UI Semibold", 19),
                bg="#F4F7F6", fg="#005847", anchor="w",
            ).pack(fill="x")
            tk.Label(
                container,
                text="Personalize o ditado, consulte a ajuda e acesse o diagnóstico.",
                font=("Segoe UI", 10), bg="#F4F7F6", fg="#40544E", anchor="w",
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
            recording_options = {
                "Durante todo o ditado": 0.0,
                "1 segundo": 1.0,
                "3 segundos": 3.0,
                "5 segundos": 5.0,
                "10 segundos": 10.0,
            }
            done_options = {
                "Imediatamente": 0.0,
                "1 segundo": 1.0,
                "3 segundos": 3.0,
                "5 segundos": 5.0,
                "10 segundos": 10.0,
                "Manter aberta": -1.0,
            }

            def label_for(options, value, fallback):
                for label, seconds in options.items():
                    if seconds == value:
                        return label
                return fallback

            recording_time_var = tk.StringVar(
                value=label_for(
                    recording_options, snapshot["overlay_recording_seconds"],
                    "Durante todo o ditado",
                )
            )
            done_time_var = tk.StringVar(
                value=label_for(
                    done_options, snapshot["overlay_done_seconds"], "1 segundo"
                )
            )

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
            if snapshot["model"] in label_by_model:
                model_combo.current(
                    list(model_by_label).index(label_by_model[snapshot["model"]])
                )
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
                general_tab, from_=220, to=1000, increment=20,
                textvariable=width_var, width=12,
            ).grid(row=5, column=1, sticky="w", pady=(12, 4))
            ttk.Label(general_tab, text="Altura em pixels").grid(
                row=6, column=0, sticky="w", pady=4
            )
            ttk.Spinbox(
                general_tab, from_=76, to=600, increment=10,
                textvariable=height_var, width=12,
            ).grid(row=6, column=1, sticky="w", pady=4)
            ttk.Label(
                general_tab,
                text="Faixas permitidas: 220–1000 px de largura e 76–600 px de altura.",
                foreground="#60716C",
            ).grid(row=7, column=0, columnspan=2, sticky="w", pady=(2, 14))
            ttk.Label(general_tab, text="Ocultar durante a gravação").grid(
                row=8, column=0, sticky="w", pady=4
            )
            ttk.Combobox(
                general_tab, textvariable=recording_time_var, state="readonly",
                values=list(recording_options), width=26,
            ).grid(row=8, column=1, sticky="w", pady=4)
            ttk.Label(general_tab, text="Ocultar após concluir").grid(
                row=9, column=0, sticky="w", pady=4
            )
            ttk.Combobox(
                general_tab, textvariable=done_time_var, state="readonly",
                values=list(done_options), width=26,
            ).grid(row=9, column=1, sticky="w", pady=4)
            ttk.Checkbutton(
                general_tab, text="Mostrar prévia do texto durante o ditado",
                variable=preview_var,
            ).grid(row=10, column=0, columnspan=2, sticky="w", pady=(12, 2))
            ttk.Checkbutton(
                general_tab, text="Guardar histórico local dos ditados",
                variable=history_var,
            ).grid(row=11, column=0, columnspan=2, sticky="w", pady=2)
            ttk.Checkbutton(
                general_tab, text="Incluir o texto integral no registro técnico",
                variable=log_var,
            ).grid(row=12, column=0, columnspan=2, sticky="w", pady=2)
            general_tab.columnconfigure(1, weight=1)

            preview_job = None

            def refresh_size_preview(*_args):
                nonlocal preview_job
                if preview_job is not None:
                    root.after_cancel(preview_job)

                def apply_preview():
                    try:
                        width = int(width_var.get())
                        height = int(height_var.get())
                    except ValueError:
                        return
                    if 220 <= width <= 1000 and 76 <= height <= 600:
                        callback = actions.get("preview_overlay")
                        if callback:
                            callback(width, height)

                preview_job = root.after(120, apply_preview)

            width_var.trace_add("write", refresh_size_preview)
            height_var.trace_add("write", refresh_size_preview)
            root.after(250, refresh_size_preview)

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
                "final também fica disponível em Copiar último ditado. O botão × "
                "fecha a caixa imediatamente sem cancelar a gravação.\n\n"
                "VOCABULÁRIO E CORREÇÕES\n"
                "Use Vocabulário preferencial para nomes próprios e termos técnicos. "
                "Use Correções automáticas para erros recorrentes, por exemplo: "
                "pro clima = PROCLIM.\n\n"
                "ÍCONE DO SISTEMA\n"
                "O pequeno microfone exibido ao gravar pertence ao sistema operacional. O ícone "
                "do SOLetrando pode ficar dentro da seta de ícones ocultos; arraste-o "
                "uma vez para a área visível se quiser mantê-lo ao lado do relógio.\n\n"
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

            buttons = tk.Frame(container, bg="#F4F7F6")
            buttons.pack(fill="x", pady=(14, 0))

            def cancel():
                callback = actions.get("cancel_overlay_preview")
                if callback:
                    callback()
                root.destroy()

            def save():
                try:
                    parsed = parse_corrections(corrections.get("1.0", "end"))
                    width = int(width_var.get())
                    height = int(height_var.get())
                    if not 220 <= width <= 1000 or not 76 <= height <= 600:
                        raise ValueError(
                            "Use largura entre 220 e 1000 e altura entre 76 e 600."
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
                    "overlay_recording_seconds": recording_options[
                        recording_time_var.get()
                    ],
                    "overlay_done_seconds": done_options[done_time_var.get()],
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
                callback = actions.get("hide_overlay")
                if callback:
                    callback()
                root.destroy()

            ttk.Button(buttons, text="Cancelar", command=cancel).pack(side="right")
            ttk.Button(
                buttons, text="Salvar", command=save, style="Accent.TButton"
            ).pack(
                side="right", padx=(0, 8)
            )
            root.protocol("WM_DELETE_WINDOW", cancel)
            root.mainloop()
        finally:
            with _settings_lock:
                _settings_open = False

    threading.Thread(target=run, name="soletrando-settings", daemon=True).start()
    return True
