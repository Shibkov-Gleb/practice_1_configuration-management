"""Тесты парсера первого этапа эмулятора."""

import os
import unittest
from unittest.mock import patch

from src.main import CommandParser


class CommandParserTests(unittest.TestCase):
    """Проверить разбор команд и раскрытие переменных окружения."""

    def test_parse_command_without_arguments(self) -> None:
        """Парсер возвращает одну команду без аргументов."""

        self.assertEqual(CommandParser.parse("ls"), ["ls"])

    def test_parse_command_with_arguments(self) -> None:
        """Парсер отделяет команду от нескольких аргументов."""

        result = CommandParser.parse("ls -la documents")

        self.assertEqual(result, ["ls", "-la", "documents"])

    def test_parse_preserves_quoted_argument(self) -> None:
        """Кавычки позволяют передать аргумент с пробелом."""

        result = CommandParser.parse('cd "My Documents"')

        self.assertEqual(result, ["cd", "My Documents"])

    def test_parse_expands_plain_environment_variable(self) -> None:
        """Форма ``$NAME`` заменяется значением переменной окружения."""

        with patch.dict(os.environ, {"TEST_SHELL_HOME": "C:\\Users\\student"}):
            result = CommandParser.parse("cd $TEST_SHELL_HOME")

        self.assertEqual(result, ["cd", "C:\\Users\\student"])

    def test_parse_expands_braced_environment_variable(self) -> None:
        """Форма ``${NAME}`` заменяется значением переменной окружения."""

        with patch.dict(os.environ, {"TEST_SHELL_HOME": "/home/student"}):
            result = CommandParser.parse("cd ${TEST_SHELL_HOME}")

        self.assertEqual(result, ["cd", "/home/student"])

    def test_missing_environment_variable_becomes_empty(self) -> None:
        """Для отсутствующей переменной используется пустая строка."""

        with patch.dict(os.environ, {}, clear=True):
            result = CommandParser.parse("echo $MISSING_SHELL_VARIABLE")

        self.assertEqual(result, ["echo", ""])

    def test_unclosed_quote_is_reported(self) -> None:
        """Незакрытая кавычка вызывает ошибку разбора."""

        with self.assertRaises(ValueError):
            CommandParser.parse('"unclosed')


if __name__ == "__main__":
    unittest.main()
