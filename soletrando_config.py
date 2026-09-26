"""Opcoes, valores padrao e validacao da configuracao do SOLetrando.

Fica separado do nucleo para poder ser testado sem abrir microfone, carregar
o modelo ou criar janelas.
"""

import re

from soletrando_text import normalize_corrections, normalize_vocabulary


DEFAULT_CONFIG = {
    "hotkey_toggle": "scroll lock",
    "hotkey_quit": "ctrl+shift+q",
    # Atalho global para ler em voz alta o texto selecionado. "" desativa.
    "hotkey_read": "ctrl+alt+l",
    # large-v3-turbo: 809M params (praticamente o tamanho do medium) com
    # precisao de classe "large" e varias vezes mais rapido. Torna o medium
    # obsoleto em qualidade e velocidade.
    "model": "large-v3-turbo",
    "language": "pt",
    "speech_language": "pt",
    # Velocidade da voz do Windows: -10 (lenta) a 10 (rapida); 0 = normal.
    "speech_rate": 0,
    "beep_enabled": False,
    # "paste" = Ctrl+V (instantaneo, unicode perfeito)
    # "type"  = simula digitacao tecla a tecla (compativel com terminais)
    "insert_mode": "paste",
    # Termos que ajudam o modelo e substituicoes aplicadas ao resultado final.
    "vocabulary": [],
    "corrections": {},
    # A previa fica somente na janela flutuante. O campo de destino recebe o
    # texto final uma unica vez, evitando duplicacoes durante o reconhecimento.
    "live_preview_enabled": True,
    "overlay_width": 320,
    "overlay_height": 110,
    # 0 = fica visivel durante toda a gravacao.
    "overlay_recording_seconds": 0.0,
    # -1 = permanece aberta; 0 = fecha imediatamente.
    "overlay_done_seconds": 1.0,
    "save_history": True,
    # Texto integral pode conter informacao sensivel; o registro tecnico guarda
    # apenas tamanho e desempenho por padrao.
    "log_transcripts": False,
    # Pede ao Windows para nao guardar o ditado no historico da area de
    # transferencia (Win+V) nem sincroniza-lo com outros dispositivos.
    "clipboard_private": True,
}

# Opcoes de hotkey disponiveis no menu
HOTKEY_OPTIONS = [
    ("ScrollLock", "scroll lock"),
    ("F8", "f8"),
    ("F9", "f9"),
    ("F10", "f10"),
    ("Pause", "pause"),
    ("Ctrl+Shift+F", "ctrl+shift+f"),
    ("Ctrl+Shift+R", "ctrl+shift+r"),
    ("Ctrl+Alt+Space", "ctrl+alt+space"),
]

READ_KEY_OPTIONS = [
    ("Desativado", ""),
    ("Ctrl+Alt+L", "ctrl+alt+l"),
    ("Ctrl+Alt+R", "ctrl+alt+r"),
    ("Ctrl+Shift+L", "ctrl+shift+l"),
    ("F7", "f7"),
    ("Pause", "pause"),
]

MODEL_OPTIONS = [
    ("tiny (mais rapido)", "tiny"),
    ("base", "base"),
    ("small", "small"),
    ("medium", "medium"),
    ("large-v3-turbo (recomendado)", "large-v3-turbo"),
    ("large-v3 (maxima precisao)", "large-v3"),
]

LANGUAGE_OPTIONS = [
    ("Portugues", "pt"),
    ("Ingles", "en"),
    ("Espanhol", "es"),
    ("Deteccao automatica", ""),
]

SPEECH_LANGUAGE_OPTIONS = [
    ("Português (Brasil)", "pt"),
    ("Inglês", "en"),
    ("Espanhol", "es"),
]

SPEECH_RATE_OPTIONS = [
    ("Bem devagar", -4),
    ("Devagar", -2),
    ("Normal", 0),
    ("Rápida", 2),
    ("Bem rápida", 4),
    ("Muito rápida", 6),
]

QUIT_KEY_OPTIONS = [
    ("Ctrl+Shift+Q", "ctrl+shift+q"),
    ("Ctrl+Alt+Q", "ctrl+alt+q"),
    ("Ctrl+Shift+E", "ctrl+shift+e"),
]

INSERT_MODE_OPTIONS = [
    ("Colar (rapido)", "paste"),
    ("Digitar (compativel)", "type"),
]

VALID_HOTKEY_TOGGLE_KEYS = {key for _, key in HOTKEY_OPTIONS}
VALID_HOTKEY_QUIT_KEYS = {key for _, key in QUIT_KEY_OPTIONS}
VALID_HOTKEY_READ_KEYS = {key for _, key in READ_KEY_OPTIONS}
VALID_MODEL_KEYS = {key for _, key in MODEL_OPTIONS}
VALID_INSERT_MODES = {key for _, key in INSERT_MODE_OPTIONS}
VALID_SPEECH_LANGUAGES = {key for _, key in SPEECH_LANGUAGE_OPTIONS}

