"""Bancada de comparacao de modelos do SOLetrando.

Mede, com as mesmas amostras de voz, a taxa de erro de palavras (WER), a taxa
de erro de caracteres (CER), o tempo da transcricao final, o tempo de uma
atualizacao da previa e o pico de memoria de video.

Uso tipico no Windows, na pasta do codigo-fonte com o ambiente ativado:

    python tools\\benchmark_modelos.py gravar tools\\frases_exemplo_pt.txt amostras
    python tools\\benchmark_modelos.py medir amostras --modelos large-v3-turbo large-v3

Cada amostra e um arquivo de audio (.wav, .m4a, .mp3, .ogg ou .flac) com um
.txt de mesmo nome contendo o texto de referencia.

Os parametros de transcricao abaixo espelham soletrando.py
(stop_and_transcribe e _live_preview_loop). Ao muda-los la, atualize aqui.
"""

import argparse
import csv
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
import unicodedata
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from soletrando_text import apply_corrections, build_initial_prompt  # noqa: E402

SAMPLE_RATE = 16000
AUDIO_EXTENSIONS = {".wav", ".m4a", ".mp3", ".ogg", ".flac"}
LIVE_PREVIEW_MAX_SECONDS = 20
FINAL_OPTIONS = dict(
    beam_size=5,
    vad_filter=True,
    vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=200),
    condition_on_previous_text=False,
)
PREVIEW_OPTIONS = dict(
    beam_size=1,
    vad_filter=True,
    vad_parameters=dict(min_silence_duration_ms=400, speech_pad_ms=150),
    condition_on_previous_text=False,
)


# ---------------------------------------------------------------------
# Metricas (sem dependencias externas; testadas em tests/test_benchmark.py)
# ---------------------------------------------------------------------
def normalize_text(text):
    """Minusculas, sem pontuacao e com espacos simples. Acentos permanecem."""
    text = unicodedata.normalize("NFC", str(text)).casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    text = text.replace("_", " ")
    return " ".join(text.split())


def edit_distance(reference, hypothesis):
    """Distancia de Levenshtein entre duas sequencias."""
    previous = list(range(len(hypothesis) + 1))
    for i, ref_item in enumerate(reference, start=1):
        current = [i] + [0] * len(hypothesis)
        for j, hyp_item in enumerate(hypothesis, start=1):
            cost = 0 if ref_item == hyp_item else 1
            current[j] = min(
                previous[j] + 1,        # remocao
                current[j - 1] + 1,     # insercao
                previous[j - 1] + cost,  # substituicao
            )
        previous = current
    return previous[-1]


def error_counts(reference, hypothesis):
    """(erros_palavras, palavras_ref, erros_caracteres, caracteres_ref)."""
    ref = normalize_text(reference)
    hyp = normalize_text(hypothesis)
    ref_words, hyp_words = ref.split(), hyp.split()
    ref_chars, hyp_chars = list(ref.replace(" ", "")), list(hyp.replace(" ", ""))
    return (
        edit_distance(ref_words, hyp_words), len(ref_words),
        edit_distance(ref_chars, hyp_chars), len(ref_chars),
    )


def rate(errors, total):
    return errors / total if total else 0.0


def summarize(rows):
    """Agrupa as linhas por modelo. WER e CER sao ponderados pelo tamanho."""
    by_model = {}
    for row in rows:
        by_model.setdefault(row["modelo"], []).append(row)
    summary = []
    for model, items in by_model.items():
        word_errors = sum(item["erros_palavras"] for item in items)
        words = sum(item["palavras_ref"] for item in items)
        char_errors = sum(item["erros_caracteres"] for item in items)
        chars = sum(item["caracteres_ref"] for item in items)
        audio = sum(item["duracao_s"] for item in items)
        final = sum(item["tempo_final_s"] for item in items)
        vram = [item["vram_pico_mb"] for item in items if item["vram_pico_mb"] is not None]
        summary.append({
            "modelo": model,
            "amostras": len(items),
            "wer_pct": round(100 * rate(word_errors, words), 2),
            "cer_pct": round(100 * rate(char_errors, chars), 2),
            "tempo_final_medio_s": round(final / len(items), 3),
            "fator_tempo_real": round(final / audio, 3) if audio else None,
            "previa_media_s": round(
                statistics.mean(item["tempo_previa_s"] for item in items), 3
            ),
            "vram_pico_mb": max(vram) if vram else None,
            "carga_modelo_s": items[0]["carga_modelo_s"],
        })
    return summary


