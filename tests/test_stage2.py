"""Тесты конфигурации и стартовых скриптов этапа 2."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from src.application import ShellWindow
from src.commands import CommandProcessor
from src.config import AppConfig, DEFAULT_VFS_PATH, parse_arguments
from src.startup import SCRIPT_ERROR_MESSAGE, StartupScriptRunner


class ConfigurationTests(unittest.TestCase):
    """Проверить разбор параметров командной строки."""

    def test_default_vfs_path_is_defined(self) -> None:
        """Без параметров используется путь VFS по умолчанию."""

        config = parse_arguments([])

        self.assertEqual(config.vfs_path, DEFAULT_VFS_PATH)
        self.assertIsNone(config.script_path)

    def test_cli_parameters_are_saved(self) -> None:
        """Оба параметра сохраняются в конфигурации."""

        config = parse_arguments(
            ["--vfs", "custom.xml", "--script", "startup.txt"]
        )

        self.assertEqual(config.vfs_path, Path("custom.xml"))
        self.assertEqual(config.script_path, Path("startup.txt"))


class StartupScriptTests(unittest.TestCase):
    """Проверить последовательное выполнение строк скрипта."""

    def test_errors_are_skipped(self) -> None:
        """Ошибка команды не останавливает следующие строки."""

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "startup.txt"
            path.write_text("unknown\nls\n", encoding="utf-8")
            events = StartupScriptRunner(path).run(CommandProcessor().execute)

        self.assertEqual([event.text for event in events], ["unknown", "ls"])
        self.assertTrue(events[0].result.error)
        self.assertFalse(events[1].result.error)

    def test_comments_and_empty_lines_are_ignored(self) -> None:
        """Комментарии и пустые строки не выполняются."""

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "startup.txt"
            path.write_text("# comment\n\nls\n", encoding="utf-8")
            events = StartupScriptRunner(path).run(CommandProcessor().execute)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].text, "ls")

    def test_script_stops_after_exit(self) -> None:
        """Команда exit завершает последовательность команд."""

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "startup.txt"
            path.write_text("ls\nexit\ncd home\n", encoding="utf-8")
            events = StartupScriptRunner(path).run(CommandProcessor().execute)

        self.assertEqual([event.text for event in events], ["ls", "exit"])
        self.assertTrue(events[-1].result.should_exit)

    def test_script_continues_after_exit_when_error_occurred(self) -> None:
        """После ошибки exit не прерывает скрипт и не закрывает окно."""

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "startup.txt"
            path.write_text("unknown\nexit\nls\n", encoding="utf-8")
            runner = StartupScriptRunner(path)
            events = runner.run(CommandProcessor().execute)

        self.assertEqual([event.text for event in events],
                         ["unknown", "exit", "ls"])
        self.assertTrue(runner.has_errors)
        self.assertFalse(any(event.result.should_exit for event in events))

    def test_error_state_is_reset_for_each_run(self) -> None:
        """Повторный успешный запуск не наследует старые ошибки."""

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "startup.txt"
            runner = StartupScriptRunner(path)
            path.write_text("unknown\n", encoding="utf-8")
            runner.run(CommandProcessor().execute)
            self.assertTrue(runner.has_errors)
            path.write_text("ls\n", encoding="utf-8")
            runner.run(CommandProcessor().execute)

        self.assertFalse(runner.has_errors)


class StartupWindowTests(unittest.TestCase):
    """Проверить журнал скрипта и дальнейший интерактивный ввод."""

    @staticmethod
    def make_window(path: Path) -> ShellWindow:
        """Создать окно с тестовыми виджетами и настоящими командами."""

        window = ShellWindow.__new__(ShellWindow)
        window.config = AppConfig(DEFAULT_VFS_PATH, path)
        window.processor = CommandProcessor()
        window.running = True
        window.history = []
        window.history_index = None
        window.root = Mock()
        window.command_entry = Mock()
        window._append = Mock()
        window._show_prompt = Mock()
        return window

    def test_error_follows_command_and_summary_follows_last_command(
        self,
    ) -> None:
        """Проверить порядок ошибок, итогового сообщения и дальнейший ввод."""

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "startup.txt"
            path.write_text('unknown\n"unclosed\nls\n', encoding="utf-8")
            window = self.make_window(path)
            window._run_startup_script()

        messages = [call.args for call in window._append.call_args_list]
        unknown = messages.index(("unknown\n", "command"))
        self.assertEqual(messages[unknown + 1][1], "error")
        quote = messages.index(('"unclosed\n', "command"))
        self.assertEqual(messages[quote + 1][1], "error")
        final_command = messages.index(("ls\n", "command"))
        self.assertLess(final_command, len(messages) - 1)
        self.assertEqual(messages[-1], (SCRIPT_ERROR_MESSAGE + "\n", "error"))
        self.assertEqual(messages.count(messages[-1]), 1)
        self.assertTrue(window.running)
        window.root.destroy.assert_not_called()
        window._show_prompt.assert_called_once_with()

        window.command_entry.get.return_value = "ls"
        window.execute_input()
        self.assertTrue(window.running)
        self.assertEqual(window.history, ["ls"])
        window.root.destroy.assert_not_called()
        self.assertEqual(window._show_prompt.call_count, 2)

        window.command_entry.get.return_value = "exit"
        window.execute_input()
        self.assertFalse(window.running)
        window.root.destroy.assert_called_once_with()

    def test_script_exit_after_error_keeps_window_open(self) -> None:
        """Команды после exit выполняются, итог виден, окно остаётся открытым."""

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "startup.txt"
            path.write_text("unknown\nexit\nls\n", encoding="utf-8")
            window = self.make_window(path)
            window._run_startup_script()

        window._append.assert_any_call("ls\n", "command")
        window._append.assert_any_call(SCRIPT_ERROR_MESSAGE + "\n", "error")
        window.root.destroy.assert_not_called()
        self.assertTrue(window.running)

    def test_successful_script_has_no_error_summary(self) -> None:
        """Успешный скрипт оставляет ввод без сообщения об ошибке."""

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "startup.txt"
            path.write_text("ls\ncd home\n", encoding="utf-8")
            window = self.make_window(path)
            window._run_startup_script()

        messages = [call.args[0] for call in window._append.call_args_list]
        self.assertNotIn(SCRIPT_ERROR_MESSAGE + "\n", messages)
        self.assertTrue(window.running)
        window._show_prompt.assert_called_once_with()

    def test_successful_script_exit_still_closes_window(self) -> None:
        """В скрипте без ошибок exit сохраняет обычное действие."""

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "startup.txt"
            path.write_text("ls\nexit\n", encoding="utf-8")
            window = self.make_window(path)
            window._run_startup_script()

        self.assertFalse(window.running)
        window.root.destroy.assert_called_once_with()
        window._show_prompt.assert_not_called()

    def test_script_read_errors_are_reported_without_closing_window(
        self,
    ) -> None:
        """Отсутствующий файл и неверная кодировка не завершают приложение."""

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "startup.txt"
            for invalid_bytes in (None, b"\xff\xfe"):
                with self.subTest(content=invalid_bytes):
                    if invalid_bytes is not None:
                        path.write_bytes(invalid_bytes)
                    window = self.make_window(path)
                    window._run_startup_script()
                    window._append.assert_any_call(
                        SCRIPT_ERROR_MESSAGE + "\n", "error",
                    )
                    window.root.destroy.assert_not_called()
                    self.assertTrue(window.running)
                    window._show_prompt.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
