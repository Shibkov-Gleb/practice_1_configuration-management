"""Тесты команд изменения VFS в памяти."""

import unittest
from itertools import permutations
from pathlib import Path

from src.commands import CommandProcessor
from src.vfs import VfsError, VfsNode, VirtualFileSystem


VFS_PATH = Path("data/vfs/several-files.xml")


class AdditionalCommandTests(unittest.TestCase):
    """Проверить rm и chmod, включая обработку ошибок."""

    def setUp(self) -> None:
        """Создать независимую VFS перед тестом."""

        filesystem = VirtualFileSystem.from_xml(VFS_PATH)
        self.processor = CommandProcessor(filesystem)

    def test_rm_deletes_file_in_memory(self) -> None:
        """rm удаляет файл из дерева, не меняя исходный XML."""

        result = self.processor.execute("rm /home/readme.txt")

        self.assertFalse(result.error)
        with self.assertRaises(VfsError):
            self.processor.vfs.resolve("/home/readme.txt")

    def test_rm_requires_recursive_flag_for_directory(self) -> None:
        """Для удаления каталога требуется ключ -r."""

        rejected = self.processor.execute("rm /home")
        accepted = self.processor.execute("rm -r /home")

        self.assertTrue(rejected.error)
        self.assertFalse(accepted.error)
        self.assertEqual(
            self.processor.execute("ls").lines,
            ("bin", "version.txt"),
        )

    def test_rm_rejects_vfs_root(self) -> None:
        """Корень VFS нельзя удалить даже с ключом -r."""

        result = self.processor.execute("rm -r /")

        self.assertTrue(result.error)

    def test_chmod_changes_mode_in_memory(self) -> None:
        """chmod изменяет права узла, видимые через подробный ls."""

        changed = self.processor.execute("chmod 600 /home/notes.txt")
        listing = self.processor.execute("ls -l /home/notes.txt")

        self.assertFalse(changed.error)
        self.assertTrue(listing.lines[0].startswith("-rw-------"))

    def test_chmod_reports_invalid_arguments(self) -> None:
        """Неверный режим и неполный вызов chmod дают ошибки."""

        invalid_mode = self.processor.execute("chmod 999 /home/notes.txt")
        missing_path = self.processor.execute("chmod 600")

        self.assertTrue(invalid_mode.error)
        self.assertTrue(missing_path.error)


