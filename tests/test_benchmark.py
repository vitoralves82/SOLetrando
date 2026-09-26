import csv
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import benchmark_modelos as bench  # noqa: E402


class BenchmarkMetricsTests(unittest.TestCase):
    def test_normalization_keeps_accents_and_removes_punctuation(self):
        self.assertEqual(
            bench.normalize_text("Ação, Rápida!  Emissões: 1,2 mil."),
            "ação rápida emissões 1 2 mil",
        )

    def test_identical_text_has_no_errors(self):
        self.assertEqual(
            bench.error_counts("Bom dia, pessoal.", "bom dia pessoal"),
            (0, 3, 0, 13),
        )

    def test_word_substitution_insertion_and_deletion(self):
        words, total, _chars, _char_total = bench.error_counts(
            "o relatório foi enviado ontem", "o relatório enviado hoje cedo"
        )
        # remove "foi", troca "ontem" por "hoje", insere "cedo"
        self.assertEqual((words, total), (3, 5))

    def test_edit_distance_on_characters(self):
        self.assertEqual(bench.edit_distance("proclim", "pro clima".replace(" ", "")), 1)

    def test_summary_weights_error_rate_by_sample_size(self):
        rows = [
            {"modelo": "a", "erros_palavras": 1, "palavras_ref": 10,
             "erros_caracteres": 2, "caracteres_ref": 50, "duracao_s": 4.0,
             "tempo_final_s": 1.0, "tempo_previa_s": 0.2,
             "vram_pico_mb": 3000, "carga_modelo_s": 5.0},
            {"modelo": "a", "erros_palavras": 0, "palavras_ref": 30,
             "erros_caracteres": 0, "caracteres_ref": 150, "duracao_s": 6.0,
             "tempo_final_s": 2.0, "tempo_previa_s": 0.4,
             "vram_pico_mb": 3500, "carga_modelo_s": 5.0},
        ]
        summary = bench.summarize(rows)[0]
        self.assertEqual(summary["wer_pct"], 2.5)
        self.assertEqual(summary["cer_pct"], 1.0)
        self.assertEqual(summary["fator_tempo_real"], 0.3)
        self.assertEqual(summary["vram_pico_mb"], 3500)
        self.assertEqual(summary["amostras"], 2)


class FakeSegment:
    def __init__(self, text):
        self.text = text


class FakeWhisperModel:
    """Devolve sempre a mesma frase, com um erro proposital."""

    def __init__(self, name, device, compute_type):
        self.name = name

    def transcribe(self, audio, language=None, initial_prompt=None, **options):
        return iter([FakeSegment(" Bom dia pessoal")]), None


class BenchmarkRunTests(unittest.TestCase):
    def test_measure_writes_csv_and_summary(self):
        fake_module = types.SimpleNamespace(
            WhisperModel=FakeWhisperModel,
            decode_audio=lambda path, sampling_rate: [0.0] * (sampling_rate * 2),
        )
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            (folder / "a.wav").write_bytes(b"")
            (folder / "a.txt").write_text("Bom dia, pessoal!", encoding="utf-8")
            (folder / "b.wav").write_bytes(b"")
            (folder / "b.txt").write_text("Boa tarde pessoal", encoding="utf-8")
            (folder / "sem_referencia.wav").write_bytes(b"")
            output = folder / "saida.csv"
            with mock.patch.dict(sys.modules, {"faster_whisper": fake_module}), \
                    mock.patch.object(bench, "gpu_memory_used_mb", return_value=None), \
                    mock.patch("builtins.print"):
                code = bench.main([
                    "medir", str(folder), "--modelos", "falso", "--device", "cpu",
                    "--saida", str(output),
                ])
            self.assertEqual(code, 0)
            with output.open(encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle, delimiter=";"))
        self.assertEqual([row["amostra"] for row in rows], ["a.wav", "b.wav"])
        self.assertEqual([row["wer_pct"] for row in rows], ["0.0", "66.67"])
        self.assertEqual(rows[0]["duracao_s"], "2.0")


if __name__ == "__main__":
    unittest.main()
