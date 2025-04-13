from ._get_version import get_version
from .signal import Signal, Slot
from .signal_container import SignalContainer
from .signal_container_spy import SignalContainerSpy
from .undo_command import UndoCommand, UndoCommandGroup
from .undo_group import UndoGroup
from .undo_stack import UndoStack

__version__ = get_version("py-undo-stack")

__all__ = [
    "Signal",
    "SignalContainer",
    "SignalContainerSpy",
    "Slot",
    "UndoCommand",
    "UndoCommandGroup",
    "UndoGroup",
    "UndoStack",
]