class BoardCommandTests(unittest.TestCase):
    """Проверить сочетания флагов и пути с точками с доски."""

    def setUp(self) -> None:
        """Добавить большой и скрытый файлы в независимую VFS."""

        filesystem = VirtualFileSystem.from_xml(VFS_PATH)
        home = filesystem.resolve("/home")
        for name, content in (("large.bin", b"x" * 1536),
                              (".hidden", b"secret")):
            home.children[name] = VfsNode(
                name=name, is_directory=False, content=content, parent=home,
            )
        self.processor = CommandProcessor(filesystem)

    def test_ls_accepts_all_flag_orders_and_separate_options(self) -> None:
        """Все сочетания l, h, a работают до и после пути."""

        for count in range(1, 4):
            for order in permutations("lha", count):
                flags = "".join(order)
                separate = " ".join("-" + flag for flag in order)
                commands = (
                    f"ls -{flags} /home", f"ls /home -{flags}",
                    f"ls {separate} /home", f"ls /home {separate}",
                )
                for command in commands:
                    with self.subTest(command=command):
                        result = self.processor.execute(command)
                        self.assertFalse(result.error, result.lines)
                        names = [line.split()[-1] for line in result.lines]
                        expected = ["large.bin", "notes.txt", "readme.txt"]
                        if "a" in flags:
                            expected = [".", "..", ".hidden", *expected]
                        self.assertEqual(names, expected)
                        large = next(line for line in result.lines
                                     if line.endswith("large.bin"))
                        if "l" in flags:
                            size = "1.5K" if "h" in flags else "1536"
                            self.assertEqual(large.split(),
                                             ["-rw-r--r--", size, "large.bin"])
                        else:
                            self.assertEqual(large, "large.bin")

    def test_ls_hidden_file_can_be_listed_explicitly(self) -> None:
        """Явный путь к скрытому файлу работает без -a."""

        result = self.processor.execute("ls /home/.hidden")

        self.assertFalse(result.error)
        self.assertEqual(result.lines, (".hidden",))

    def test_ls_all_in_root_keeps_dot_entries_in_vfs(self) -> None:
        """Обе точки в корне обозначают корень VFS."""

        result = self.processor.execute("ls -la /")

        self.assertFalse(result.error)
        self.assertEqual(result.lines[0].split()[:-1],
                         result.lines[1].split()[:-1])
        self.assertEqual(result.lines[0].split()[-1], ".")
        self.assertEqual(result.lines[1].split()[-1], "..")
        self.assertNotIn(".", self.processor.vfs.root.children)

    def test_ls_human_sizes_cover_bytes_and_larger_units(self) -> None:
        """Размеры файлов отображаются в байтах, K и M."""

        node = self.processor.vfs.resolve("/home/large.bin")
        for size, expected in ((0, "0"), (1023, "1023"), (1024, "1.0K"),
                               (1536, "1.5K"), (10240, "10K"),
                               (1048576, "1.0M")):
            with self.subTest(size=size):
                node.content = b"x" * size
                result = self.processor.execute("ls -lh /home/large.bin")
                self.assertFalse(result.error)
                self.assertEqual(result.lines[0].split()[1], expected)

    def test_ls_repeated_flags_are_allowed(self) -> None:
        """Повтор флага не меняет результат."""

        repeated = self.processor.execute("ls -llhha /home")
        normal = self.processor.execute("ls -lha /home")

        self.assertFalse(repeated.error)
        self.assertEqual(repeated.lines, normal.lines)

    def test_ls_unknown_flags_and_extra_paths_are_rejected(self) -> None:
        """Неизвестный флаг не трактуется как имя каталога."""

        for command in ("ls -x", "ls -lhx", "ls --help", "ls /home /bin"):
            with self.subTest(command=command):
                result = self.processor.execute(command)
                self.assertTrue(result.error)
                self.assertEqual(self.processor.vfs.current.path, "/")

    def test_ls_option_terminator_allows_names_with_hyphens(self) -> None:
        """После -- аргумент с дефисом считается путём."""

        root = self.processor.vfs.root
        root.children["-reports"] = VfsNode(
            name="-reports", is_directory=False, parent=root,
        )
        result = self.processor.execute("ls -l -- -reports")

        self.assertFalse(result.error)
        self.assertTrue(result.lines[0].endswith(" -reports"))

    def test_cd_resolves_dots_inside_relative_and_absolute_paths(self) -> None:
        """Точки обрабатываются в любом компоненте пути."""

        cases = (
            ("./home", "/home"), ("home/.", "/home"),
            ("home/..", "/"), ("home/../home", "/home"),
            ("./home/./../bin/..", "/"), ("/home/../bin/.", "/bin"),
            ("home/../../..", "/"),
        )
        for path, expected in cases:
            with self.subTest(path=path):
                self.processor.vfs.current = self.processor.vfs.root
                result = self.processor.execute(f"cd {path}")
                self.assertFalse(result.error, result.lines)
                self.assertEqual(self.processor.vfs.current.path, expected)

    def test_cd_dot_and_parent_use_current_directory(self) -> None:
        """Одиночные . и .. работают относительно текущего каталога."""

        for command, expected in (("cd home", "/home"), ("cd .", "/home"),
                                  ("cd ..", "/"), ("cd ..", "/")):
            result = self.processor.execute(command)
            self.assertFalse(result.error)
            self.assertEqual(self.processor.vfs.current.path, expected)

    def test_ls_resolves_dots_without_changing_current_directory(self) -> None:
        """ls разрешает . и .., сохраняя текущий каталог."""

        self.processor.execute("cd /home")
        listing = self.processor.execute("ls -hal ../home/.")
        expected = self.processor.execute("ls -lha .")

        self.assertFalse(listing.error)
        self.assertEqual(listing.lines, expected.lines)
        self.assertEqual(self.processor.vfs.current.path, "/home")

    def test_dot_components_after_files_are_rejected(self) -> None:
        """Нельзя проходить через файл даже с помощью . или .."""

        for command in ("cd /home/notes.txt/..", "ls /home/notes.txt/.",
                        "ls /home/notes.txt/../readme.txt", "cd home../"):
            with self.subTest(command=command):
                result = self.processor.execute(command)
                self.assertTrue(result.error)
                self.assertEqual(self.processor.vfs.current.path, "/")


if __name__ == "__main__":
    unittest.main()
