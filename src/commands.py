"""Парсер и команды первого и второго этапов эмулятора."""

from __future__ import annotations

import os
import re
import shlex
import time
from dataclasses import dataclass

from .vfs import VfsError, VfsNode, VirtualFileSystem, format_mode


SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 60 * SECONDS_PER_MINUTE


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
    """Выполнять команды эмулятора и хранить подключенную VFS."""

    def __init__(self, vfs: VirtualFileSystem | None = None) -> None:
        """Создать обработчик команд и запомнить момент запуска."""

        self.vfs = vfs
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
        if command == "ls":
            return self._execute_ls(arguments)
        if command == "cd":
            return self._execute_cd(arguments)
        if command == "clear":
            return self._execute_clear(arguments)
        if command == "uptime":
            return self._execute_uptime(arguments)
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

    def _execute_ls(self, arguments: list[str]) -> CommandResult:
        """Показать содержимое каталога VFS."""

        if self.vfs is None:
            return self._execute_stub("ls", arguments)
        try:
            long_format, path = self._parse_ls_arguments(arguments)
            nodes = self.vfs.list_directory(path)
        except (ValueError, VfsError) as error:
            return CommandResult.failure(f"Ошибка ls: {error}")
        lines = tuple(self._format_node(node, long_format) for node in nodes)
        return CommandResult(lines)

    @staticmethod
    def _parse_ls_arguments(arguments: list[str]) -> tuple[bool, str]:
        """Разобрать путь и поддерживаемые флаги команды ``ls``."""

        long_format = False
        path = "."
        path_seen = False
        for argument in arguments:
            if argument in {"-l", "-a"}:
                long_format = long_format or argument == "-l"
                continue
            if argument in {"-la", "-al"}:
                long_format = True
                continue
            if path_seen:
                raise ValueError("ожидается не более одного пути")
            path = argument
            path_seen = True
        return long_format, path

    @staticmethod
    def _format_node(node: VfsNode, long_format: bool) -> str:
        """Сформировать строку обычного или подробного списка."""

        if not long_format:
            return node.name
        return f"{format_mode(node)} {node.size:>6} {node.name}"

    def _execute_cd(self, arguments: list[str]) -> CommandResult:
        """Изменить текущий каталог VFS."""

        if self.vfs is None:
            return self._execute_stub("cd", arguments)
        if len(arguments) > 1:
            return CommandResult.failure(
                "Ошибка cd: ожидается не более одного пути."
            )
        path = arguments[0] if arguments else "."
        try:
            node = self.vfs.change_directory(path)
        except VfsError as error:
            return CommandResult.failure(f"Ошибка cd: {error}")
        return CommandResult((f"Текущий каталог: {node.path}",))

    @staticmethod
    def _execute_clear(arguments: list[str]) -> CommandResult:
        """Подготовить очистку области вывода."""

        if arguments:
            return CommandResult.failure(
                "Ошибка: команда clear не принимает аргументы."
            )
        return CommandResult(clear=True)

    def _execute_uptime(self, arguments: list[str]) -> CommandResult:
        """Показать время работы эмулятора."""

        if arguments:
            return CommandResult.failure(
                "Ошибка: команда uptime не принимает аргументы."
            )
        seconds = max(0, int(time.monotonic() - self.started_at))
        hours, remainder = divmod(seconds, SECONDS_PER_HOUR)
        minutes, seconds = divmod(remainder, SECONDS_PER_MINUTE)
        return CommandResult((f"Uptime: {hours:02}:{minutes:02}:{seconds:02}",))

    @staticmethod
    def _execute_stub(command: str, arguments: list[str]) -> CommandResult:
        """Вернуть имя команды-заглушки и ее аргументы."""

        if arguments:
            text = f"{command}: заглушка; аргументы: {' '.join(arguments)}"
        else:
            text = f"{command}: заглушка; аргументов нет"
        return CommandResult((text,))
