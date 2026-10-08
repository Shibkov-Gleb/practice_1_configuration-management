"""Парсер и команды первого и второго этапов эмулятора."""

from __future__ import annotations

import os
import re
import shlex
import time
from dataclasses import dataclass

from .vfs import (
    VfsError,
    VfsNode,
    VirtualFileSystem,
    format_mode,
    parse_mode,
)


NO_ARGUMENTS = 0
ONE_ARGUMENT = 1
TWO_ARGUMENTS = 2
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
        if command == "rm":
            return self._execute_rm(arguments)
        if command == "chmod":
            return self._execute_chmod(arguments)
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
            flags, path = self._parse_ls_arguments(arguments)
            target = self.vfs.resolve(path)
            nodes = self.vfs.list_directory(path)
        except (ValueError, VfsError) as error:
            return CommandResult.failure(f"Ошибка ls: {error}")
        entries = [
            (node.name, node) for node in nodes
            if "a" in flags or not target.is_directory
            or not node.name.startswith(".")
        ]
        if "a" in flags and target.is_directory:
            entries = [
                (".", target), ("..", target.parent or self.vfs.root),
                *entries,
            ]
        lines = tuple(
            self._format_node(node, flags, name) for name, node in entries
        )
        return CommandResult(lines)

    @staticmethod
    def _parse_ls_arguments(arguments: list[str]) -> tuple[set[str], str]:
        """Разобрать путь и поддерживаемые флаги команды ``ls``."""

        flags: set[str] = set()
        path = "."
        path_seen = False
        options_ended = False
        for argument in arguments:
            if argument == "--" and not options_ended:
                options_ended = True
                continue
            if (not options_ended and argument.startswith("-")
                    and argument != "-"):
                for flag in argument[1:]:
                    if flag not in "lha":
                        raise ValueError(f"неизвестный флаг: -{flag}")
                    flags.add(flag)
                continue
            if path_seen:
                raise ValueError("ожидается не более одного пути")
            path = argument
            path_seen = True
        return flags, path

    @staticmethod
    def _format_node(node: VfsNode, flags: set[str], name: str) -> str:
        """Сформировать строку обычного или подробного списка."""

        if "l" not in flags:
            return name
        size = str(node.size)
        if "h" in flags:
            size = CommandProcessor._human_readable_size(node.size)
        return f"{format_mode(node)} {size:>6} {name}"

    @staticmethod
    def _human_readable_size(size: int) -> str:
        """Показать размер в байтах или единицах с основанием 1024."""

        if size < 1024:
            return str(size)
        value = float(size)
        for unit in "KMGTPE":
            value /= 1024
            if value < 1024 or unit == "E":
                if value < 10:
                    return f"{value:.1f}{unit}"
                return f"{value:.0f}{unit}"
        return str(size)

    def _execute_cd(self, arguments: list[str]) -> CommandResult:
        """Изменить текущий каталог VFS."""

        if self.vfs is None:
            return self._execute_stub("cd", arguments)
        if len(arguments) > ONE_ARGUMENT:
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
        seconds = max(NO_ARGUMENTS, int(time.monotonic() - self.started_at))
        hours, remainder = divmod(seconds, SECONDS_PER_HOUR)
        minutes, seconds = divmod(remainder, SECONDS_PER_MINUTE)
        text = f"Uptime: {hours:02}:{minutes:02}:{seconds:02}"
        return CommandResult((text,))

    def _execute_rm(self, arguments: list[str]) -> CommandResult:
        """Удалить файл или каталог только из дерева VFS."""

        if self.vfs is None:
            return CommandResult.failure("Ошибка rm: VFS не подключена.")
        try:
            recursive, path = self._parse_rm_arguments(arguments)
            node = self.vfs.resolve(path)
            if node.is_directory and not recursive:
                raise VfsError("для каталога требуется ключ -r")
            self.vfs.remove(node)
        except (ValueError, VfsError) as error:
            return CommandResult.failure(f"Ошибка rm: {error}")
        return CommandResult((f"Удалено: {path}",))

    @staticmethod
    def _parse_rm_arguments(arguments: list[str]) -> tuple[bool, str]:
        """Разобрать флаги и путь команды ``rm``."""

        recursive = False
        path: str | None = None
        for argument in arguments:
            if argument in {"-r", "-R"}:
                if recursive:
                    raise ValueError("ключ -r указан повторно")
                recursive = True
                continue
            if path is not None:
                raise ValueError("ожидается один путь")
            path = argument
        if path is None:
            raise ValueError("не указан путь")
        return recursive, path

    def _execute_chmod(self, arguments: list[str]) -> CommandResult:
        """Изменить права узла только в дереве VFS."""

        if self.vfs is None:
            return CommandResult.failure("Ошибка chmod: VFS не подключена.")
        if len(arguments) != TWO_ARGUMENTS:
            return CommandResult.failure(
                "Ошибка chmod: нужны режим и путь."
            )
        mode_text, path = arguments
        try:
            node = self.vfs.resolve(path)
            self.vfs.set_mode(node, parse_mode(mode_text))
        except VfsError as error:
            return CommandResult.failure(f"Ошибка chmod: {error}")
        return CommandResult((f"Права изменены: {format_mode(node)}",))

    @staticmethod
    def _execute_stub(command: str, arguments: list[str]) -> CommandResult:
        """Вернуть имя команды-заглушки и ее аргументы."""

        if arguments:
            text = f"{command}: заглушка; аргументы: {' '.join(arguments)}"
        else:
            text = f"{command}: заглушка; аргументов нет"
        return CommandResult((text,))
