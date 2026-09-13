"""Funcoes de vocabulario e correcoes do SOLetrando."""

import re


def normalize_vocabulary(items):
    """Remove vazios e duplicatas, preservando a ordem informada."""
    if not isinstance(items, list):
        return []
    result = []
    seen = set()
    for item in items:
        term = str(item).strip()
        key = term.casefold()
        if term and key not in seen:
            seen.add(key)
            result.append(term)
    return result


def normalize_corrections(corrections):
    """Aceita somente pares de texto nao vazios."""
    if not isinstance(corrections, dict):
        return {}
    result = {}
    for source, target in corrections.items():
        source = str(source).strip()
        target = str(target).strip()
        if source and target:
            result[source] = target
    return result


def parse_corrections(value):
    """Converte linhas no formato ouvido = correto em um dicionario."""
    result = {}
    for line_number, raw_line in enumerate(str(value).splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        separator = "=>" if "=>" in line else "="
        if separator not in line:
            raise ValueError(
                f"Linha {line_number}: use o formato ouvido = correto"
            )
        source, target = (part.strip() for part in line.split(separator, 1))
        if not source or not target:
            raise ValueError(
                f"Linha {line_number}: os dois lados precisam ter texto"
            )
        result[source] = target
    return result


def apply_corrections(text, corrections):
    """Aplica correcoes literais, sem trocar trechos dentro de palavras."""
    result = str(text)
    ordered = sorted(
        normalize_corrections(corrections).items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for source, target in ordered:
        pattern = re.compile(
            rf"(?<!\w){re.escape(source)}(?!\w)",
            flags=re.IGNORECASE,
        )
        result = pattern.sub(lambda _match, replacement=target: replacement, result)
    return result


def build_initial_prompt(vocabulary):
    """Cria um contexto curto para favorecer termos conhecidos pelo Whisper."""
    terms = normalize_vocabulary(vocabulary)
    if not terms:
        return None
    return "Vocabulário preferencial em português brasileiro: " + ", ".join(terms)
