"""Тесты базовых команд, работающих с деревом VFS."""

import re
import unittest
from pathlib import Path

from src.commands import CommandProcessor
from src.vfs import VirtualFileSystem


VFS_PATH = Path("data/vfs/minimal.xml")


class BasicCommandTests(unittest.TestCase):
    """Проверить ls, cd, clear и uptime."""

    def setUp(self) -> None:
        """Создать обработчик с минимальной VFS перед тестом."""

        filesystem = VirtualFileSystem.from_xml(VFS_PATH)
        self.processor = CommandProcessor(filesystem)

    def test_ls_lists_current_directory(self) -> None:
        """Обычный ls выводит содержимое текущего каталога."""

        result = self.processor.execute("ls")

        self.assertEqual(result.lines, ("home",))
        self.assertFalse(result.error)

    def test_ls_long_format_lists_file_metadata(self) -> None:
        """Флаг -l выводит тип, права, размер и имя узла."""

        result = self.processor.execute("ls -l /home")

        self.assertRegex(result.lines[0], r"^-rw-r--r-- +\d+ welcome\.txt$")

    def test_cd_changes_current_directory(self) -> None:
        """cd изменяет каталог и поддерживает относительный путь."""

        result = self.processor.execute("cd home")

        self.assertEqual(result.lines, ("Текущий каталог: /home",))
        self.assertEqual(self.processor.vfs.current.path, "/home")

    def test_errors_are_reported(self) -> None:
        """Ошибочный путь и лишние аргументы не меняют состояние VFS."""

        missing = self.processor.execute("cd missing")
        too_many = self.processor.execute("cd home extra")

        self.assertTrue(missing.error)
        self.assertTrue(too_many.error)
        self.assertEqual(self.processor.vfs.current.path, "/")

    def test_clear_returns_clear_flag(self) -> None:
        """clear сообщает GUI, что область вывода нужно очистить."""

        result = self.processor.execute("clear")

        self.assertTrue(result.clear)
        self.assertFalse(result.error)

    def test_uptime_has_clock_format(self) -> None:
        """uptime возвращает продолжительность в формате часы:минуты:секунды."""

        result = self.processor.execute("uptime")

        self.assertRegex(result.lines[0], r"^Uptime: \d{2}:\d{2}:\d{2}$")


if __name__ == "__main__":
    unittest.main()
