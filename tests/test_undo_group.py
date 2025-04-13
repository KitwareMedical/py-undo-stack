import gc

import pytest

from tests.mock_undo_command import MockUndoCommand
from undo_stack import SignalContainerSpy, UndoGroup, UndoStack


@pytest.fixture
def undo_group():
    return UndoGroup()


@pytest.fixture
def group_spy(undo_group):
    return SignalContainerSpy(undo_group)


def test_can_add_and_remove_stacks(undo_group):
    u1 = UndoStack()
    u2 = UndoStack()
    undo_group.add_stack(u1)
    undo_group.add_stack(u2)

    assert u1.group() == undo_group
    assert u2.group() == undo_group

    undo_group.remove_stack(u2)
    assert u2.group() is None
    assert undo_group.n_stacks == 1


def test_on_delete_stack_removes_itself_from_group(undo_group):
    u1 = UndoStack()
    undo_group.add_stack(u1)
    del u1
    gc.collect()
    assert undo_group.n_stacks == 0


def test_has_one_active_stack(undo_group):
    u1 = UndoStack()
    u2 = UndoStack()
    undo_group.add_stack(u1)
    undo_group.add_stack(u2)

    u1.set_active(True)
    u2.set_active(True)

    assert undo_group.active_stack() == u2
    assert not u1.is_active()


def test_forwards_signals_from_active(undo_group, group_spy):
    u1 = UndoStack()
    u2 = UndoStack()
    undo_group.add_stack(u1)
    undo_group.add_stack(u2)
    u2.set_active(True)

    group_spy[undo_group.active_stack_changed].assert_called_once_with(u2)

    u1.push(MockUndoCommand())
    group_spy[undo_group.undo_text_changed].assert_not_called()

    c1 = MockUndoCommand()
    u2.push(c1)
    group_spy[undo_group.undo_text_changed].assert_called_once()
    c2 = MockUndoCommand()
    u2.push(c2)
    undo_group.undo()

    assert undo_group.can_undo()
    assert undo_group.can_redo()
    assert not undo_group.is_clean()
    assert undo_group.undo_text() == c1.text()
    assert undo_group.redo_text() == c2.text()

    undo_group.redo()
    assert undo_group.undo_text() == c2.text()


def test_undo_redo_without_active_does_nothing(undo_group):
    undo_group.undo()
    undo_group.redo()


def test_add_remove_none_does_nothing(undo_group):
    undo_group.add_stack(None)
    undo_group.remove_stack(None)


def test_setting_stack_inactive_removes_from_group_active(undo_group):
    u1 = UndoStack(undo_group=undo_group)
    u1.set_active(True)
    assert undo_group.active_stack() == u1
    u1.set_active(False)
    assert undo_group.active_stack() is None


def test_setting_stack_active_deactivates_previous(undo_group):
    u1 = UndoStack(undo_group=undo_group)
    u2 = UndoStack(undo_group=undo_group)
    u1.set_active(True)
    u2.set_active(True)
    assert not u1.is_active()
    assert undo_group.active_stack() == u2


def test_set_active_without_group_does_nothing(undo_group):
    u1 = UndoStack()
    u1.set_active(True)
    assert undo_group.active_stack() is None


def test_stack_without_groups_are_considered_active():
    u1 = UndoStack()
    assert u1.is_active()


@pytest.mark.asyncio
async def test_is_compatible_with_async(undo_group):
    mock = MockUndoCommand()
    u1 = UndoStack(undo_group=undo_group)
    u1.set_active(True)
    await u1.push_async(mock)
    await undo_group.undo_async()
    await undo_group.redo_async()

    mock.undo_async_mock.assert_called_once()
    mock.redo_async_mock.assert_called_once()
