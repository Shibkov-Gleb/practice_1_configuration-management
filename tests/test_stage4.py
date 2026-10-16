"""Тесты базовых команд, работающих с деревом VFS."""

import unittest
from pathlib import Path

from src.commands import CommandProcessor
from src.vfs import VirtualFileSystem

VFS_PATH = Path("data/vfs/minimal.xml")


def make_processor() -> CommandProcessor:
    """Создать обработчик с независимой минимальной VFS."""

    filesystem = VirtualFileSystem.from_xml(VFS_PATH)
    return CommandProcessor(filesystem)


class BasicCommandTests(unittest.TestCase):
    """Проверить ls, cd, clear и uptime."""

    def test_ls_lists_current_directory(self) -> None:
        """Обычный ls выводит содержимое текущего каталога."""

        result = make_processor().execute("ls")

        self.assertEqual(result.lines, ("home",))
        self.assertFalse(result.error)

    def test_ls_long_format_lists_file_metadata(self) -> None:
        """Флаг -l выводит тип, права, размер и имя узла."""

        result = make_processor().execute("ls -la /home")

        self.assertRegex(result.lines[0], r"^-rw-r--r-- +\d+ welcome\.txt$")

    def test_cd_changes_current_directory(self) -> None:
        """cd изменяет каталог и поддерживает относительный путь."""

        processor = make_processor()
        result = processor.execute("cd home")

        self.assertEqual(result.lines, ("Текущий каталог: /home",))
        self.assertEqual(processor.vfs.current.path, "/home")

    def test_errors_are_reported(self) -> None:
        """Ошибочный путь и лишние аргументы не меняют состояние VFS."""

        processor = make_processor()
        missing = processor.execute("cd missing")
        too_many = processor.execute("cd home extra")

        self.assertTrue(missing.error)
        self.assertTrue(too_many.error)
        self.assertEqual(processor.vfs.current.path, "/")

    def test_clear_returns_clear_flag(self) -> None:
        """clear сообщает GUI, что область вывода нужно очистить."""

        result = make_processor().execute("clear")

        self.assertTrue(result.clear)
        self.assertFalse(result.error)

    def test_uptime_has_clock_format(self) -> None:
        """uptime возвращает часы, минуты и секунды работы."""

        result = make_processor().execute("uptime")

        self.assertRegex(result.lines[0], r"^Uptime: \d{2}:\d{2}:\d{2}$")


if __name__ == "__main__":
    unittest.main()
