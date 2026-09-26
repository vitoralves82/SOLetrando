"""Janelas leves de estado e configuracao do SOLetrando."""

import queue
import threading
import time


COLORS = {
    "idle": ("#F7F8FA", "#D59B00"),
    "recording": ("#EAF2FF", "#2563EB"),
    "transcribing": ("#FFF4CC", "#A66B00"),
    "done": ("#EEF2F7", "#334155"),
    "error": ("#FDECEC", "#A12622"),
    "preview": ("#F7F8FA", "#D59B00"),
    "reading": ("#EAF2FF", "#2563EB"),
}


class StatusOverlay:
    """Indicador flutuante controlado por uma fila segura entre threads."""

    def __init__(self, width=560, height=180):
        self._commands = queue.Queue()
        self._thread = None
        self._ready = threading.Event()
        self._width = int(width)
        self._height = int(height)
        self._read_selection = None
        self._stop_reading = None

    def set_reading_actions(self, read_selection, stop_reading):
        self._read_selection = read_selection
        self._stop_reading = stop_reading

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

            root = tk.Tk()
            root.withdraw()
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.configure(bg="#F7F8FA")

            frame = tk.Frame(root, bg="#F7F8FA", padx=10, pady=6)
            frame.pack(fill="both", expand=True)
            header = tk.Frame(frame, bg="#F7F8FA")
            header.pack(fill="x")
            badge = tk.Canvas(
                header, width=16, height=16, bg="#F7F8FA",
                highlightthickness=0, borderwidth=0,
            )
            badge.pack(side="left", padx=(0, 6))
            badge_circle = badge.create_oval(
                1, 1, 15, 15, fill="#D59B00", outline=""
            )
            badge.create_text(
                8, 8, text="S", fill="#FFFFFF",
                font=("Segoe UI Semibold", 7),
            )
            title = tk.Label(
                header, text="SOLetrando", font=("Segoe UI Semibold", 10),
                bg="#F7F8FA", fg="#111827", anchor="w", cursor="fleur",
            )
            title.pack(side="left", fill="x", expand=True)
            close_button = tk.Button(
                header, text="×", font=("Segoe UI", 10), bg="#F7F8FA",
                fg="#7C8491", activebackground="#F7F8FA",
                activeforeground="#111827", relief="flat", borderwidth=0,
                highlightthickness=0, padx=3, pady=0, takefocus=0,
            )
            close_button.pack(side="right")

            stop_button = tk.Button(
                header, text="Parar", font=("Segoe UI", 9), bg="#F7F8FA",
                fg="#334155", relief="flat", borderwidth=0, takefocus=0,
                command=lambda: self._stop_reading and self._stop_reading(),
            )
            stop_button.pack(side="right", padx=(0, 5))
            read_button = tk.Button(
                header, text="Ler", font=("Segoe UI Semibold", 9),
                bg="#F2BC2E", fg="#111827", activebackground="#D59B00",
                relief="flat", borderwidth=0, takefocus=0,
            )
            read_button.pack(side="right", padx=(0, 5))

            text_frame = tk.Frame(frame, bg="#F7F8FA")
            text_frame.pack(fill="both", expand=True, pady=(4, 0))
            detail = tk.Text(
                text_frame, font=("Segoe UI", 10), bg="#F7F8FA",
                fg="#1F2937", wrap="word", relief="flat", borderwidth=0,
                highlightthickness=0, padx=0, pady=0, cursor="arrow",
                width=1, height=1, takefocus=0,
            )
            scrollbar = tk.Scrollbar(
                text_frame, orient="vertical", command=detail.yview,
                width=12, relief="flat", borderwidth=0,
                background="#F2BC2E", activebackground="#D59B00",
                troughcolor="#D9DEE7", highlightthickness=0,
            )
            detail.configure(yscrollcommand=scrollbar.set)
            detail.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y", padx=(8, 0))
            detail.configure(state="disabled")

            def read_selected():
                selected = ""
                try:
                    selected = detail.get("sel.first", "sel.last")
                except tk.TclError:
                    pass
                if self._read_selection:
                    self._read_selection(selected)

            read_button.configure(command=read_selected)

            def scroll_detail(event):
                detail.yview_scroll(int(-event.delta / 120), "units")
                return "break"

            detail.bind("<MouseWheel>", scroll_detail)
            scrollbar.bind("<MouseWheel>", scroll_detail)

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

            compact_mode = False
            current_state = None
            labels = {
                "idle": "Pronto",
                "recording": "Gravando",
                "transcribing": "Transcrevendo",
                "done": "Texto pronto",
                "error": "Atenção necessária",
                "preview": "Prévia de tamanho",
                "reading": "Lendo seleção",
            }

            def update_title():
                status = labels.get(current_state, current_state or "Pronto")
                title.configure(
                    text=(status if compact_mode or self._width < 400
                          else f"SOLetrando  •  {status}")
                )

            def place_at_bottom_right(width, height):
                nonlocal compact_mode
                logical_width = max(80, round(width / dpi_scale))
                logical_height = max(28, round(height / dpi_scale))
                new_compact_mode = width < 220 or height < 76
                if new_compact_mode != compact_mode:
                    compact_mode = new_compact_mode
                    if compact_mode:
                        text_frame.pack_forget()
                        read_button.pack_forget()
                        stop_button.pack_forget()
                        frame.configure(padx=8, pady=5)
                    else:
                        text_frame.pack(
                            fill="both", expand=True, pady=(4, 0)
                        )
                        frame.configure(padx=10, pady=6)
                        stop_button.pack(side="right", padx=(0, 5))
                        read_button.pack(side="right", padx=(0, 5))
                    update_title()
                x = root.winfo_screenwidth() - logical_width - 16
                y = root.winfo_screenheight() - logical_height - 48
                root.geometry(
                    f"{logical_width}x{logical_height}+{max(0, x)}+{max(0, y)}"
                )

            place_at_bottom_right(self._width, self._height)
            hide_deadline = None
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
                        frame.configure(bg=background)
                        header.configure(bg=background)
                        badge.configure(bg=background)
                        badge.itemconfigure(badge_circle, fill=accent)
                        text_frame.configure(bg=background)
                        update_title()
                        title.configure(bg=background, fg=accent)
                        close_button.configure(
                            bg=background, activebackground=background
                        )
                        stop_button.configure(
                            bg=background, activebackground=background
                        )
                        detail.configure(bg=background)
                        set_text(message)
                        if state_changed or force_show:
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


