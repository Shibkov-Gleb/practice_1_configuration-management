"""Автоматические тесты первого этапа эмулятора."""

import os
import unittest
from unittest.mock import Mock, patch

from src.main import CommandParser, ShellEmulator


class CommandParserTests(unittest.TestCase):
    """Проверить разбор команд и переменных окружения."""

    def test_parse_command_without_arguments(self) -> None:
        """Команда без аргументов разбирается в один элемент."""

        self.assertEqual(CommandParser.parse("ls"), ["ls"])

    def test_parse_command_with_arguments(self) -> None:
        """Команда и несколько аргументов разделяются."""

        result = CommandParser.parse("ls -la documents")

        self.assertEqual(result, ["ls", "-la", "documents"])

    def test_parse_preserves_quoted_argument(self) -> None:
        """Кавычки сохраняют аргумент с пробелом единым."""

        result = CommandParser.parse('cd "My Documents"')

        self.assertEqual(result, ["cd", "My Documents"])

    def test_parse_expands_plain_environment_variable(self) -> None:
        """Переменная в форме $NAME раскрывается."""

        with patch.dict(os.environ, {"TEST_SHELL_HOME": "C:\\Users\\student"}):
            result = CommandParser.parse("cd $TEST_SHELL_HOME")

        self.assertEqual(result, ["cd", "C:\\Users\\student"])

    def test_parse_expands_braced_environment_variable(self) -> None:
        """Переменная в форме ${NAME} раскрывается."""

        with patch.dict(os.environ, {"TEST_SHELL_HOME": "/home/student"}):
            result = CommandParser.parse("cd ${TEST_SHELL_HOME}")

        self.assertEqual(result, ["cd", "/home/student"])

    def test_missing_environment_variable_becomes_empty(self) -> None:
        """Неизвестная переменная заменяется пустой строкой."""

        with patch.dict(os.environ, {}, clear=True):
            result = CommandParser.parse("echo $MISSING_SHELL_VARIABLE")

        self.assertEqual(result, ["echo", ""])

    def test_unclosed_quote_is_reported(self) -> None:
        """Незакрытая кавычка вызывает ошибку разбора."""

        with self.assertRaises(ValueError):
            CommandParser.parse('"unclosed')

    def test_home_falls_back_to_windows_user_profile(self) -> None:
        """HOME использует USERPROFILE, если HOME отсутствует."""

        environment = {"USERPROFILE": "C:\\Users\\student"}
        with patch.dict(os.environ, environment, clear=True):
            result = CommandParser.parse("cd $HOME")

        self.assertEqual(result, ["cd", "C:\\Users\\student"])


class ShellEmulatorTests(unittest.TestCase):
    """Проверить команды без запуска настоящего графического окна."""

    @staticmethod
    def make_shell(command: str) -> ShellEmulator:
        """Создать минимальный объект эмулятора с тестовыми виджетами."""

        shell = ShellEmulator.__new__(ShellEmulator)
        shell.command_entry = Mock()
        shell.command_entry.get.return_value = command
        shell.history = []
        shell.history_index = None
        shell._append = Mock()
        shell._show_prompt = Mock()
        shell.exit = Mock()
        return shell

    def test_window_title_contains_vfs_name(self) -> None:
        """Заголовок окна содержит переданное имя VFS."""

        root = Mock()
        helpers = (
            patch.object(ShellEmulator, "_configure_style"),
            patch.object(ShellEmulator, "_build_interface"),
            patch.object(ShellEmulator, "_write_welcome"),
            patch.object(ShellEmulator, "_show_prompt"),
        )
        with helpers[0], helpers[1], helpers[2], helpers[3]:
            ShellEmulator(root, "test_vfs")

        root.title.assert_called_once_with(
            "Эмулятор оболочки ОС - test_vfs"
        )

    def test_ls_stub_outputs_name_and_arguments(self) -> None:
        """Заглушка ls печатает имя и аргументы."""

        shell = self.make_shell("ls -la documents")
        shell.execute_input()

        shell._append.assert_any_call(
            "ls: заглушка; аргументы: -la documents\n",
            "result",
        )

    def test_cd_stub_outputs_name_and_arguments(self) -> None:
        """Заглушка cd печатает имя и аргументы."""

        shell = self.make_shell("cd /home/student")
        shell.execute_input()

        shell._append.assert_any_call(
            "cd: заглушка; аргументы: /home/student\n",
            "result",
        )

    def test_unknown_command_reports_error(self) -> None:
        """Неизвестная команда приводит к сообщению об ошибке."""

        shell = self.make_shell("unknown")
        shell.execute_input()

        shell._append.assert_any_call(
            "Ошибка: неизвестная команда 'unknown'.\n",
            "error",
        )

    def test_parse_error_is_shown_in_dialog(self) -> None:
        """Ошибка кавычек отображается в истории диалога."""

        shell = self.make_shell('"unclosed')
        shell.execute_input()

        error_calls = [
            call.args[0]
            for call in shell._append.call_args_list
            if call.args[1] == "error"
        ]
        self.assertTrue(error_calls[0].startswith("Ошибка разбора команды:"))

    def test_exit_rejects_arguments(self) -> None:
        """Команда exit не принимает аргументы."""

        shell = self.make_shell("exit now")
        shell.execute_input()

        shell._append.assert_any_call(
            "Ошибка: команда exit не принимает аргументы.\n",
            "error",
        )
        shell.exit.assert_not_called()

    def test_exit_without_arguments_closes_application(self) -> None:
        """Команда exit без аргументов закрывает приложение."""

        shell = self.make_shell("exit")
        shell.execute_input()

        shell.exit.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
