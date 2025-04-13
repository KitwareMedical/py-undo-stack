from __future__ import annotations

from typing import Optional
from weakref import ref

from .signal import Signal
from .signal_container import SignalContainer
from .undo_stack import UndoStack


class UndoGroup(SignalContainer):
    """
    Qt like undo group.
    """

    active_stack_changed = Signal(Optional[UndoStack])
    can_redo_changed = Signal(bool)
    can_undo_changed = Signal(bool)
    clean_changed = Signal(bool)
    index_changed = Signal(int)
    redo_text_changed = Signal(str)
    undo_text_changed = Signal(str)

    def __init__(self):
        self._active_stack: ref[UndoStack] | None = None
        self._stacks: list[ref[UndoStack]] = []

    def active_stack(self) -> UndoStack | None:
        self._remove_obsolete()
        return self._active_stack() if self.is_active_valid() else None

    def add_stack(self, stack: UndoStack | None) -> None:
        if stack is None:
            return

        stack.set_group(self)
        stack_ref = ref(stack)
        if stack_ref not in self._stacks:
            self._stacks.append(stack_ref)

    def can_redo(self) -> bool:
        return self._active_stack().can_redo() if self.is_active_valid() else False

    def can_undo(self) -> bool:
        return self._active_stack().can_undo() if self.is_active_valid() else False

    def is_clean(self) -> bool:
        return self._active_stack().is_clean() if self.is_active_valid() else True

    def redo_text(self) -> str:
        return self._active_stack().redo_text() if self.is_active_valid() else ""

    def remove_stack(self, stack: UndoStack | None) -> None:
        if not stack:
            return

        stack_ref = ref(stack)
        if stack_ref in self._stacks:
            self._stacks.remove(stack_ref)
            stack.set_group(None)

    def undo_text(self) -> str:
        return self._active_stack().undo_text() if self.is_active_valid() else ""

    def undo(self) -> None:
        if self.is_active_valid():
            self._active_stack().undo()

    def redo(self) -> None:
        if self.is_active_valid():
            self._active_stack().redo()

    async def undo_async(self) -> None:
        if self.is_active_valid():
            await self._active_stack().undo_async()

    async def redo_async(self) -> None:
        if self.is_active_valid():
            await self._active_stack().redo_async()

    def set_active_stack(self, stack: UndoStack | None) -> None:
        stack_ref = ref(stack) if stack else None
        if stack_ref == self._active_stack:
            return

        self.add_stack(stack)
        self._set_active_connected(False)
        self._active_stack = stack_ref
        self._set_active_connected(True)
        self.active_stack_changed(stack)

    def _set_active_connected(self, is_connected):
        if not self.is_active_valid():
            return

        for stack_s in self._active_stack().signals():
            for group_s in self.signals():
                if stack_s.name == group_s.name:
                    if is_connected:
                        stack_s.connect(group_s)
                    else:
                        stack_s.disconnect(group_s)

    @property
    def n_stacks(self) -> int:
        self._remove_obsolete()
        return len(self._stacks)

    def _remove_obsolete(self):
        self._stacks = [s for s in self._stacks if s()]
        if not self.is_active_valid():
            self.set_active_stack(None)

    def is_active_valid(self):
        return self._active_stack is not None and self._active_stack() is not None
