"""Парсер и команды первого и второго этапов эмулятора."""

from __future__ import annotations

import os
import re
import shlex
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class CommandResult:
    """Результат выполнения одной команды."""

    lines: tuple[str, ...] = ()
    error: bool = False
    should_exit: bool = False
    clear: bool = False

    @classmethod
    def failure(cls, message: str) -> "CommandResult":
        """Создать результат с сообщением об ошибке."""

        return cls((message,), error=True)


class CommandParser:
    """Разбирать команды и раскрывать переменные окружения ОС."""

    _VARIABLE = re.compile(
        r"\$(?:"
        r"\{(?P<braced>[A-Za-z_][A-Za-z0-9_]*)\}|"
        r"(?P<plain>[A-Za-z_][A-Za-z0-9_]*)"
        r")"
    )

    @classmethod
    def expand_environment(cls, text: str) -> str:
        """Заменить переменные их значениями из окружения ОС."""

        def replace(match: re.Match[str]) -> str:
            name = match.group("braced") or match.group("plain")
            value = os.environ.get(name)
            if value is None and name == "HOME":
                value = os.environ.get("USERPROFILE")
            return value or ""

        return cls._VARIABLE.sub(replace, text)

    @classmethod
    def parse(cls, text: str) -> list[str]:
        """Вернуть команду и аргументы с раскрытыми переменными."""

        parts = shlex.split(text, posix=True)
        return [cls.expand_environment(part) for part in parts]


class CommandProcessor:
    """Выполнять команды-заглушки этапа 2."""

    def __init__(self) -> None:
        """Создать обработчик команд и запомнить момент запуска."""

        self.started_at = time.monotonic()

    def execute(self, text: str) -> CommandResult:
        """Разобрать и выполнить одну строку команды."""

        try:
            parts = CommandParser.parse(text)
        except ValueError as error:
            return CommandResult.failure(f"Ошибка разбора команды: {error}")
        if not parts:
            return CommandResult()

        command, *arguments = parts
        if command == "exit":
            return self._execute_exit(arguments)
        if command in {"ls", "cd"}:
            return self._execute_stub(command, arguments)
        return CommandResult.failure(
            f"Ошибка: неизвестная команда '{command}'."
        )

    @staticmethod
    def _execute_exit(arguments: list[str]) -> CommandResult:
        """Завершить работу или сообщить о лишних аргументах."""

        if arguments:
            return CommandResult.failure(
                "Ошибка: команда exit не принимает аргументы."
            )
        return CommandResult(should_exit=True)

    @staticmethod
    def _execute_stub(command: str, arguments: list[str]) -> CommandResult:
        """Вернуть имя команды-заглушки и ее аргументы."""

        if arguments:
            text = f"{command}: заглушка; аргументы: {' '.join(arguments)}"
        else:
            text = f"{command}: заглушка; аргументов нет"
        return CommandResult((text,))