# Campos que podem aparecer no registro tecnico. Vocabulario, correcoes e
# qualquer campo novo ficam de fora ate serem avaliados e incluidos aqui.
TECHNICAL_LOG_KEYS = (
    "model", "language", "speech_language", "speech_rate", "insert_mode",
    "hotkey_toggle", "hotkey_quit", "hotkey_read", "beep_enabled",
    "live_preview_enabled", "save_history", "log_transcripts",
    "clipboard_private", "overlay_width", "overlay_height",
    "overlay_recording_seconds", "overlay_done_seconds",
)


def is_valid_language(value):
    """Aceita "" (automatico) ou um codigo tipo pt, en, pt-br."""
    if value == "":
        return True
    return bool(re.fullmatch(r"[a-z]{2,3}(-[a-z]{2,4})?", str(value).lower()))


def sanitize_config(cfg):
    """Normaliza configuracao para evitar valores invalidos/corrompidos."""
    normalized = dict(DEFAULT_CONFIG)
    if isinstance(cfg, dict):
        normalized.update(cfg)
        # Migra apenas o tamanho padrao da versao anterior. Valores realmente
        # personalizados pelo usuario permanecem intactos.
        if (
            "overlay_done_seconds" not in cfg
            and cfg.get("overlay_width") == 560
            and cfg.get("overlay_height") == 180
        ):
            normalized["overlay_width"] = DEFAULT_CONFIG["overlay_width"]
            normalized["overlay_height"] = DEFAULT_CONFIG["overlay_height"]

    if normalized["hotkey_toggle"] not in VALID_HOTKEY_TOGGLE_KEYS:
        normalized["hotkey_toggle"] = DEFAULT_CONFIG["hotkey_toggle"]
    if normalized["hotkey_quit"] not in VALID_HOTKEY_QUIT_KEYS:
        normalized["hotkey_quit"] = DEFAULT_CONFIG["hotkey_quit"]
    if normalized.get("hotkey_read") not in VALID_HOTKEY_READ_KEYS:
        normalized["hotkey_read"] = DEFAULT_CONFIG["hotkey_read"]
    # A mesma tecla nao pode gravar e ler ao mesmo tempo. Em conflito, a
    # leitura e desativada em vez de trocar silenciosamente o atalho de gravar.
    if normalized["hotkey_read"] in {
        normalized["hotkey_toggle"], normalized["hotkey_quit"]
    }:
        normalized["hotkey_read"] = ""
    if normalized["model"] not in VALID_MODEL_KEYS:
        normalized["model"] = DEFAULT_CONFIG["model"]
    if not is_valid_language(normalized.get("language")):
        normalized["language"] = DEFAULT_CONFIG["language"]
    if normalized.get("speech_language") not in VALID_SPEECH_LANGUAGES:
        normalized["speech_language"] = DEFAULT_CONFIG["speech_language"]
    if not isinstance(normalized.get("beep_enabled"), bool):
        normalized["beep_enabled"] = DEFAULT_CONFIG["beep_enabled"]
    if normalized.get("insert_mode") not in VALID_INSERT_MODES:
        normalized["insert_mode"] = DEFAULT_CONFIG["insert_mode"]
    normalized["vocabulary"] = normalize_vocabulary(normalized.get("vocabulary"))
    normalized["corrections"] = normalize_corrections(normalized.get("corrections"))
    for key in (
        "live_preview_enabled", "save_history", "log_transcripts",
        "clipboard_private",
    ):
        if not isinstance(normalized.get(key), bool):
            normalized[key] = DEFAULT_CONFIG[key]
    rate = normalized.get("speech_rate")
    if isinstance(rate, bool) or not isinstance(rate, (int, float)):
        normalized["speech_rate"] = DEFAULT_CONFIG["speech_rate"]
    else:
        normalized["speech_rate"] = max(-10, min(10, int(rate)))
    for key, minimum, maximum in (
        ("overlay_width", 120, 1000),
        ("overlay_height", 44, 600),
    ):
        try:
            normalized[key] = max(minimum, min(maximum, int(normalized[key])))
        except (TypeError, ValueError):
            normalized[key] = DEFAULT_CONFIG[key]
    for key, minimum, maximum in (
        ("overlay_recording_seconds", 0.0, 60.0),
        ("overlay_done_seconds", -1.0, 60.0),
    ):
        try:
            normalized[key] = max(
                minimum, min(maximum, float(normalized[key]))
            )
        except (TypeError, ValueError):
            normalized[key] = DEFAULT_CONFIG[key]
    return normalized


def describe_config_for_log(cfg):
    """Resumo tecnico da configuracao, sem vocabulario nem correcoes.

    Os termos do vocabulario e as correcoes costumam conter nomes de pessoas,
    clientes e projetos. O registro tecnico recebe apenas a quantidade.
    """
    cfg = cfg if isinstance(cfg, dict) else {}
    parts = [f"{key}={cfg[key]!r}" for key in TECHNICAL_LOG_KEYS if key in cfg]
    vocabulary = cfg.get("vocabulary")
    corrections = cfg.get("corrections")
    parts.append(
        f"vocabulario={len(vocabulary) if isinstance(vocabulary, list) else 0} termo(s)"
    )
    parts.append(
        f"correcoes={len(corrections) if isinstance(corrections, dict) else 0} regra(s)"
    )
    return ", ".join(parts)
