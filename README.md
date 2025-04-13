# py-undo-stack

This library implements a pure python undo / redo stack pattern.

## Overview

This library revolves around the concept of UndoStack and UndoCommand and is an
implementation of the Command pattern. When an action needs to be undoable, an
UndoCommand is created which encapsulates how to go from an undo state to a redo
state.

UndoCommands are pushed to the UndoStack and the UndoStack is responsible for
managing the sequences of undo / redo and the stack size depending on what is
pushed on the stack.

### UndoGroup

UndoGroup can be used to manage multiple UndoStack. One stack can be active at
once per UndoGroup. When calling the UndoGroup API, the calls are delegated to
the active stack for processing.

### Signal

Signal class provides a basic signal / slot implementation. Signals are
triggered in the UndoStack and UndoGroup to inform that their states have
changed. The signals are emitted regardless of async or not async variations.

### Compression

UndoCommand provides a mechanism to compress commands with one another. Commands
pushed to the stack try to merge with previous commands provided that their
`do_try_merge` methods return True.

When commands are merged, the pushed command is discarded and only the previous
command is kept containing both commands information.

### Obsolete

Commands can be marked as obsolete. When a command is obsolete it will be
removed from the stack automatically.

### Async

UndoStack and UndoGroup provide async variations for their `push` `undo` and
`redo` methods. UndoCommand provides async variations for its `undo` and `redo`
methods.

When async undo / redo methods are called, the actions are awaited.

## Examples

```python
"""
This example shows an example of undo / redo for mutating lists and dicts.
"""

import logging
from contextlib import contextmanager
from copy import deepcopy

from undo_stack import UndoCommand, UndoStack

logging.basicConfig(level=logging.DEBUG)


class ListDictUndoCommand(UndoCommand):
    """
    We create a command which will save the state of the object before and after.
    We also create a utility context manager to make usage easier in the code.
    """

    def __init__(self, obj_before, obj_after, obj):
        super().__init__()
        self._before = obj_before
        self._after = obj_after
        self._obj = obj

    def is_obsolete(self) -> bool:
        """
        If the before and after states are strictly the same, then we can discard this undo / redo.
        """
        return self._before == self._after

    def _restore(self, state) -> None:
        """Generic method to restore the state while keeping the original instance."""
        if isinstance(self._obj, dict):
            self._obj.clear()
            self._obj.update(state)
        elif isinstance(self._obj, list):
            self._obj.clear()
            self._obj.extend(state)
        else:
            raise NotImplementedError()

    def undo(self) -> None:
        """Restore the previous state."""
        self._restore(self._before)

    def redo(self) -> None:
        """Reapply the modified state."""
        self._restore(self._after)

    @classmethod
    @contextmanager
    def save_for_undo(cls, undo_stack: UndoStack, obj):
        """
        In the context manager, we save the state before, and state after yield.
        The before and after states will allow us to restore the state of the object.
        """
        before = deepcopy(obj)
        yield
        after = deepcopy(obj)
        undo_stack.push(cls(before, after, obj))


"""
In our basic application, we create one undo stack.
With this undo stack we will monitor the changes of a list and a dict.
"""

undo_stack = UndoStack()

a_list = []
a_dict = {}

# With our context manager, we can track changes to the dict and list
with ListDictUndoCommand.save_for_undo(undo_stack, a_dict):
    a_dict["hello"] = "world"

with ListDictUndoCommand.save_for_undo(undo_stack, a_list):
    a_list.append(42)

logging.info(undo_stack.n_commands())
# >>> 2

logging.info(undo_stack.can_undo())
# >>> True

# Our undo stack is ordered. Undoing will undo the latest undo on the stack which is the list append.
undo_stack.undo()
logging.info(a_list)
# >>> []

undo_stack.redo()
logging.info(a_list)
# >>> [42]

# We can undo further to reset the content of the dict
undo_stack.undo()
undo_stack.undo()

logging.info(a_dict)
# >>> {}

undo_stack.redo()
logging.info(a_dict)
# >>> {"hello": "world"}

# Pushing in the stack will make the list modification obsolete
with ListDictUndoCommand.save_for_undo(undo_stack, a_dict):
    a_dict["hello"] = str(reversed("world"))

logging.info(undo_stack.can_redo())
# >>> False
```

## Acknowledgments

This implementation is inspired by Qt's
[QUndoStack, QUndoCommand, QUndoGroup](https://doc.qt.io/qt-6/qundostack.html).
For usage in Qt based application, direct usage of Qt's classes is recommended.