def _find_asset(filename):
    """Localiza recursos no codigo-fonte e nas pastas geradas pelo PyInstaller."""
    import sys
    from pathlib import Path

    candidates = [Path(sys.executable).parent / filename]
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        candidates.append(Path(bundle_dir) / filename)
    candidates.append(Path(__file__).parent / filename)
    return next((path for path in candidates if path.exists()), None)


def _set_window_icon(root):
    """Aplica o icone oficial tanto no codigo-fonte quanto no executavel."""
    try:
        icon_path = _find_asset("soletrando.ico")
        if icon_path:
            root.iconbitmap(default=str(icon_path))
    except Exception:
        pass




def choices_with_current(options, current, custom_label="Personalizado"):
    """Lista (rotulo, valor) que sempre contem o valor atual.

    Um valor valido que nao esta na lista (ex.: idioma "fr" passado pela linha
    de comando) aparece como opcao extra em vez de ser trocado ao salvar.
    """
    options = list(options)
    if any(value == current for _label, value in options):
        return options
    return options + [(f"{custom_label} ({current})", current)]


AUTO_VOICE_LABEL = "Automática (primeira voz do idioma)"


def voice_choices(voices, language, current=""):
    """Opcoes (rotulo, nome) do seletor de voz para o idioma da leitura.

    voices=None significa lista ainda nao carregada: a voz salva continua
    selecionavel. Uma voz salva que nao esta mais instalada aparece marcada,
    para o usuario perceber em vez de a escolha sumir ao salvar.
    """
    from soletrando_speech import is_online_voice, voices_for_language

    options = [(AUTO_VOICE_LABEL, "")]
    names = set()
    for voice in voices_for_language(voices or [], language):
        name = voice["name"]
        names.add(name)
        label = f"{name} (online)" if is_online_voice(name) else name
        options.append((label, name))
    if current and current not in names:
        suffix = "" if voices is None else " (não encontrada)"
        options.append((f"{current}{suffix}", current))
    return options


def validate_settings(values):
    """Devolve (aba, mensagem) com o primeiro problema, ou None."""
    read_key = values.get("hotkey_read", "")
    if read_key and read_key == values.get("hotkey_toggle"):
        return (
            "reading",
            "A tecla de leitura não pode ser a mesma tecla de gravar.",
        )
    if read_key and read_key == values.get("hotkey_quit"):
        return (
            "reading",
            "A tecla de leitura não pode ser a mesma tecla de encerrar.",
        )
    width = values.get("overlay_width")
    height = values.get("overlay_height")
    if not isinstance(width, int) or not 120 <= width <= 1000:
        return ("overlay", "Use largura entre 120 e 1000 pixels.")
    if not isinstance(height, int) or not 44 <= height <= 600:
        return ("overlay", "Use altura entre 44 e 600 pixels.")
    return None


