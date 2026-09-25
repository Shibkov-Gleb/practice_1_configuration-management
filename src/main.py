"""Графический REPL эмулятора оболочки ОС для первого этапа."""

from __future__ import annotations

import getpass
import os
import re
import shlex
import socket
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Optional


VFS_NAME = "vfs_stage1"
WINDOW_WIDTH = 960
WINDOW_HEIGHT = 620
MIN_WINDOW_WIDTH = 640
MIN_WINDOW_HEIGHT = 420
OUTER_PADDING = 12
BUTTON_WIDTH = 4
ENTRY_IPADY = 7

DEFAULT_BACKGROUND = "#202124"
OUTPUT_BACKGROUND = "#111315"
OUTPUT_FOREGROUND = "#e8eaed"
OUTPUT_INSERT_COLOR = "#e8eaed"
OUTPUT_SELECTION_COLOR = "#3c4043"

class CommandParser:
    """Разбирать команды и раскрывать переменные окружения ОС."""

    VARIABLE = re.compile(
        r"\$(?:"
        r"\{(?P<braced>[A-Za-z_][A-Za-z0-9_]*)\}|"
        r"(?P<plain>[A-Za-z_][A-Za-z0-9_]*)"
        r")"
    )

    @classmethod
    def expand_environment(cls, text: str) -> str:
        """Заменить переменные их значениями из окружения реальной ОС."""

        def replace(match: re.Match[str]) -> str:
            name = match.group("braced") or match.group("plain")
            value = os.environ.get(name)
            if value is None and name == "HOME":
                value = os.environ.get("USERPROFILE")
            return "" if value is None else value

        return cls.VARIABLE.sub(replace, text)

    @classmethod
    def parse(cls, text: str) -> list[str]:
        """Вернуть команду и аргументы с раскрытыми переменными."""

        parts = shlex.split(text, posix=True)
        return [cls.expand_environment(part) for part in parts]


