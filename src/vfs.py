"""XML-загрузчик виртуальной файловой системы, работающей в памяти."""

from __future__ import annotations

import base64
import binascii
import xml.etree.ElementTree as element_tree
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_DIRECTORY_MODE = 0o755
DEFAULT_FILE_MODE = 0o644
MIN_MODE = 0
MAX_MODE = 0o777
PERMISSION_BITS = (
    0o400, 0o200, 0o100, 0o040, 0o020,
    0o010, 0o004, 0o002, 0o001,
)
PERMISSION_CHARS = "rwxrwxrwx"


class VfsError(ValueError):
    """Ошибка структуры, пути или содержимого виртуальной ФС."""


@dataclass
class VfsNode:
    """Узел дерева VFS: файл или каталог."""

    name: str
    is_directory: bool
    content: bytes = b""
    mode: int = DEFAULT_FILE_MODE
    parent: "VfsNode | None" = field(default=None, repr=False)
    children: dict[str, "VfsNode"] = field(default_factory=dict)

    @property
    def path(self) -> str:
        """Вернуть абсолютный путь узла в VFS."""

        if self.parent is None:
            return "/"
        parent_path = self.parent.path.rstrip("/")
        return f"{parent_path}/{self.name}"

    @property
    def size(self) -> int:
        """Вернуть размер файла в байтах или размер каталога."""

        if not self.is_directory:
            return len(self.content)
        return sum(child.size for child in self.children.values())


class VirtualFileSystem:
    """Дерево VFS, загруженное из XML и изменяемое только в памяти."""

    def __init__(self, name: str) -> None:
        """Создать пустую VFS с указанным именем."""

        self.name = name
        self.root = VfsNode(
            name="",
            is_directory=True,
            mode=DEFAULT_DIRECTORY_MODE,
        )
        self.current = self.root

    @classmethod
    def empty(cls, name: str) -> "VirtualFileSystem":
        """Создать пустую VFS для продолжения работы после ошибки загрузки."""

        return cls(name or "vfs")

    @classmethod
    def from_xml(cls, path: Path) -> "VirtualFileSystem":
        """Загрузить VFS из XML, не изменяя исходный файл."""

        try:
            root_element = element_tree.parse(path).getroot()
        except (OSError, element_tree.ParseError) as error:
            raise VfsError(f"Ошибка загрузки VFS '{path}': {error}") from error

        if root_element.tag != "vfs":
            raise VfsError("Корневой элемент VFS должен называться vfs")
        name = root_element.attrib.get("name") or path.stem
        filesystem = cls(name)
        for child_element in root_element:
            filesystem._add_element(child_element, filesystem.root)
        return filesystem

    def _add_element(
        self,
        element: element_tree.Element,
        parent: VfsNode,
    ) -> VfsNode:
        """Преобразовать XML-элемент в узел дерева."""

        if element.tag not in {"directory", "file"}:
            raise VfsError(f"Неизвестный элемент VFS: {element.tag}")
        name = element.attrib.get("name", "")
        self._validate_name(name)
        if name in parent.children:
            raise VfsError(f"Дублирующееся имя VFS: {name}")

        is_directory = element.tag == "directory"
        default_mode = (
            DEFAULT_DIRECTORY_MODE if is_directory else DEFAULT_FILE_MODE
        )
        node = VfsNode(
            name=name,
            is_directory=is_directory,
            content=b"" if is_directory else self._file_content(element),
            mode=self._parse_mode(element.attrib.get("mode"), default_mode),
            parent=parent,
        )
        parent.children[name] = node
        if is_directory:
            for child_element in element:
                self._add_element(child_element, node)
        return node

    @staticmethod
    def _validate_name(name: str) -> None:
        """Проверить имя узла и запретить обход дерева через имя."""

        if not name or name in {".", ".."} or "/" in name:
            raise VfsError(f"Недопустимое имя VFS: {name!r}")

    @staticmethod
    def _parse_mode(value: str | None, default: int) -> int:
        """Преобразовать восьмеричное право доступа в число."""

        if value is None:
            return default
        try:
            mode = int(value, 8)
        except ValueError as error:
            raise VfsError(f"Недопустимый режим доступа: {value}") from error
        if not MIN_MODE <= mode <= MAX_MODE:
            raise VfsError(f"Недопустимый режим доступа: {value}")
        return mode

    @staticmethod
    def _file_content(element: element_tree.Element) -> bytes:
        """Прочитать текстовое или base64-содержимое XML-файла."""

        text = element.text or ""
        encoding = element.attrib.get("encoding", "text")
        if encoding == "text":
            return text.encode("utf-8")
        if encoding == "base64":
            try:
                return base64.b64decode(text, validate=True)
            except (binascii.Error, ValueError) as error:
                raise VfsError("Некорректные base64-данные VFS") from error
        raise VfsError(f"Неизвестная кодировка VFS: {encoding}")

    def resolve(self, path: str, start: VfsNode | None = None) -> VfsNode:
        """Найти узел по абсолютному или относительному пути VFS."""

        absolute_path = path.startswith("/") or path.startswith("~")
        current = self.root if absolute_path else (start or self.current)
        parts = path.replace("~", "", 1).split("/")
        for part in parts:
            if not part or part == ".":
                continue
            if part == "..":
                current = current.parent or self.root
                continue
            if not current.is_directory or part not in current.children:
                raise VfsError(f"Путь не найден: {path}")
            current = current.children[part]
        return current

    def change_directory(self, path: str) -> VfsNode:
        """Изменить текущий каталог в памяти."""

        node = self.resolve(path)
        if not node.is_directory:
            raise VfsError(f"Не является каталогом: {path}")
        self.current = node
        return node

    def list_directory(self, path: str = ".") -> list[VfsNode]:
        """Вернуть отсортированное содержимое каталога или сам файл."""

        node = self.resolve(path)
        if not node.is_directory:
            return [node]
        return sorted(
            node.children.values(),
            key=lambda item: item.name.lower(),
        )

    def is_inside(self, node: VfsNode, ancestor: VfsNode) -> bool:
        """Проверить, находится ли узел внутри другого узла."""

        current: VfsNode | None = node
        while current is not None:
            if current is ancestor:
                return True
            current = current.parent
        return False

    def remove(self, node: VfsNode) -> None:
        """Удалить узел только из дерева VFS в памяти."""

        if node.parent is None:
            raise VfsError("Нельзя удалить корень VFS")
        if self.is_inside(self.current, node):
            self.current = node.parent
        del node.parent.children[node.name]

    def set_mode(self, node: VfsNode, mode: int) -> None:
        """Изменить права узла только в памяти."""

        if not MIN_MODE <= mode <= MAX_MODE:
            raise VfsError(f"Недопустимый режим доступа: {mode:o}")
        node.mode = mode


def parse_mode(value: str) -> int:
    """Преобразовать пользовательский восьмеричный режим доступа."""

    try:
        mode = int(value, 8)
    except ValueError as error:
        raise VfsError(f"Недопустимый режим доступа: {value}") from error
    if not MIN_MODE <= mode <= MAX_MODE:
        raise VfsError(f"Недопустимый режим доступа: {value}")
    return mode


def format_mode(node: VfsNode) -> str:
    """Сформировать UNIX-подобное представление типа и прав узла."""

    kind = "d" if node.is_directory else "-"
    permissions = "".join(
        char if node.mode & bit else "-"
        for bit, char in zip(PERMISSION_BITS, PERMISSION_CHARS)
    )
    return kind + permissions
