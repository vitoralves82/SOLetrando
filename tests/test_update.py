import tempfile
import unittest
import zipfile
from pathlib import Path

import update


class SafeExtractArchiveTests(unittest.TestCase):
    def _archive(self, entries):
        temporary = tempfile.TemporaryDirectory()
        archive_path = Path(temporary.name) / "update.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            for name, content in entries:
                archive.writestr(name, content)
        return temporary, archive_path

    def test_extracts_regular_files(self):
        temporary, archive_path = self._archive([
            ("SOLetrando/version.txt", "1.1.0"),
            ("SOLetrando/assets/icon.txt", "icone"),
        ])
        self.addCleanup(temporary.cleanup)

        with tempfile.TemporaryDirectory() as destination:
            with zipfile.ZipFile(archive_path) as archive:
                update.safe_extract_archive(archive, Path(destination))

            version = Path(destination) / "SOLetrando" / "version.txt"
            self.assertEqual(version.read_text(encoding="utf-8"), "1.1.0")

    def test_rejects_parent_directory_traversal(self):
        temporary, archive_path = self._archive([("../outside.txt", "ataque")])
        self.addCleanup(temporary.cleanup)

        with tempfile.TemporaryDirectory() as destination:
            with zipfile.ZipFile(archive_path) as archive:
                with self.assertRaisesRegex(ValueError, "inseguro"):
                    update.safe_extract_archive(archive, Path(destination))

    def test_rejects_windows_absolute_path(self):
        temporary, archive_path = self._archive([
            ("C:\\Users\\Public\\outside.txt", "ataque"),
        ])
        self.addCleanup(temporary.cleanup)

        with tempfile.TemporaryDirectory() as destination:
            with zipfile.ZipFile(archive_path) as archive:
                with self.assertRaisesRegex(ValueError, "absoluto do Windows"):
                    update.safe_extract_archive(archive, Path(destination))

    def test_rejects_symbolic_links(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        archive_path = Path(temporary.name) / "update.zip"
        link = zipfile.ZipInfo("atalho")
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr(link, "../outside.txt")

        with tempfile.TemporaryDirectory() as destination:
            with zipfile.ZipFile(archive_path) as archive:
                with self.assertRaisesRegex(ValueError, "Link simbolico"):
                    update.safe_extract_archive(archive, Path(destination))


class VersionComparisonTests(unittest.TestCase):
    def test_parse_accepts_tag_prefix_and_short_versions(self):
        self.assertEqual(update.parse_version("v1.1.2"), (1, 1, 2))
        self.assertEqual(update.parse_version("1.2"), (1, 2, 0))
        self.assertEqual(update.parse_version(" 2 "), (2, 0, 0))

    def test_parse_rejects_invalid_text(self):
        for value in ("", None, "abc", "1.2.3.4", "1..2", "1.2-beta", "v"):
            self.assertIsNone(update.parse_version(value), value)

    def test_only_later_versions_are_offered(self):
        self.assertTrue(update.is_newer_version("1.2.0", "1.1.2"))
        self.assertTrue(update.is_newer_version("v1.10.0", "1.9.9"))
        self.assertFalse(update.is_newer_version("1.1.2", "1.1.2"))
        self.assertFalse(update.is_newer_version("v1.1.2", "1.1.2"))

    def test_published_older_version_is_not_offered(self):
        # Situacao real: 1.1.2 instalada e 1.0.0 como ultima publicacao.
        self.assertFalse(update.is_newer_version("1.0.0", "1.1.2"))

    def test_invalid_remote_version_is_never_offered(self):
        self.assertFalse(update.is_newer_version("ultima", "1.0.0"))
        self.assertFalse(update.is_newer_version("", "0.0.0"))

    def test_unreadable_local_version_counts_as_zero(self):
        self.assertTrue(update.is_newer_version("1.0.0", "corrompido"))

    def test_source_checkout_is_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertFalse(update.is_source_checkout(folder))
            (Path(folder) / ".git").mkdir()
            self.assertTrue(update.is_source_checkout(folder))


if __name__ == "__main__":
    unittest.main()
