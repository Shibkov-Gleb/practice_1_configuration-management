"""Тесты XML-загрузчика виртуальной файловой системы."""

import base64
import tempfile
import unittest
from pathlib import Path

from src.vfs import VfsError, VirtualFileSystem


class VirtualFileSystemTests(unittest.TestCase):
    """Проверить загрузку дерева и двоичных данных в память."""

    def test_xml_builds_nested_tree(self) -> None:
        """Вложенные XML-элементы становятся узлами дерева."""

        xml = """<vfs name='test'>
          <directory name='home'><file name='note.txt'>hello</file></directory>
        </vfs>"""
        filesystem = self._load(xml)

        note = filesystem.resolve("/home/note.txt")

        self.assertEqual(note.content, b"hello")
        self.assertEqual(note.path, "/home/note.txt")

    def test_base64_file_is_decoded_in_memory(self) -> None:
        """Содержимое base64-файла декодируется в байты."""

        encoded = base64.b64encode(b"binary").decode("ascii")
        filesystem = self._load(
            f"<vfs name='test'><file name='data.bin' encoding='base64'>"
            f"{encoded}</file></vfs>"
        )

        self.assertEqual(filesystem.resolve("/data.bin").content, b"binary")

    def test_source_file_is_not_modified(self) -> None:
        """Загрузка не перезаписывает XML-источник."""

        xml = "<vfs name='test'><file name='a.txt'>a</file></vfs>"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vfs.xml"
            path.write_text(xml, encoding="utf-8")
            before = path.read_bytes()
            VirtualFileSystem.from_xml(path)

            self.assertEqual(path.read_bytes(), before)

    def test_invalid_xml_reports_error(self) -> None:
        """Ошибка XML превращается в понятную ошибку VFS."""

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.xml"
            path.write_text("<vfs>", encoding="utf-8")

            with self.assertRaises(VfsError):
                VirtualFileSystem.from_xml(path)

    @staticmethod
    def _load(xml: str) -> VirtualFileSystem:
        """Загрузить тестовый XML из временного файла."""

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vfs.xml"
            path.write_text(xml, encoding="utf-8")
            return VirtualFileSystem.from_xml(path)


if __name__ == "__main__":
    unittest.main()
