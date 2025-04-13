from itertools import count
from unittest.mock import MagicMock

from undo_stack import UndoCommand


class MockUndoCommand(UndoCommand):
    mock_id = count()

    def __init__(self, *, do_try_merge=None):
        super().__init__()
        self.undo_mock = MagicMock()
        self.undo_async_mock = MagicMock()
        self.redo_mock = MagicMock()
        self.redo_async_mock = MagicMock()
        self.merge_with_mock = MagicMock(return_value=False)
        self._text = f"{self.__class__} {next(self.mock_id)}"
        self._do_try_merge = do_try_merge

    def undo(self, *args, **kwargs) -> None:
        self.undo_mock(*args, **kwargs)

    def redo(self, *args, **kwargs):
        self.redo_mock(*args, **kwargs)

    async def undo_async(self) -> None:
        self.undo_async_mock()

    async def redo_async(self) -> None:
        self.redo_async_mock()

    def merge_with(self, *args, **kwargs) -> bool:
        return self.merge_with_mock(*args, **kwargs)

    def do_try_merge(self, command: "UndoCommand") -> bool:
        if self._do_try_merge is None:
            return super().do_try_merge(command)
        return self._do_try_merge

    def obsolete_after_call(self, mock: MagicMock):
        def set_obsolete(*_):
            self._is_obsolete = True
            return True

        mock.side_effect = set_obsolete