# ---------------------------------------------------------------------
# GPU
# ---------------------------------------------------------------------
def gpu_memory_used_mb():
    """Memoria de video em uso (MB) segundo o nvidia-smi, ou None."""
    executable = shutil.which("nvidia-smi")
    if not executable:
        return None
    try:
        result = subprocess.run(
            [executable, "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return int(result.stdout.strip().splitlines()[0])
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


class GpuPeakMonitor:
    """Amostra a memoria de video em segundo plano e guarda o pico."""

    def __init__(self, interval=0.2):
        self.interval = interval
        self.peak = None
        self._stop = threading.Event()
        self._thread = None

    def __enter__(self):
        self.peak = gpu_memory_used_mb()
        if self.peak is not None:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return self

    def _run(self):
        while not self._stop.wait(self.interval):
            value = gpu_memory_used_mb()
            if value is not None and (self.peak is None or value > self.peak):
                self.peak = value

    def __exit__(self, *_exc):
        self._stop.set()
        if self._thread:
            self._thread.join(2)


# ---------------------------------------------------------------------
# Amostras
# ---------------------------------------------------------------------
def find_samples(folder):
    samples = []
    for audio in sorted(Path(folder).iterdir()):
        if audio.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        reference = audio.with_suffix(".txt")
        if not reference.exists():
            print(f"[aviso] {audio.name} sem {reference.name}; ignorado")
            continue
        samples.append((audio, reference.read_text(encoding="utf-8").strip()))
    return samples


def load_user_config():
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return {}
    path = Path(base) / "Soletrando" / "soletrando_config.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def record_samples(phrases_file, output_folder):
    """Mostra cada frase, grava ate Enter e salva .wav + .txt."""
    import numpy as np
    import sounddevice as sd

    phrases = [
        line.strip() for line in Path(phrases_file).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    output = Path(output_folder)
    output.mkdir(parents=True, exist_ok=True)
    print(f"{len(phrases)} frase(s). Fale naturalmente, como no uso real.\n")
    for index, phrase in enumerate(phrases, start=1):
        name = output / f"amostra_{index:02d}"
        print(f"[{index}/{len(phrases)}] {phrase}")
        answer = input("  Enter para gravar, p para pular, s para sair: ").strip().lower()
        if answer == "s":
            break
        if answer == "p":
            continue
        frames = []
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                            callback=lambda data, *_: frames.append(data.copy())):
            input("  Gravando... Enter para parar.")
        audio = np.concatenate(frames).flatten() if frames else np.zeros(0, "float32")
        pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()
        with wave.open(str(name.with_suffix(".wav")), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(pcm)
        name.with_suffix(".txt").write_text(phrase + "\n", encoding="utf-8")
        print(f"  Salvo: {name.with_suffix('.wav').name} ({len(audio) / SAMPLE_RATE:.1f} s)\n")


# ---------------------------------------------------------------------
# Medicao
# ---------------------------------------------------------------------
def transcribe(model, audio, language, prompt, options):
    segments, _info = model.transcribe(
        audio, language=language or None, initial_prompt=prompt, **options
    )
    return " ".join(segment.text.strip() for segment in segments).strip()


def measure(args):
    from faster_whisper import WhisperModel, decode_audio

    samples = find_samples(args.pasta)
    if not samples:
        print("Nenhuma amostra encontrada (audio + .txt com o mesmo nome).")
        return 1

    vocabulary, corrections = [], {}
    if args.usar_config:
        user_config = load_user_config()
        vocabulary = user_config.get("vocabulary", [])
        corrections = user_config.get("corrections", {})
        print(f"Usando vocabulario ({len(vocabulary)}) e correcoes "
              f"({len(corrections)}) da configuracao local.")
    prompt = build_initial_prompt(vocabulary)

    audios = [(path, reference, decode_audio(str(path), sampling_rate=SAMPLE_RATE))
              for path, reference in samples]
    print(f"{len(audios)} amostra(s), "
          f"{sum(len(a) for _p, _r, a in audios) / SAMPLE_RATE:.0f} s de audio.\n")

    rows = []
    for model_name in args.modelos:
        print(f"== {model_name} ({args.device}/{args.compute_type}) ==")
        started = time.perf_counter()
        model = WhisperModel(model_name, device=args.device, compute_type=args.compute_type)
        load_seconds = time.perf_counter() - started
        # Aquecimento: a primeira chamada inclui inicializacoes da GPU.
        transcribe(model, audios[0][2], args.idioma, prompt, PREVIEW_OPTIONS)

        for path, reference, audio in audios:
            with GpuPeakMonitor() as monitor:
                started = time.perf_counter()
                window = audio[-SAMPLE_RATE * LIVE_PREVIEW_MAX_SECONDS:]
                transcribe(model, window, args.idioma, prompt, PREVIEW_OPTIONS)
                preview_seconds = time.perf_counter() - started

                started = time.perf_counter()
                text = transcribe(model, audio, args.idioma, prompt, FINAL_OPTIONS)
                final_seconds = time.perf_counter() - started
            text = apply_corrections(text, corrections) if corrections else text
            word_errors, words, char_errors, chars = error_counts(reference, text)
            row = {
                "modelo": model_name,
                "amostra": path.name,
                "duracao_s": round(len(audio) / SAMPLE_RATE, 2),
                "tempo_previa_s": round(preview_seconds, 3),
                "tempo_final_s": round(final_seconds, 3),
                "erros_palavras": word_errors,
                "palavras_ref": words,
                "wer_pct": round(100 * rate(word_errors, words), 2),
                "erros_caracteres": char_errors,
                "caracteres_ref": chars,
                "vram_pico_mb": monitor.peak,
                "carga_modelo_s": round(load_seconds, 2),
                "referencia": reference,
                "transcricao": text,
            }
            rows.append(row)
            print(f"  {path.name}: WER {row['wer_pct']:.1f}% | final "
                  f"{final_seconds:.2f} s | previa {preview_seconds:.2f} s")
        del model
        print()

    output = Path(args.saida)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print("Resumo (WER e CER ponderados pelo tamanho das amostras):")
    for item in summarize(rows):
        print(
            f"  {item['modelo']:<16} WER {item['wer_pct']:>6.2f}%  "
            f"CER {item['cer_pct']:>6.2f}%  final {item['tempo_final_medio_s']:.2f} s  "
            f"previa {item['previa_media_s']:.2f} s  "
            f"fator {item['fator_tempo_real']}  VRAM pico {item['vram_pico_mb'] or 'n/d'} MB"
        )
    print(f"\nDetalhes por amostra em: {output.resolve()}")
    print("Atencao: o CSV contem as transcricoes; nao compartilhe se as frases "
          "forem pessoais.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="comando", required=True)

    record = sub.add_parser("gravar", help="grava amostras a partir de frases")
    record.add_argument("frases", help="arquivo .txt com uma frase por linha")
    record.add_argument("pasta", help="pasta onde salvar as amostras")

    bench = sub.add_parser("medir", help="compara modelos nas amostras")
    bench.add_argument("pasta", help="pasta com audios e .txt de referencia")
    bench.add_argument("--modelos", nargs="+",
                       default=["large-v3-turbo", "large-v3"])
    bench.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    bench.add_argument("--compute-type", default=None,
                       help="padrao: float16 na GPU e int8 na CPU")
    bench.add_argument("--idioma", default="pt")
    bench.add_argument("--usar-config", action="store_true",
                       help="aplica vocabulario e correcoes do SOLetrando instalado")
    bench.add_argument("--saida", default="resultado_benchmark.csv")

    args = parser.parse_args(argv)
    if args.comando == "gravar":
        record_samples(args.frases, args.pasta)
        return 0
    if args.compute_type is None:
        args.compute_type = "float16" if args.device == "cuda" else "int8"
    return measure(args)


if __name__ == "__main__":
    sys.exit(main())