class ShellEmulator:
    """Управлять окном эмулятора и выполнением команд первого этапа."""

    def __init__(self, root: tk.Tk, vfs_name: str = VFS_NAME) -> None:
        """Создать интерфейс эмулятора в переданном окне Tk."""

        self.root = root
        self.vfs_name = vfs_name
        self.history: list[str] = []
        self.history_index: Optional[int] = None
        self.running = True

        self.root.title(f"Эмулятор оболочки ОС - {self.vfs_name}")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.root.configure(bg=DEFAULT_BACKGROUND)

        self._configure_style()
        self._build_interface()
        self._write_welcome()
        self._show_prompt()

    @staticmethod
    def _configure_style() -> None:
        """Настроить стиль стандартных элементов интерфейса."""

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Run.TButton",
            font=("Segoe UI", 14, "bold"),
            padding=(14, 5),
        )

    def _build_interface(self) -> None:
        """Создать основные области окна."""

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main = ttk.Frame(self.root, padding=OUTER_PADDING)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)

        self._build_output_area(main)
        self._build_command_area(main)
        self.root.protocol("WM_DELETE_WINDOW", self.exit)

    def _build_output_area(self, parent: ttk.Frame) -> None:
        """Создать прокручиваемое поле истории диалога."""

        output_frame = ttk.Frame(parent)
        output_frame.grid(row=0, column=0, sticky="nsew")
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)

        self.output = tk.Text(
            output_frame,
            wrap="word",
            state="disabled",
            background=OUTPUT_BACKGROUND,
            foreground=OUTPUT_FOREGROUND,
            insertbackground=OUTPUT_INSERT_COLOR,
            selectbackground=OUTPUT_SELECTION_COLOR,
            relief="flat",
            borderwidth=0,
            padx=14,
            pady=OUTER_PADDING,
            font=("Consolas", 11),
        )
        self.output.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(
            output_frame,
            orient="vertical",
            command=self.output.yview,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.output.configure(yscrollcommand=scrollbar.set)

        self._configure_output_tags()

    def _configure_output_tags(self) -> None:
        """Назначить цвета разным видам текста в истории."""

        self.output.tag_configure("prompt", foreground="#8ab4f8")
        self.output.tag_configure("command", foreground="#fbbc04")
        self.output.tag_configure("error", foreground="#f28b82")
        self.output.tag_configure("info", foreground="#9aa0a6")
        self.output.tag_configure("result", foreground=OUTPUT_FOREGROUND)

    def _build_command_area(self, parent: ttk.Frame) -> None:
        """Создать поле команды и кнопку выполнения."""

        command_frame = ttk.Frame(
            parent,
            padding=(0, OUTER_PADDING, 0, 0),
        )
        command_frame.grid(row=1, column=0, sticky="ew")
        command_frame.columnconfigure(0, weight=1)

        self.command_entry = ttk.Entry(
            command_frame,
            font=("Consolas", 12),
        )
        self.command_entry.grid(
            row=0,
            column=0,
            sticky="ew",
            ipady=ENTRY_IPADY,
        )
        self.command_entry.bind("<Return>", self._on_submit)
        self.command_entry.bind("<Up>", self._show_previous_command)
        self.command_entry.bind("<Down>", self._show_next_command)

        run_button = ttk.Button(
            command_frame,
            text=">",
            width=BUTTON_WIDTH,
            style="Run.TButton",
            command=self.execute_input,
        )
        run_button.grid(row=0, column=1, padx=(8, 0), sticky="ns")

    def _write_welcome(self) -> None:
        """Показать имя VFS и перечень доступных команд."""

        self._append(
            "Минимальный прототип эмулятора оболочки ОС\n",
            "info",
        )
        self._append(f"VFS: {self.vfs_name}\n", "info")
        self._append("Команды: ls, cd, exit\n", "info")
        self._append(
            "Переменные окружения: например, cd $HOME\n\n",
            "info",
        )

    def _append(self, text: str, tag: str = "result") -> None:
        """Добавить текст в историю и прокрутить её к концу."""

        self.output.configure(state="normal")
        self.output.insert(tk.END, text, tag)
        self.output.configure(state="disabled")
        self.output.see(tk.END)

    @staticmethod
    def _prompt() -> str:
        """Сформировать приглашение из имени пользователя и хоста."""

        username = getpass.getuser() or "user"
        hostname = socket.gethostname() or "localhost"
        return f"{username}@{hostname}:~$ "

    def _show_prompt(self) -> None:
        """Добавить новое приглашение к вводу."""

        self._append(self._prompt(), "prompt")

    def _on_submit(self, _event: tk.Event) -> str:
        """Выполнить команду после нажатия Enter."""

        self.execute_input()
        return "break"

    def execute_input(self) -> None:
        """Получить, разобрать и выполнить команду из поля ввода."""

        raw_command = self.command_entry.get()
        self.command_entry.delete(0, tk.END)
        self.history_index = None

        self._append(raw_command + "\n", "command")
        if raw_command.strip():
            self.history.append(raw_command)

        parts = self._parse_input(raw_command)
        if parts is None:
            self._show_prompt()
            return
        if not parts:
            self._show_prompt()
            return

        command, *arguments = parts
        if command == "exit":
            self._execute_exit(arguments)
            return

        handlers: dict[str, Callable[[list[str]], None]] = {
            "ls": self._command_stub,
            "cd": self._command_stub,
        }
        handler = handlers.get(command)
        if handler is None:
            self._append(
                f"Ошибка: неизвестная команда '{command}'.\n",
                "error",
            )
        else:
            handler([command, *arguments])
        self._show_prompt()

    def _parse_input(self, raw_command: str) -> Optional[list[str]]:
        """Разобрать ввод или вывести сообщение об ошибке."""

        try:
            return CommandParser.parse(raw_command)
        except ValueError as error:
            self._append(
                f"Ошибка разбора команды: {error}\n",
                "error",
            )
            return None

    def _execute_exit(self, arguments: list[str]) -> None:
        """Закрыть окно или сообщить о лишних аргументах."""

        if arguments:
            self._append(
                "Ошибка: команда exit не принимает аргументы.\n",
                "error",
            )
            self._show_prompt()
            return
        self.exit()

    def _command_stub(self, parts: list[str]) -> None:
        """Вывести имя команды-заглушки и её аргументы."""

        command, *arguments = parts
        if arguments:
            arguments_text = " ".join(arguments)
            self._append(
                f"{command}: заглушка; аргументы: {arguments_text}\n",
                "result",
            )
        else:
            self._append(
                f"{command}: заглушка; аргументов нет\n",
                "result",
            )

    def _show_previous_command(self, _event: tk.Event) -> str:
        """Показать предыдущую команду из истории."""

        if not self.history:
            return "break"
        if self.history_index is None:
            self.history_index = len(self.history)
        self.history_index = max(0, self.history_index - 1)
        self._replace_entry(self.history[self.history_index])
        return "break"

    def _show_next_command(self, _event: tk.Event) -> str:
        """Показать следующую команду из истории."""

        if self.history_index is None:
            return "break"
        self.history_index += 1
        if self.history_index >= len(self.history):
            self.history_index = None
            self._replace_entry("")
        else:
            self._replace_entry(self.history[self.history_index])
        return "break"

    def _replace_entry(self, value: str) -> None:
        """Заменить текст поля ввода и поставить курсор в конец."""

        self.command_entry.delete(0, tk.END)
        self.command_entry.insert(0, value)
        self.command_entry.icursor(tk.END)

    def exit(self, _event: Optional[tk.Event] = None) -> None:
        """Закрыть приложение, если оно ещё работает."""

        if self.running:
            self.running = False
            self.root.destroy()

    def run(self) -> None:
        """Передать управление циклу событий Tk."""

        self.command_entry.focus_set()
        self.root.mainloop()


def main() -> None:
    """Создать окно приложения и запустить эмулятор."""

    root = tk.Tk()
    ShellEmulator(root).run()


if __name__ == "__main__":
    main()
