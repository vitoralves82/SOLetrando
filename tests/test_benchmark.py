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
             "erros_formatados": 3, "tokens_formatados_ref": 12,
             "termos_ref": 2, "termos_acertos": 1,
             "tempo_final_s": 1.0, "tempo_previa_s": 0.2,
             "vram_pico_mb": 3000, "carga_modelo_s": 5.0},
            {"modelo": "a", "erros_palavras": 0, "palavras_ref": 30,
             "erros_caracteres": 0, "caracteres_ref": 150, "duracao_s": 6.0,
             "erros_formatados": 1, "tokens_formatados_ref": 38,
             "termos_ref": 2, "termos_acertos": 2,
             "tempo_final_s": 2.0, "tempo_previa_s": 0.4,
             "vram_pico_mb": 3500, "carga_modelo_s": 5.0},
        ]
        summary = bench.summarize(rows)[0]
        self.assertEqual(summary["wer_pct"], 2.5)
        self.assertEqual(summary["cer_pct"], 1.0)
        self.assertEqual(summary["wer_formatado_pct"], 8.0)
        self.assertEqual(summary["acerto_termos_pct"], 75.0)
        self.assertEqual(summary["fator_tempo_real"], 0.3)
        self.assertEqual(summary["vram_pico_mb"], 3500)
        self.assertEqual(summary["amostras"], 2)

    def test_summary_without_terms_reports_none(self):
        row = {"modelo": "a", "erros_palavras": 0, "palavras_ref": 3,
               "erros_caracteres": 0, "caracteres_ref": 10, "duracao_s": 1.0,
               "erros_formatados": 0, "tokens_formatados_ref": 4,
               "termos_ref": 0, "termos_acertos": 0,
               "tempo_final_s": 0.5, "tempo_previa_s": 0.1,
               "vram_pico_mb": None, "carga_modelo_s": 1.0}
        summary = bench.summarize([row])[0]
        self.assertIsNone(summary["acerto_termos_pct"])
        self.assertIsNone(summary["vram_pico_mb"])


class DictationFormatTests(unittest.TestCase):
    def test_format_tokens_keep_case_and_punctuation(self):
        self.assertEqual(
            bench.format_tokens("Bom dia, IBAMA!"),
            ["Bom", "dia", ",", "IBAMA", "!"],
        )

    def test_lowercase_output_without_punctuation_is_penalized(self):
        reference = "Bom dia, pessoal. O IBAMA respondeu."
        # O WER comum nao ve diferenca; o formatado mostra o retrabalho.
        self.assertEqual(
            bench.error_counts(reference, "bom dia pessoal o ibama respondeu")[0], 0
        )
        errors, total = bench.formatted_error_counts(
            reference, "bom dia pessoal o ibama respondeu"
        )
        self.assertEqual(total, 9)
        # 3 pontuacoes ausentes + Bom, O e IBAMA trocadas por minusculas.
        self.assertEqual(errors, 6)

    def test_identical_formatting_has_no_errors(self):
        text = "A reunião é às 9h30, com a EnvironPact."
        self.assertEqual(bench.formatted_error_counts(text, text), (0, 10))


class TermAccuracyTests(unittest.TestCase):
    def test_terms_require_the_exact_spelling_of_the_reference(self):
        reference = "O IBAMA pediu o inventário do GHG Protocol ao IBAMA."
        hypothesis = "O Ibama pediu o inventário do GHG Protocol ao IBAMA."
        self.assertEqual(
            bench.term_hits(reference, hypothesis, ["ibama", "GHG Protocol"]),
            (3, 2),
        )

    def test_terms_absent_from_reference_are_ignored(self):
        self.assertEqual(
            bench.term_hits("Bom dia.", "Bom dia.", ["CONAMA"]), (0, 0)
        )

    def test_terms_do_not_match_inside_words(self):
        self.assertEqual(
            bench.term_hits("Escopo 3 e escopos", "Escopo 3 e escopos", ["Escopo"]),
            (1, 1),
        )

    def test_duplicate_terms_are_counted_once(self):
        self.assertEqual(
            bench.term_hits("IBAMA", "IBAMA", ["IBAMA", "ibama", " IBAMA "]),
            (1, 1),
        )


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
            terms = folder / "termos.txt"
            terms.write_text("# siglas\npessoal\nBoa tarde\n", encoding="utf-8")
            output = folder / "saida.csv"
            with mock.patch.dict(sys.modules, {"faster_whisper": fake_module}), \
                    mock.patch.object(bench, "gpu_memory_used_mb", return_value=None), \
                    mock.patch("builtins.print"):
                code = bench.main([
                    "medir", str(folder), "--modelos", "falso", "--device", "cpu",
                    "--saida", str(output), "--termos", str(terms),
                ])
            self.assertEqual(code, 0)
            with output.open(encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle, delimiter=";"))
        self.assertEqual([row["amostra"] for row in rows], ["a.wav", "b.wav"])
        self.assertEqual([row["wer_pct"] for row in rows], ["0.0", "66.67"])
        self.assertEqual(rows[0]["duracao_s"], "2.0")
        # "Bom dia, pessoal!" contra "Bom dia pessoal": faltam 2 sinais em 5.
        self.assertEqual(rows[0]["wer_formatado_pct"], "40.0")
        # "pessoal" aparece nas duas referencias; "Boa tarde" so na segunda.
        self.assertEqual(
            [(row["termos_ref"], row["termos_acertos"]) for row in rows],
            [("1", "1"), ("2", "1")],
        )


if __name__ == "__main__":
    unittest.main()
