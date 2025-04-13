from abc import ABC, abstractmethod


class UndoCommand(ABC):
    """
    Base class for undo commands.
    """

    def __init__(self):
        self._id = None
        self._is_obsolete = False
        self._text = ""

    @abstractmethod
    def undo(self) -> None:
        pass

    @abstractmethod
    def redo(self) -> None:
        pass

    async def undo_async(self) -> None:
        self.undo()

    async def redo_async(self) -> None:
        self.redo()

    def merge_with(self, _command: "UndoCommand") -> bool:
        """
        Try to merge current command with provided input command.
        If merge is successful, only one undo action will be kept in the stack.
        """
        return False

    def do_try_merge(self, command: "UndoCommand") -> bool:
        if not isinstance(command, UndoCommand):
            return False

        return self._id is not None and self._id == command._id

    def is_obsolete(self) -> bool:
        return self._is_obsolete

    def text(self):
        return self._text


class UndoCommandGroup(UndoCommand):
    """
    Allows to group multiple commands into one undo / redo command.
    Undo / redo text is the text of the group.

    Used implicitly from UndoStack's group_undo_commands context manager.
    """

    def __init__(self, text=""):
        from .undo_stack import UndoStack

        super().__init__()
        self._text = text
        self._stack = UndoStack()

    def undo(self) -> None:
        while self._stack.can_undo():
            self._stack.undo()

    def redo(self) -> None:
        while self._stack.can_redo():
            self._stack.redo()

    async def undo_async(self) -> None:
        while self._stack.can_undo():
            await self._stack.undo_async()

    async def redo_async(self) -> None:
        while self._stack.can_redo():
            await self._stack.redo_async()

    def is_obsolete(self) -> bool:
        return self._stack.n_commands() == 0

    def push(self, cmd: "UndoCommand") -> None:
        self._stack.push(cmd)

    async def push_async(self, cmd: "UndoCommand") -> None:
        await self._stack.push_async(cmd)
