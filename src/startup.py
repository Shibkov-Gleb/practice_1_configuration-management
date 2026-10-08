"""Запуск последовательности команд из стартового скрипта."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from .commands import CommandResult


SCRIPT_ERROR_MESSAGE = "Где то в вашем скрипте ошибка"


@dataclass(frozen=True)
class ScriptEvent:
    """Одна обработанная строка стартового скрипта."""

    line_number: int
    text: str
    result: CommandResult


class StartupScriptRunner:
    """Читать и последовательно выполнять команды из файла."""

    def __init__(self, path: Path) -> None:
        """Запомнить путь к стартовому скрипту."""

        self.path = path
        self.has_errors = False

    def run(self, execute: Callable[[str], CommandResult]) -> list[ScriptEvent]:
        """Выполнить команды, пропуская ошибочные строки."""

        self.has_errors = False
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as error:
            self.has_errors = True
            result = CommandResult.failure(
                f"Ошибка запуска скрипта: {error}"
            )
            return [ScriptEvent(0, "", result)]

        events: list[ScriptEvent] = []
        for line_number, line in enumerate(lines, start=1):
            command = line.strip()
            if not command or command.startswith("#"):
                continue
            result = execute(command)
            self.has_errors = self.has_errors or result.error
            if result.should_exit and self.has_errors:
                result = replace(result, should_exit=False)
            events.append(ScriptEvent(line_number, command, result))
            if result.should_exit:
                break
        return events