PRIVACY_TEXT = (
    "O QUE FICA GUARDADO NESTE COMPUTADOR\n"
    "Tudo fica na pasta de dados do SOLetrando (botão abaixo).\n\n"
    "•  Configuração: preferências, vocabulário e correções. É necessária "
    "para o aplicativo funcionar.\n"
    "•  Último ditado: sempre guardado, para o comando Copiar último ditado.\n"
    "•  Histórico de ditados: somente com a opção acima marcada. Ao passar "
    "de 2 MB, a versão anterior é mantida como cópia (.1).\n"
    "•  Registro técnico: eventos, tempos e erros, para diagnóstico. Não "
    "inclui vocabulário nem correções; o texto ditado só entra se a opção "
    "acima estiver marcada. Guarda até cerca de 1 MB e uma cópia anterior.\n"
    "•  Modelos de reconhecimento: baixados uma vez e reutilizados.\n\n"
    "O QUE PODE SAIR DO COMPUTADOR\n"
    "•  O SOLetrando não envia áudio nem texto pela internet. A rede é usada "
    "para baixar o modelo de reconhecimento na primeira vez.\n"
    "•  O texto ditado passa pela área de transferência para ser colado. "
    "Com a opção acima, o Windows é instruído a não guardá-lo no histórico "
    "(Win+V) nem sincronizá-lo; outros programas que monitoram a área de "
    "transferência ainda podem lê-lo.\n"
    "•  O programa que recebe o texto segue as próprias regras de "
    "armazenamento e envio.\n"
    "•  Arquivos compartilhados manualmente (por exemplo, o registro técnico "
    "enviado para suporte) levam o que contêm. Revise antes de enviar."
)

GUIDE_TEXT = (
    "DITAR\n"
    "1. Coloque o cursor no campo que receberá o texto.\n"
    "2. Pressione a tecla de gravar (padrão: Scroll Lock).\n"
    "3. Fale normalmente e acompanhe a prévia na caixa flutuante.\n"
    "4. Pressione a mesma tecla para concluir. O texto é inserido no campo.\n\n"
    "LER UM TEXTO EM VOZ ALTA\n"
    "Selecione o texto em qualquer programa e pressione a tecla de leitura "
    "(padrão: Ctrl+Alt+A). Pressione de novo para parar. Também é possível "
    "selecionar um trecho na caixa flutuante e clicar em Ler. A voz é "
    "escolhida em Leitura > Voz; Automática usa a primeira voz do idioma.\n\n"
    "SE A SELEÇÃO NÃO FOR LIDA\n"
    "Alguns programas não informam a seleção ao Windows. Nesses casos o "
    "SOLetrando copia a seleção por um instante e restaura a área de "
    "transferência, mas só quando ela contém texto simples, para não perder "
    "imagens ou formatação copiadas antes.\n\n"
    "VOCABULÁRIO E CORREÇÕES\n"
    "Use o vocabulário para nomes próprios e siglas. Use as correções para "
    "erros recorrentes, por exemplo: pro clima = PROCLIM.\n\n"
    "ÍCONE DO SISTEMA\n"
    "O ícone do SOLetrando pode ficar escondido na seta da bandeja, ao lado "
    "do relógio. Arraste-o uma vez para a área visível se quiser acesso "
    "rápido. O microfone que aparece ao gravar pertence ao Windows.\n\n"
    "EM CASO DE FALHA\n"
    "Abra o registro técnico nesta aba. Ele mostra se o atalho foi aceito, "
    "qual modelo foi carregado e quanto tempo cada etapa levou."
)


