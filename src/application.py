"""Tkinter-интерфейс эмулятора и интеграция конфигурации этапа 2."""

from __future__ import annotations

import getpass
import socket
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from .commands import CommandProcessor, CommandResult
from .config import AppConfig, parse_arguments
from .startup import SCRIPT_ERROR_MESSAGE, ScriptEvent, StartupScriptRunner
from .vfs import VfsError, VirtualFileSystem


VFS_TITLE_FALLBACK = "vfs_stage1"
WINDOW_WIDTH = 960
WINDOW_HEIGHT = 620
MIN_WINDOW_WIDTH = 640
MIN_WINDOW_HEIGHT = 420
PADDING = 12
BUTTON_WIDTH = 4
ENTRY_IPADY = 7


class ShellWindow:
    """Показывать диалог эмулятора в графическом окне."""

    def __init__(
        self,
        root: tk.Tk,
        config: AppConfig,
        vfs: VirtualFileSystem,
        load_error: str | None = None,
    ) -> None:
        """Создать окно с заданной конфигурацией запуска."""

        self.root = root
        self.config = config
        self.vfs = vfs
        self.load_error = load_error
        self.processor = CommandProcessor(vfs)
        self.history: list[str] = []
        self.history_index: int | None = None
        self.running = True
        self.vfs_name = vfs.name or VFS_TITLE_FALLBACK

        self._configure_window()
        self._configure_style()
        self._build_interface()
        self._write_welcome()

    def _configure_window(self) -> None:
        """Настроить размер, заголовок и обработчик закрытия окна."""

        self.root.title(f"Эмулятор оболочки ОС - {self.vfs_name}")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.root.configure(bg="#202124")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    @staticmethod
    def _configure_style() -> None:
        """Настроить стиль кнопки запуска."""

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
        """Создать области вывода и ввода команды."""

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main = ttk.Frame(self.root, padding=PADDING)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)
        self._build_output_area(main)
        self._build_command_area(main)

    def _build_output_area(self, parent: ttk.Frame) -> None:
        """Создать прокручиваемое поле журнала."""

        frame = ttk.Frame(parent)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.output = tk.Text(
            frame,
            wrap="word",
            state="disabled",
            background="#111315",
            foreground="#e8eaed",
            insertbackground="#e8eaed",
            selectbackground="#3c4043",
            relief="flat",
            borderwidth=0,
            padx=14,
            pady=PADDING,
            font=("Consolas", 11),
        )
        self.output.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(frame, orient="vertical")
        scrollbar.grid(row=0, column=1, sticky="ns")
        scrollbar.configure(command=self.output.yview)
        self.output.configure(yscrollcommand=scrollbar.set)
        self._configure_output_tags()

    def _configure_output_tags(self) -> None:
        """Назначить цвета сообщениям журнала."""

        self.output.tag_configure("prompt", foreground="#8ab4f8")
        self.output.tag_configure("command", foreground="#fbbc04")
        self.output.tag_configure("error", foreground="#f28b82")
        self.output.tag_configure("info", foreground="#9aa0a6")
        self.output.tag_configure("result", foreground="#e8eaed")

    def _build_command_area(self, parent: ttk.Frame) -> None:
        """Создать поле ввода, историю команд и кнопку запуска."""

        frame = ttk.Frame(parent, padding=(0, PADDING, 0, 0))
        frame.grid(row=1, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)
        self.command_entry = ttk.Entry(frame, font=("Consolas", 12))
        self.command_entry.grid(row=0, column=0, sticky="ew", ipady=ENTRY_IPADY)
        self.command_entry.bind("<Return>", self._on_submit)
        self.command_entry.bind("<Up>", self._show_previous)
        self.command_entry.bind("<Down>", self._show_next)
        button = ttk.Button(
            frame,
            text=">",
            width=BUTTON_WIDTH,
            style="Run.TButton",
            command=self.execute_input,
        )
        button.grid(row=0, column=1, padx=(8, 0), sticky="ns")

    def _write_welcome(self) -> None:
        """Вывести параметры запуска и приглашение пользователя."""

        for line in self.config.debug_lines():
            self._append(line + "\n", "info")
        if self.load_error:
            self._append(self.load_error + "\n", "error")
        else:
            self._append(f"VFS загружена в память: {self.vfs.name}\n", "info")
        self._append("Команды: ls, cd, clear, uptime, exit\n\n", "info")
        self._show_prompt()

    def _append(self, text: str, tag: str = "result") -> None:
        """Добавить текст в журнал и перейти к последней строке."""

        self.output.configure(state="normal")
        self.output.insert(tk.END, text, tag)
        self.output.configure(state="disabled")
        self.output.see(tk.END)

    @staticmethod
    def _prompt() -> str:
        """Сформировать приглашение из имени пользователя и хоста ОС."""

        username = getpass.getuser() or "user"
        hostname = socket.gethostname() or "localhost"
        return f"{username}@{hostname}:~$ "

    def _show_prompt(self) -> None:
        """Показать приглашение в журнале."""

        self._append(self._prompt(), "prompt")

    def _on_submit(self, _event: tk.Event) -> str:
        """Запустить команду по нажатию Enter."""

        self.execute_input()
        return "break"

    def execute_input(self) -> None:
        """Выполнить команду из поля ввода и отобразить результат."""

        command = self.command_entry.get()
        self.command_entry.delete(0, tk.END)
        self.history_index = None
        if command.strip():
            self.history.append(command)
        self._render_command(command, self.processor.execute(command))

    def _render_command(
        self, command: str, result: CommandResult, show_prompt: bool = True,
    ) -> None:
        """Показать ввод, результат и новое приглашение."""

        self._append(command + "\n", "command")
        if result.clear:
            self._clear_output()
        tag = "error" if result.error else "result"
        for line in result.lines:
            self._append(line + "\n", tag)
        if result.should_exit:
            self.close()
        elif show_prompt:
            self._show_prompt()

    def _run_startup_script(self) -> None:
        """Выполнить стартовый скрипт после создания интерфейса."""

        if self.config.script_path is None:
            return
        runner = StartupScriptRunner(self.config.script_path)
        for event in runner.run(self.processor.execute):
            self._render_script_event(event)
            if event.result.should_exit:
                break
        if runner.has_errors:
            self._append(SCRIPT_ERROR_MESSAGE + "\n", "error")
        if self.running:
            self._show_prompt()

    def _render_script_event(self, event: ScriptEvent) -> None:
        """Показать строку скрипта так же, как интерактивный ввод."""

        if event.line_number:
            self._append(f"[script:{event.line_number}] ", "info")
        self._render_command(event.text, event.result, show_prompt=False)

    def _clear_output(self) -> None:
        """Очистить журнал по команде ``clear`` на следующих этапах."""

        self.output.configure(state="normal")
        self.output.delete("1.0", tk.END)
        self.output.configure(state="disabled")

    def _show_previous(self, _event: tk.Event) -> str:
        """Показать предыдущую команду из истории."""

        if not self.history:
            return "break"
        if self.history_index is None:
            self.history_index = len(self.history)
        self.history_index = max(0, self.history_index - 1)
        self._replace_entry(self.history[self.history_index])
        return "break"

    def _show_next(self, _event: tk.Event) -> str:
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
        """Заменить содержимое поля ввода."""

        self.command_entry.delete(0, tk.END)
        self.command_entry.insert(0, value)
        self.command_entry.icursor(tk.END)

    def close(self, _event: tk.Event | None = None) -> None:
        """Закрыть приложение один раз."""

        if self.running:
            self.running = False
            self.root.destroy()

    def run(self) -> None:
        """Запустить стартовый скрипт и цикл событий Tk."""

        self._run_startup_script()
        if self.running:
            self.command_entry.focus_set()
            self.root.mainloop()


def run_application(arguments: list[str] | None = None) -> None:
    """Разобрать конфигурацию и запустить графическое приложение."""

    config = parse_arguments(arguments)
    vfs, load_error = _load_vfs(config.vfs_path)
    root = tk.Tk()
    ShellWindow(root, config, vfs, load_error).run()


def _load_vfs(path: Path) -> tuple[VirtualFileSystem, str | None]:
    """Загрузить VFS или вернуть пустую VFS с сообщением об ошибке."""

    try:
        return VirtualFileSystem.from_xml(path), None
    except VfsError as error:
        name = path.stem or VFS_TITLE_FALLBACK
        return VirtualFileSystem.empty(name), str(error)
