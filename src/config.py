"""Конфигурация запуска эмулятора оболочки."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


DEFAULT_VFS_PATH = Path("data/vfs/minimal.xml")


@dataclass(frozen=True)
class AppConfig:
    """Параметры командной строки приложения."""

    vfs_path: Path
    script_path: Path | None

    def debug_lines(self) -> tuple[str, ...]:
        """Вернуть строки отладочного вывода параметров запуска."""

        script = str(self.script_path) if self.script_path else "не задан"
        return (
            "Параметры запуска:",
            f"  Путь к VFS: {self.vfs_path}",
            f"  Стартовый скрипт: {script}",
        )


def parse_arguments(arguments: Sequence[str] | None = None) -> AppConfig:
    """Разобрать параметры ``--vfs`` и ``--script``."""

    parser = argparse.ArgumentParser(
        description="Графический эмулятор оболочки ОС",
    )
    parser.add_argument(
        "--vfs",
        type=Path,
        default=DEFAULT_VFS_PATH,
        help="путь к XML-файлу виртуальной файловой системы",
    )
    parser.add_argument(
        "--script",
        type=Path,
        help="путь к стартовому скрипту команд эмулятора",
    )
    namespace = parser.parse_args(arguments)
    return AppConfig(namespace.vfs, namespace.script)