def show_settings_window(config, on_save, model_options=None, actions=None,
                         about=None):
    """Abre as configuracoes, a ajuda e as ferramentas do aplicativo."""
    global _settings_open
    with _settings_lock:
        if _settings_open:
            return False
        _settings_open = True

    from soletrando_config import (
        DEFAULT_CONFIG, HOTKEY_OPTIONS, INSERT_MODE_OPTIONS, LANGUAGE_OPTIONS,
        QUIT_KEY_OPTIONS, READ_KEY_OPTIONS, SPEECH_LANGUAGE_OPTIONS,
        SPEECH_RATE_OPTIONS,
    )

    model_options = list(model_options or [])
    actions = dict(actions or {})
    about = dict(about or {})
    snapshot = {key: config.get(key, value) for key, value in DEFAULT_CONFIG.items()}
    snapshot["vocabulary"] = list(snapshot["vocabulary"])
    snapshot["corrections"] = dict(snapshot["corrections"])
    snapshot["speech_voices"] = dict(snapshot["speech_voices"])

    def run():
        global _settings_open
        try:
            import tkinter as tk
            from tkinter import messagebox, scrolledtext, ttk
            from soletrando_text import parse_corrections

            root = tk.Tk()
            root.title("Configurações do SOLetrando")
            root.geometry("780x660")
            root.minsize(660, 520)
            _set_window_icon(root)

            background = "#F5F6F8"
            surface = "#FFFFFF"
            ink = "#111827"
            muted = "#667085"
            amber = "#F2BC2E"
            amber_dark = "#D59B00"
            root.configure(bg=background)

            style = ttk.Style(root)
            try:
                style.theme_use("clam")
            except tk.TclError:
                pass
            style.configure("TFrame", background=surface)
            style.configure("TLabel", background=surface, foreground=ink)
            style.configure("Muted.TLabel", background=surface, foreground=muted)
            style.configure(
                "Section.TLabel", background=surface, foreground=ink,
                font=("Segoe UI Semibold", 11),
            )
            style.configure(
                "TCheckbutton", background=surface, foreground=ink
            )
            style.map(
                "TCheckbutton", background=[("active", surface)]
            )
            style.configure("TNotebook", background=background, borderwidth=0)
            style.configure(
                "TNotebook.Tab", padding=(14, 7), background="#E7EAF0",
                foreground="#344054",
            )
            style.map(
                "TNotebook.Tab",
                background=[("selected", amber)],
                foreground=[("selected", ink)],
            )
            style.configure(
                "Accent.TButton", background=amber, foreground=ink,
                padding=(16, 7), borderwidth=0,
            )
            style.map(
                "Accent.TButton", background=[("active", amber_dark)]
            )

            tk.Frame(root, bg=amber, height=5).pack(fill="x")
            shell = tk.Frame(root, bg=background)
            shell.pack(fill="both", expand=True)
            settings_canvas = tk.Canvas(
                shell, bg=background, highlightthickness=0, borderwidth=0
            )
            settings_scrollbar = ttk.Scrollbar(
                shell, orient="vertical", command=settings_canvas.yview,
            )
            settings_canvas.configure(yscrollcommand=settings_scrollbar.set)
            settings_scrollbar.pack(side="right", fill="y")
            settings_canvas.pack(side="left", fill="both", expand=True)

            container = tk.Frame(
                settings_canvas, bg=background, padx=24, pady=16
            )
            container_window = settings_canvas.create_window(
                (0, 0), window=container, anchor="nw"
            )

            def update_scroll_region(_event=None):
                settings_canvas.configure(scrollregion=settings_canvas.bbox("all"))

            def fit_container_width(event):
                settings_canvas.itemconfigure(container_window, width=event.width)

            container.bind("<Configure>", update_scroll_region)
            settings_canvas.bind("<Configure>", fit_container_width)

            def scroll_settings(event):
                if event.widget.winfo_class() in {"Text", "TCombobox", "TSpinbox"}:
                    return None
                settings_canvas.yview_scroll(int(-event.delta / 120), "units")
                return "break"

            root.bind("<MouseWheel>", scroll_settings)

            brand = tk.Frame(container, bg=background)
            brand.pack(fill="x", pady=(0, 12))
            try:
                from PIL import Image, ImageTk

                icon_path = _find_asset("icon_idle.png")
                if icon_path:
                    icon_image = Image.open(icon_path).convert("RGBA")
                    icon_image = icon_image.resize((46, 46), Image.Resampling.LANCZOS)
                    root._soletrando_header_icon = ImageTk.PhotoImage(icon_image)
                    tk.Label(
                        brand, image=root._soletrando_header_icon,
                        bg=background, borderwidth=0,
                    ).pack(side="left", padx=(0, 12))
            except Exception:
                pass
            brand_text = tk.Frame(brand, bg=background)
            brand_text.pack(side="left", fill="x", expand=True)
            tk.Label(
                brand_text, text="SOLetrando", font=("Segoe UI Semibold", 19),
                bg=background, fg=ink, anchor="w",
            ).pack(fill="x")
            subtitle_parts = ["Ditado e leitura por voz, no seu computador"]
            if about.get("version"):
                subtitle_parts.append(f"versão {about['version']}")
            tk.Label(
                brand_text, text="  •  ".join(subtitle_parts),
                font=("Segoe UI", 10), bg=background, fg=muted, anchor="w",
            ).pack(fill="x", pady=(2, 0))
            if about.get("engine"):
                chip = tk.Label(
                    brand, text=about["engine"], font=("Segoe UI", 9),
                    bg="#E7EAF0", fg="#344054", padx=10, pady=3,
                )
                chip.pack(side="right", anchor="n")

            notebook = ttk.Notebook(container)
            notebook.pack(fill="both", expand=True)
            tabs = {}
            for key, label in (
                ("dictation", "Ditado"),
                ("reading", "Leitura"),
                ("vocabulary", "Vocabulário"),
                ("overlay", "Caixa flutuante"),
                ("privacy", "Privacidade"),
                ("help", "Ajuda"),
            ):
                frame = ttk.Frame(notebook, padding=18)
                notebook.add(frame, text=label)
                frame.columnconfigure(1, weight=1)
                tabs[key] = frame

            wrap = 620

            def section(tab, text, row, top=0):
                ttk.Label(tab, text=text, style="Section.TLabel").grid(
                    row=row, column=0, columnspan=2, sticky="w", pady=(top, 6)
                )

            def hint(tab, text, row, top=0, bottom=10):
                ttk.Label(
                    tab, text=text, style="Muted.TLabel", wraplength=wrap,
                    justify="left",
                ).grid(
                    row=row, column=0, columnspan=2, sticky="w",
                    pady=(top, bottom),
                )

            def separator(tab, row):
                ttk.Separator(tab).grid(
                    row=row, column=0, columnspan=2, sticky="ew", pady=(6, 14)
                )

            def choice(tab, row, text, options, current, width=30,
                       custom_label="Personalizado", on_change=None):
                options = choices_with_current(options, current, custom_label)
                labels = [label for label, _value in options]
                by_label = dict(options)
                current_label = next(
                    label for label, value in options if value == current
                )
                variable = tk.StringVar(value=current_label)
                ttk.Label(tab, text=text).grid(
                    row=row, column=0, sticky="w", pady=4, padx=(0, 16)
                )
                box = ttk.Combobox(
                    tab, textvariable=variable, state="readonly",
                    values=labels, width=width,
                )
                box.grid(row=row, column=1, sticky="w", pady=4)
                if on_change:
                    box.bind("<<ComboboxSelected>>", lambda _event: on_change())
                return lambda: by_label.get(variable.get(), current)

            # ---------------- Ditado ----------------
            tab = tabs["dictation"]
            section(tab, "Reconhecimento", 0)
            get_model = choice(
                tab, 1, "Modelo de transcrição",
                model_options or [(snapshot["model"], snapshot["model"])],
                snapshot["model"], width=34,
            )
            hint(
                tab,
                "O turbo costuma ser o equilíbrio entre velocidade e precisão. "
                "A troca é aplicada ao salvar e pode levar alguns segundos; um "
                "modelo novo é baixado na primeira vez.",
                2, top=2,
            )
            get_language = choice(
                tab, 3, "Idioma do ditado", LANGUAGE_OPTIONS,
                snapshot["language"], custom_label="Outro",
            )
            separator(tab, 4)
            section(tab, "Atalhos e inserção", 5)
            get_toggle = choice(
                tab, 6, "Tecla de gravar e concluir", HOTKEY_OPTIONS,
                snapshot["hotkey_toggle"],
            )
            get_quit = choice(
                tab, 7, "Tecla de encerrar o aplicativo", QUIT_KEY_OPTIONS,
                snapshot["hotkey_quit"],
            )
            get_insert = choice(
                tab, 8, "Como inserir o texto", INSERT_MODE_OPTIONS,
                snapshot["insert_mode"],
            )
            hint(
                tab,
                "Colar é instantâneo. Digitar é mais lento, mas funciona em "
                "terminais e campos que bloqueiam a colagem.",
                9, top=2,
            )
            preview_var = tk.BooleanVar(value=snapshot["live_preview_enabled"])
            beep_var = tk.BooleanVar(value=snapshot["beep_enabled"])
            ttk.Checkbutton(
                tab, text="Mostrar prévia do texto durante o ditado",
                variable=preview_var,
            ).grid(row=10, column=0, columnspan=2, sticky="w", pady=2)
            ttk.Checkbutton(
                tab, text="Tocar um bip ao iniciar e ao concluir",
                variable=beep_var,
            ).grid(row=11, column=0, columnspan=2, sticky="w", pady=2)

            # ---------------- Leitura ----------------
            tab = tabs["reading"]
            section(tab, "Ler o texto selecionado", 0)
            hint(
                tab,
                "Selecione um texto em qualquer programa e pressione a tecla "
                "de leitura. Pressione de novo para parar. As vozes são as "
                "instaladas no Windows; as locais funcionam sem internet.",
                1, top=0,
            )
            get_read_key = choice(
                tab, 2, "Tecla de leitura", READ_KEY_OPTIONS,
                snapshot["hotkey_read"],
            )
            # Voz escolhida por idioma. A lista vem do Windows numa thread
            # separada (pode levar alguns segundos) e so e aplicada na thread
            # da janela, pelo after().
            voice_state = {
                "voices": None,
                "language": snapshot["speech_language"],
                "chosen": dict(snapshot["speech_voices"]),
                "options": {},
                "loading": False,
            }
            voice_var = tk.StringVar()
            voice_status_var = tk.StringVar()

            def remember_voice():
                value = voice_state["options"].get(voice_var.get())
                if value is None:
                    return
                if value:
                    voice_state["chosen"][voice_state["language"]] = value
                else:
                    voice_state["chosen"].pop(voice_state["language"], None)

            def fill_voices():
                language = voice_state["language"]
                voices = voice_state["voices"]
                current = voice_state["chosen"].get(language, "")
                options = voice_choices(voices, language, current)
                voice_state["options"] = dict(options)
                voice_box.configure(values=[label for label, _ in options])
                voice_var.set(
                    next(label for label, value in options if value == current)
                )
                if voices is None:
                    voice_status_var.set("Procurando as vozes instaladas...")
                    return
                installed = {voice["name"] for voice in voices}
                found = sum(1 for _label, value in options if value in installed)
                if not found:
                    message = "Nenhuma voz instalada para este idioma."
                elif found == 1:
                    message = "1 voz instalada para este idioma."
                else:
                    message = f"{found} vozes instaladas para este idioma."
                if any(label.endswith("(online)") for label, _ in options):
                    message += (
                        " Vozes online precisam de internet e enviam o texto "
                        "para fora do computador."
                    )
                voice_status_var.set(message)

            def language_changed():
                remember_voice()
                voice_state["language"] = get_speech_language()
                fill_voices()

            get_speech_language = choice(
                tab, 3, "Idioma da voz", SPEECH_LANGUAGE_OPTIONS,
                snapshot["speech_language"], on_change=language_changed,
            )
            ttk.Label(tab, text="Voz").grid(
                row=4, column=0, sticky="w", pady=4, padx=(0, 16)
            )
            voice_box = ttk.Combobox(
                tab, textvariable=voice_var, state="readonly", width=48,
            )
            voice_box.grid(row=4, column=1, sticky="w", pady=4)
            voice_box.bind(
                "<<ComboboxSelected>>", lambda _event: remember_voice()
            )

            def load_voices():
                list_voices = actions.get("list_voices")
                if not list_voices or voice_state["loading"]:
                    return
                voice_state["loading"] = True
                refresh_button.state(["disabled"])
                remember_voice()
                voice_state["voices"] = None
                fill_voices()
                result = queue.Queue()

                def worker():
                    try:
                        result.put(list(list_voices() or []))
                    except Exception:
                        result.put([])

                def check():
                    try:
                        voices = result.get_nowait()
                    except queue.Empty:
                        root.after(150, check)
                        return
                    voice_state["voices"] = voices
                    voice_state["loading"] = False
                    refresh_button.state(["!disabled"])
                    fill_voices()

                threading.Thread(
                    target=worker, name="soletrando-vozes", daemon=True
                ).start()
                root.after(150, check)

            ttk.Label(
                tab, textvariable=voice_status_var, style="Muted.TLabel",
                wraplength=wrap - 170, justify="left",
            ).grid(row=5, column=1, sticky="w", pady=(0, 6))

            def get_speech_voices():
                remember_voice()
                return dict(voice_state["chosen"])

            def get_voice():
                return voice_state["options"].get(voice_var.get(), "")

            get_speech_rate = choice(
                tab, 6, "Velocidade da voz", SPEECH_RATE_OPTIONS,
                snapshot["speech_rate"],
            )

            def test_voice():
                callback = actions.get("test_voice")
                if callback:
                    callback(get_speech_language(), get_speech_rate(), get_voice())

            voice_buttons = ttk.Frame(tab)
            voice_buttons.grid(row=7, column=1, sticky="w", pady=(8, 4))
            test_button = ttk.Button(
                voice_buttons, text="Ouvir exemplo", command=test_voice
            )
            test_button.pack(side="left")
            refresh_button = ttk.Button(
                voice_buttons, text="Atualizar lista", command=load_voices
            )
            refresh_button.pack(side="left", padx=(8, 0))
            if "test_voice" not in actions:
                test_button.state(["disabled"])
            hint(
                tab,
                "Sem voz no idioma escolhido? Instale em Configurações do "
                "Windows > Hora e idioma > Fala > Adicionar vozes e clique em "
                "Atualizar lista. A lista mostra as vozes SAPI 5, as mesmas "
                "de Painel de Controle > Fala.",
                8, top=10,
            )
            fill_voices()
            if "list_voices" in actions:
                load_voices()
            else:
                refresh_button.state(["disabled"])
                voice_status_var.set("")

            # ---------------- Vocabulário ----------------
            tab = tabs["vocabulary"]
            tab.rowconfigure(2, weight=1)
            tab.rowconfigure(5, weight=1)
            section(tab, "Vocabulário preferencial", 0)
            hint(
                tab,
                "Um termo por linha. Exemplo: EnvironPact, PROCLIM, Camarupim.",
                1, bottom=5,
            )
            vocabulary = scrolledtext.ScrolledText(
                tab, height=7, font=("Segoe UI", 10), wrap="word",
                relief="solid", borderwidth=1,
            )
            vocabulary.grid(row=2, column=0, columnspan=2, sticky="nsew")
            vocabulary.insert("1.0", "\n".join(snapshot["vocabulary"]))
            section(tab, "Correções automáticas", 3, top=14)
            hint(
                tab, "Uma por linha: texto ouvido = texto correto.", 4, bottom=5
            )
            corrections = scrolledtext.ScrolledText(
                tab, height=7, font=("Segoe UI", 10), wrap="word",
                relief="solid", borderwidth=1,
            )
            corrections.grid(row=5, column=0, columnspan=2, sticky="nsew")
            corrections.insert(
                "1.0",
                "\n".join(
                    f"{source} = {target}"
                    for source, target in snapshot["corrections"].items()
                ),
            )

            # ---------------- Caixa flutuante ----------------
            tab = tabs["overlay"]
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
            section(tab, "Tamanho", 0)
            ttk.Label(tab, text="Largura em pixels").grid(
                row=1, column=0, sticky="w", pady=4, padx=(0, 16)
            )
            ttk.Spinbox(
                tab, from_=120, to=1000, increment=20,
                textvariable=width_var, width=12,
            ).grid(row=1, column=1, sticky="w", pady=4)
            ttk.Label(tab, text="Altura em pixels").grid(
                row=2, column=0, sticky="w", pady=4, padx=(0, 16)
            )
            ttk.Spinbox(
                tab, from_=44, to=600, increment=8,
                textvariable=height_var, width=12,
            ).grid(row=2, column=1, sticky="w", pady=4)
            hint(
                tab,
                "Faixas permitidas: 120 a 1000 px de largura e 44 a 600 px de "
                "altura. Abaixo de 220 × 76 px, a caixa mostra apenas o estado. "
                "A caixa no canto da tela acompanha as mudanças para você ver o "
                "resultado antes de salvar.",
                3, top=4,
            )
            separator(tab, 4)
            section(tab, "Quando ocultar", 5)
            ttk.Label(tab, text="Durante a gravação").grid(
                row=6, column=0, sticky="w", pady=4, padx=(0, 16)
            )
            ttk.Combobox(
                tab, textvariable=recording_time_var, state="readonly",
                values=list(recording_options), width=26,
            ).grid(row=6, column=1, sticky="w", pady=4)
            ttk.Label(tab, text="Depois de concluir").grid(
                row=7, column=0, sticky="w", pady=4, padx=(0, 16)
            )
            ttk.Combobox(
                tab, textvariable=done_time_var, state="readonly",
                values=list(done_options), width=26,
            ).grid(row=7, column=1, sticky="w", pady=4)

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
                    if 120 <= width <= 1000 and 44 <= height <= 600:
                        callback = actions.get("preview_overlay")
                        if callback:
                            callback(width, height)

                preview_job = root.after(120, apply_preview)

            width_var.trace_add("write", refresh_size_preview)
            height_var.trace_add("write", refresh_size_preview)

            def on_tab_changed(_event=None):
                # A previa de tamanho so aparece na aba correspondente, para
                # nao cobrir a tela enquanto o usuario ajusta outras opcoes.
                if notebook.select() == str(tabs["overlay"]):
                    refresh_size_preview()

            notebook.bind("<<NotebookTabChanged>>", on_tab_changed)

            # ---------------- Privacidade ----------------
            tab = tabs["privacy"]
            history_var = tk.BooleanVar(value=snapshot["save_history"])
            log_var = tk.BooleanVar(value=snapshot["log_transcripts"])
            clipboard_var = tk.BooleanVar(value=snapshot["clipboard_private"])
            section(tab, "Opções", 0)
            ttk.Checkbutton(
                tab, text="Guardar histórico local dos ditados",
                variable=history_var,
            ).grid(row=1, column=0, columnspan=2, sticky="w", pady=2)
            ttk.Checkbutton(
                tab, text="Incluir o texto ditado no registro técnico "
                          "(use só para diagnosticar um problema)",
                variable=log_var,
            ).grid(row=2, column=0, columnspan=2, sticky="w", pady=2)
            ttk.Checkbutton(
                tab, text="Não guardar os ditados no histórico da área de "
                          "transferência do Windows (Win+V)",
                variable=clipboard_var,
            ).grid(row=3, column=0, columnspan=2, sticky="w", pady=2)
            separator(tab, 4)

            privacy_text = scrolledtext.ScrolledText(
                tab, font=("Segoe UI", 10), wrap="word", relief="flat",
                background=surface, foreground=ink, height=11, padx=2,
                pady=2, borderwidth=0, highlightthickness=0, cursor="arrow",
            )
            privacy_text.grid(row=5, column=0, columnspan=2, sticky="nsew")
            privacy_text.insert("1.0", PRIVACY_TEXT)
            privacy_text.configure(state="disabled")
            tab.rowconfigure(5, weight=1)

            privacy_buttons = ttk.Frame(tab)
            privacy_buttons.grid(
                row=6, column=0, columnspan=2, sticky="ew", pady=(10, 0)
            )

            def run_file_action(action_name, question):
                callback = actions.get(action_name)
                if callback is None:
                    return
                if question and not messagebox.askyesno(
                    "Confirmar", question, parent=root
                ):
                    return
                result = callback()
                if isinstance(result, str) and result:
                    messagebox.showinfo("SOLetrando", result, parent=root)

            def small_button(parent, label, action_name, question=None):
                button = ttk.Button(
                    parent, text=label,
                    command=lambda: run_file_action(action_name, question),
                )
                button.pack(side="left", padx=(0, 8))
                if action_name not in actions:
                    button.state(["disabled"])

            small_button(privacy_buttons, "Abrir pasta de dados", "open_folder")
            small_button(privacy_buttons, "Abrir histórico", "open_history")
            small_button(
                privacy_buttons, "Apagar histórico...", "clear_history",
                "Apagar o histórico de ditados e o último ditado salvo? "
                "Esta ação não pode ser desfeita.",
            )
            small_button(
                privacy_buttons, "Apagar registro técnico...", "clear_log",
                "Apagar o registro técnico e sua cópia anterior? "
                "Esta ação não pode ser desfeita.",
            )

            # ---------------- Ajuda ----------------
            tab = tabs["help"]
            tab.rowconfigure(0, weight=1)
            guide_text = scrolledtext.ScrolledText(
                tab, font=("Segoe UI", 10), wrap="word", relief="flat",
                background=surface, foreground=ink, padx=8, pady=6, height=14,
            )
            guide_text.grid(row=0, column=0, columnspan=2, sticky="nsew")
            guide_text.insert("1.0", GUIDE_TEXT)
            guide_text.configure(state="disabled")
            support = ttk.Frame(tab)
            support.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
            small_button(support, "Abrir registro técnico", "open_log")
            small_button(support, "Desinstalar...", "uninstall")
            details = []
            if about.get("version"):
                details.append(f"Versão {about['version']}")
            if about.get("engine"):
                details.append(about["engine"])
            if about.get("data_dir"):
                details.append(f"Dados em {about['data_dir']}")
            if details:
                hint(tab, "  •  ".join(details), 2, top=10, bottom=0)

            buttons = tk.Frame(container, bg=background)
            buttons.pack(fill="x", pady=(14, 0))

            def cancel():
                callback = actions.get("cancel_overlay_preview")
                if callback:
                    callback()
                root.destroy()

            def save():
                try:
                    parsed = parse_corrections(corrections.get("1.0", "end"))
                except ValueError as error:
                    notebook.select(tabs["vocabulary"])
                    messagebox.showerror(
                        "Configuração inválida", str(error), parent=root
                    )
                    return
                try:
                    width = int(width_var.get())
                    height = int(height_var.get())
                except ValueError:
                    width = height = None
                values = {
                    "model": get_model(),
                    "language": get_language(),
                    "hotkey_toggle": get_toggle(),
                    "hotkey_quit": get_quit(),
                    "hotkey_read": get_read_key(),
                    "insert_mode": get_insert(),
                    "beep_enabled": beep_var.get(),
                    "live_preview_enabled": preview_var.get(),
                    "speech_language": get_speech_language(),
                    "speech_voices": get_speech_voices(),
                    "speech_rate": get_speech_rate(),
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
                    "save_history": history_var.get(),
                    "log_transcripts": log_var.get(),
                    "clipboard_private": clipboard_var.get(),
                }
                problem = validate_settings(values)
                if problem:
                    tab_key, message = problem
                    notebook.select(tabs[tab_key])
                    messagebox.showerror(
                        "Configuração inválida", message, parent=root
                    )
                    return
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
