import unittest

from soletrando_text import (
    apply_corrections,
    build_initial_prompt,
    normalize_vocabulary,
    parse_corrections,
)


class TextToolsTests(unittest.TestCase):
    def test_vocabulary_removes_duplicates_and_empty_values(self):
        self.assertEqual(
            normalize_vocabulary(["PROCLIM", "", " proclim ", "EnvironPact"]),
            ["PROCLIM", "EnvironPact"],
        )

    def test_corrections_prefer_longer_phrases(self):
        corrections = {
            "pro clima": "PROCLIM",
            "clima": "clima",
        }
        self.assertEqual(
            apply_corrections("O pro clima avalia o clima.", corrections),
            "O PROCLIM avalia o clima.",
        )

    def test_corrections_do_not_replace_inside_words(self):
        self.assertEqual(
            apply_corrections("mar e Maromba", {"mar": "MAR"}),
            "MAR e Maromba",
        )

    def test_parse_corrections_reports_invalid_line(self):
        with self.assertRaisesRegex(ValueError, "Linha 2"):
            parse_corrections("pro clima = PROCLIM\nlinha inválida")

    def test_initial_prompt_uses_brazilian_portuguese_context(self):
        prompt = build_initial_prompt(["EnvironPact", "Camarupim"])
        self.assertIn("português brasileiro", prompt)
        self.assertIn("EnvironPact", prompt)


if __name__ == "__main__":
    unittest.main()
