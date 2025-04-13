from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from .signal_container import SignalContainer

if TYPE_CHECKING:
    from .undo_group import UndoGroup

from .signal import Signal
from .undo_command import UndoCommand, UndoCommandGroup


class UndoStack(SignalContainer):
    """
    Qt like undo stack implementation.
    Adapted from : https://github.com/qt/qtbase/blob/dev/src/gui/util/qundostack.cpp
    """

    can_redo_changed = Signal(bool)
    can_undo_changed = Signal(bool)
    clean_changed = Signal(bool)
    index_changed = Signal(int)
    redo_text_changed = Signal(str)
    undo_text_changed = Signal(str)

    def __init__(self, *, undo_limit=0, undo_group: UndoGroup | None = None):
        self._index = 0
        self._clean_index = 0
        self._group: UndoGroup | None = None
        self._undo_limit = undo_limit
        self._command_list: list[UndoCommand] = []
        self._undo_command_group: UndoCommandGroup | None = None

        if undo_group:
            undo_group.add_stack(self)

    def push(self, command: UndoCommand):
        """Pushes a command onto the stack."""
        if self._undo_command_group is not None:
            self._undo_command_group.push(command)
            return

        if command.is_obsolete():
            command.redo()

        self._push_impl(command)

    async def push_async(self, command: UndoCommand):
        """Pushes a command onto the stack."""
        if self._undo_command_group is not None:
            await self._undo_command_group.push_async(command)
            return

        if command.is_obsolete():
            await command.redo_async()

        self._push_impl(command)

    def _push_impl(self, command):
        current = self._current_command()
        self._pop_outdated_commands()
        try_merge = self._do_try_merge(command, current)
        if try_merge and current.merge_with(command):
            if current and current.is_obsolete():
                self._command_list.pop()
                self._set_index(self._index - 1, False)
            else:
                self._trigger_index_changed_signals()
        elif not command.is_obsolete():
            self._command_list.append(command)
            self._set_index(self._index + 1, False)
        self._update_undo_limit()

    def _do_try_merge(self, command: UndoCommand, cur: UndoCommand | None) -> bool:
        return command.do_try_merge(cur) and self._index != self._clean_index

    def _pop_outdated_commands(self):
        while self._index < len(self._command_list):
            self._command_list.pop()
        if self._clean_index > self._index:
            self._clean_index = -1

    def _current_command(self) -> UndoCommand:
        return self._command_list[self._index - 1] if self._index > 0 else None

    def _set_index(self, idx: int, clean: bool) -> None:
        with self._trigger_index_if_changed(), self._trigger_clean_if_changed():
            self._index = idx
            if clean:
                self._clean_index = self._index

    def _trigger_index_changed_signals(self):
        self.index_changed(self._index)
        self.can_undo_changed(self.can_undo())
        self.can_redo_changed(self.can_redo())
        self.undo_text_changed(self.undo_text())
        self.redo_text_changed(self.redo_text())

    def _trigger_clean_changed(self):
        self.clean_changed(self.is_clean())

    @contextmanager
    def _trigger_index_if_changed(self):
        idx = self.index()
        yield
        if idx != self.index():
            self._trigger_index_changed_signals()

    @contextmanager
    def _trigger_clean_if_changed(self):
        was_clean = self.is_clean()
        yield
        if was_clean != self.is_clean():
            self._trigger_clean_changed()

    def _update_undo_limit(self):
        if self._undo_limit <= 0 or self._undo_limit >= len(self._command_list):
            return

        del_count = len(self._command_list) - self._undo_limit

        for _ in range(del_count):
            self._command_list.pop(0)

        self._index -= del_count
        self._clean_index = max(-1, self._clean_index - del_count)
        return

    def _undo_index(self) -> int:
        return self._index - 1

    def _redo_index(self) -> int:
        return self._index

    def undo(self):
        """Undoes the last command."""
        if not self.can_undo():
            return

        idx = self._undo_index()
        command = self._command_list[idx]
        self._apply_undo_redo(idx, idx, command, command.undo)

    def redo(self):
        """Redoes the last undone command."""
        if not self.can_redo():
            return

        idx = self._redo_index()
        command = self._command_list[idx]
        self._apply_undo_redo(idx, idx + 1, command, command.redo)

    async def undo_async(self):
        """Undoes the last command."""
        if not self.can_undo():
            return

        idx = self._undo_index()
        command = self._command_list[idx]
        await self._apply_undo_redo_async(idx, idx, command, command.undo_async)

    async def redo_async(self):
        """Redoes the last undone command."""
        if not self.can_redo():
            return

        idx = self._redo_index()
        command = self._command_list[idx]
        await self._apply_undo_redo_async(idx, idx + 1, command, command.redo_async)

    def _apply_undo_redo(
        self, idx: int, next_idx: int, command: UndoCommand, undo_redo_f: Callable
    ):
        if not command.is_obsolete():
            undo_redo_f()
        self._update_index_and_handle_obsolete_commands(command, idx, next_idx)

    def _update_index_and_handle_obsolete_commands(self, command, idx, next_idx):
        if command.is_obsolete():
            self._command_list.pop(idx)
            next_idx = idx

            if self._clean_index > idx:
                self.reset_clean()
        self._set_index(next_idx, False)

    async def _apply_undo_redo_async(
        self, idx: int, next_idx: int, command: UndoCommand, undo_redo_f: Callable
    ):
        if not command.is_obsolete():
            await undo_redo_f()
        self._update_index_and_handle_obsolete_commands(command, idx, next_idx)

    def can_undo(self) -> bool:
        """Checks if undo is possible."""
        return self._index > 0 and self._undo_command_group is None

    def can_redo(self) -> bool:
        """Checks if redo is possible."""
        return (
            self._index < len(self._command_list) and self._undo_command_group is None
        )

    def undo_text(self) -> str:
        """Returns the text description of the next undo command."""
        if not self.can_undo():
            return ""
        return self._command_list[self._undo_index()].text()

    def redo_text(self) -> str:
        """Returns the text description of the next redo command."""
        if not self.can_redo():
            return ""
        return self._command_list[self._redo_index()].text()

    def set_clean(self) -> None:
        """Marks the stack as clean."""
        self._set_index(self._index, True)

    def set_active(self, is_active: bool) -> None:
        if not self._group:
            return
        if is_active:
            self._group.set_active_stack(self)
        elif self.is_active():
            self._group.set_active_stack(None)

    def is_active(self):
        if not self._group:
            return True
        return self._group.active_stack() == self

    def is_clean(self) -> bool:
        """Checks if the stack is clean."""
        return self._clean_index == self._index

    def clear(self) -> None:
        """Clears all commands from the stack."""
        with self._trigger_index_if_changed(), self._trigger_clean_if_changed():
            self._command_list.clear()
            self._index = 0
            self._clean_index = 0

    def n_commands(self) -> int:
        """Returns the number of commands in the stack."""
        return len(self._command_list)

    def index(self) -> int:
        """Gets the current index in the stack."""
        return self._index

    def set_index(self, idx: int) -> None:
        """Sets the current index in the stack."""
        idx = max(0, min(idx, self.n_commands()))
        with self.emit_signals_once():
            while self._index < idx:
                self.redo()

            while self._index > idx:
                self.undo()

    def clean_index(self) -> int:
        return self._clean_index

    def set_undo_limit(self, limit: int) -> None:
        self._undo_limit = limit
        self._update_undo_limit()

    def undo_limit(self) -> int:
        return self._undo_limit

    def reset_clean(self) -> None:
        with self._trigger_clean_if_changed():
            self._clean_index = -1

    def set_group(self, undo_group: UndoGroup | None) -> None:
        self._group = undo_group

    def group(self) -> UndoGroup | None:
        return self._group

    @contextmanager
    def group_undo_commands(self, text: str = "") -> Generator:
        prev_group = self._undo_command_group
        new_group = UndoCommandGroup(text)
        self._undo_command_group = new_group
        yield
        self._undo_command_group = prev_group
        if prev_group is not None:
            prev_group.push(new_group)
        else:
            self.push(new_group)

    def trigger_all_signals(self):
        self._trigger_index_changed_signals()
        self._trigger_clean_changed()

    def get_stack_texts(self) -> list[str]:
        return [cmd.text() for cmd in self._command_list]
