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


if __name__ == "__main__":
    unittest.main()
