import asyncio

import pytest

from tests.mock_undo_command import MockUndoCommand
from undo_stack import SignalContainerSpy, UndoCommand, UndoStack


@pytest.fixture
def mock_command():
    return MockUndoCommand()


@pytest.fixture
def undo_stack():
    return UndoStack()


@pytest.fixture
def undo_spy(undo_stack):
    return SignalContainerSpy(undo_stack)


def test_applies_redo_for_obsolete_commands_on_push(undo_stack, mock_command):
    mock_command._is_obsolete = True
    undo_stack.push(mock_command)
    mock_command.redo_mock.assert_called_once()


def test_skips_redo_for_not_obsolete_on_push(undo_stack, mock_command):
    mock_command._is_obsolete = False
    undo_stack.push(mock_command)
    mock_command.redo_mock.assert_not_called()


def test_undo_redo_calls_command_undo(undo_stack, mock_command):
    undo_stack.push(mock_command)
    assert undo_stack.n_commands() == 1

    undo_stack.undo()
    mock_command.undo_mock.assert_called_once()

    undo_stack.redo()
    mock_command.redo_mock.assert_called_once()


class ListAppendCommand(UndoCommand):
    def __init__(self, a_list: list, value):
        super().__init__()
        self._list = a_list
        self._value = value
        self.redo()

    def undo(self) -> None:
        self._list.pop()

    def redo(self) -> None:
        self._list.append(self._value)


def test_by_default_commands_merge_with_is_false():
    a_list = []
    cmd = ListAppendCommand(a_list, 1)
    assert not cmd.merge_with(ListAppendCommand(a_list, 2))


def test_undo_redo_are_applied_in_order_of_push(undo_stack):
    a_list = []

    for i in range(10):
        undo_stack.push(ListAppendCommand(a_list, i))

    assert a_list == list(range(10))

    for _ in range(5):
        undo_stack.undo()

    assert a_list == list(range(5))

    for _ in range(3):
        undo_stack.redo()

    assert a_list == list(range(8))


def test_can_set_index_explicitly(undo_stack):
    a_list = []

    for i in range(10):
        undo_stack.push(ListAppendCommand(a_list, i))

    undo_stack.set_index(3)
    assert a_list == list(range(3))

    undo_stack.set_index(8)
    assert a_list == list(range(8))

    undo_stack.set_index(10)
    assert a_list == list(range(10))


def test_pushing_undo_pops_outdated_commands(undo_stack):
    a_list = []

    for i in range(10):
        undo_stack.push(ListAppendCommand(a_list, i))

    undo_stack.set_index(3)
    assert undo_stack.n_commands() == 10
    undo_stack.push(ListAppendCommand(a_list, 42))
    assert undo_stack.n_commands() == 4

    undo_stack.undo()
    assert a_list == [0, 1, 2]

    undo_stack.redo()
    assert a_list == [0, 1, 2, 42]


def test_pushing_with_merge_command_discards_second_when_obsolete(undo_stack):
    m1 = MockUndoCommand()
    m1._id = 1
    m2 = MockUndoCommand()
    m2._id = 1

    m1.merge_with_mock.return_value = True
    undo_stack.push(m1)
    undo_stack.push(m2)

    assert undo_stack.n_commands() == 1
    undo_stack.undo()
    m1.undo_mock.assert_called_once()


def test_commands_with_none_ids_cannot_be_merged(undo_stack):
    m1 = MockUndoCommand()
    m2 = MockUndoCommand()

    undo_stack.push(m1)
    undo_stack.push(m2)
    m1.merge_with_mock.assert_not_called()


def test_commands_with_different_ids_cannot_be_merged(undo_stack):
    m1 = MockUndoCommand()
    m1._id = 1
    m2 = MockUndoCommand()
    m2._id = 2

    undo_stack.push(m1)
    undo_stack.push(m2)
    m1.merge_with_mock.assert_not_called()


def test_can_be_marked_as_clean(undo_stack, undo_spy):
    assert undo_stack.is_clean()

    for _ in range(5):
        undo_stack.push(MockUndoCommand())

    assert not undo_stack.is_clean()
    undo_spy[undo_stack.clean_changed].assert_called_once_with(False)
    undo_spy.reset()

    undo_stack.set_index(2)
    undo_stack.set_clean()

    undo_spy[undo_stack.clean_changed].assert_called_once_with(True)
    undo_spy.reset()

    undo_stack.redo()
    assert not undo_stack.is_clean()
    undo_spy[undo_stack.clean_changed].assert_called_once_with(False)


def test_on_index_changes_triggers_change_signals(undo_stack, undo_spy):
    cmd = MockUndoCommand()
    cmd._text = "My Command"

    undo_stack.push(cmd)
    undo_spy[undo_stack.index_changed].assert_called_once_with(1)
    undo_spy[undo_stack.clean_changed].assert_called_once_with(False)
    undo_spy[undo_stack.undo_text_changed].assert_called_once_with("My Command")
    undo_spy[undo_stack.can_undo_changed].assert_called_once_with(True)
    undo_spy[undo_stack.can_redo_changed].assert_called_once_with(False)

    undo_spy.reset()
    undo_stack.undo()
    undo_spy[undo_stack.index_changed].assert_called_once_with(0)
    undo_spy[undo_stack.clean_changed].assert_called_once_with(True)
    undo_spy[undo_stack.undo_text_changed].assert_called_once_with("")
    undo_spy[undo_stack.redo_text_changed].assert_called_once_with("My Command")
    undo_spy[undo_stack.can_undo_changed].assert_called_once_with(False)
    undo_spy[undo_stack.can_redo_changed].assert_called_once_with(True)


def test_can_group_undo_commands(undo_stack):
    a_list = []

    with undo_stack.group_undo_commands("List group"):
        for i in range(10):
            undo_stack.push(ListAppendCommand(a_list, i))

    assert undo_stack.n_commands() == 1
    undo_stack.undo()
    assert a_list == []
    undo_stack.redo()
    assert a_list == list(range(10))


def test_grouped_undo_commands_in_recursion_is_grouped_in_one(undo_stack):
    a_list = []
    with undo_stack.group_undo_commands("List group"):
        for i in range(5):
            undo_stack.push(ListAppendCommand(a_list, i))

        with undo_stack.group_undo_commands("inner"):
            for i in range(5, 10):
                undo_stack.push(ListAppendCommand(a_list, i))

    assert undo_stack.n_commands() == 1
    undo_stack.undo()
    assert a_list == []
    undo_stack.redo()
    assert a_list == list(range(10))


def test_obsolete_groups_are_not_added_to_command(undo_stack):
    with undo_stack.group_undo_commands(), undo_stack.group_undo_commands():
        obsolete_cmd = MockUndoCommand()
        obsolete_cmd._is_obsolete = True
        undo_stack.push(obsolete_cmd)

    assert undo_stack.n_commands() == 0


def test_on_undo_after_push_fires_redo_changed(undo_stack, undo_spy):
    undo_stack.push(MockUndoCommand())
    undo_stack.undo()
    undo_spy.reset()
    undo_stack.push(MockUndoCommand())
    undo_spy[undo_stack.can_redo_changed].assert_called_once_with(False)


def test_limit_can_be_set(undo_stack):
    a_list = []
    assert undo_stack.undo_limit() == 0
    undo_stack.set_undo_limit(5)
    assert undo_stack.undo_limit() == 5

    for i in range(10):
        undo_stack.push(ListAppendCommand(a_list, i))

    assert undo_stack.n_commands() == 5
    undo_stack.set_index(0)
    assert a_list == list(range(5))
    undo_stack.set_index(undo_stack.n_commands())
    assert a_list == list(range(10))


def test_pushing_and_out_dating_clean_state_sets_unclean(undo_stack, undo_spy):
    for _ in range(5):
        undo_stack.push(MockUndoCommand())

    undo_spy.reset()
    undo_stack.set_clean()
    assert undo_stack.clean_index() == 5
    undo_spy[undo_stack.clean_changed].assert_called_once_with(True)

    undo_spy.reset()
    undo_stack.undo()
    undo_spy[undo_stack.clean_changed].assert_called_once_with(False)

    undo_spy.reset()
    undo_stack.push(MockUndoCommand())
    undo_spy[undo_stack.clean_changed].assert_not_called()
    assert not undo_stack.is_clean()


def test_can_be_cleared(undo_stack, undo_spy):
    for _ in range(5):
        undo_stack.push(MockUndoCommand())

    undo_spy.reset()
    undo_stack.clear()
    assert undo_stack.n_commands() == 0
    undo_spy[undo_stack.index_changed].assert_called_once_with(0)
    undo_spy[undo_stack.clean_changed].assert_called_once_with(True)
    undo_spy[undo_stack.undo_text_changed].assert_called_once_with("")
    undo_spy[undo_stack.redo_text_changed].assert_called_once_with("")
    undo_spy[undo_stack.can_undo_changed].assert_called_once_with(False)
    undo_spy[undo_stack.can_redo_changed].assert_called_once_with(False)


def test_clean_state_can_be_reset(undo_stack, undo_spy):
    for _ in range(5):
        undo_stack.push(MockUndoCommand())

    undo_stack.set_clean()
    undo_spy.reset()
    undo_stack.reset_clean()
    assert not undo_stack.is_clean()
    undo_spy[undo_stack.clean_changed].assert_called_once_with(False)


def test_can_trigger_all_signals(undo_stack, undo_spy):
    undo_stack.trigger_all_signals()
    undo_spy[undo_stack.index_changed].assert_called_once_with(0)
    undo_spy[undo_stack.clean_changed].assert_called_once_with(True)
    undo_spy[undo_stack.undo_text_changed].assert_called_once_with("")
    undo_spy[undo_stack.redo_text_changed].assert_called_once_with("")
    undo_spy[undo_stack.can_undo_changed].assert_called_once_with(False)
    undo_spy[undo_stack.can_redo_changed].assert_called_once_with(False)


def test_commands_obsolete_after_merge_are_removed(undo_stack):
    mock = MockUndoCommand(do_try_merge=True)
    mock.obsolete_after_call(mock.merge_with_mock)

    undo_stack.push(mock)
    assert undo_stack.n_commands() == 1

    undo_stack.push(MockUndoCommand(do_try_merge=True))
    mock.merge_with_mock.assert_called_once()
    assert undo_stack.n_commands() == 0


def test_commands_obsolete_after_undo_are_removed(undo_stack):
    mock = MockUndoCommand()
    mock.obsolete_after_call(mock.undo_mock)

    assert undo_stack.index() == 0
    undo_stack.push(mock)
    assert undo_stack.n_commands() == 1
    undo_stack.undo()
    assert undo_stack.n_commands() == 0
    assert undo_stack.index() == 0


def test_commands_obsolete_after_redo_are_removed(undo_stack):
    mock = MockUndoCommand()
    mock.obsolete_after_call(mock.redo_mock)

    assert undo_stack.index() == 0
    undo_stack.push(mock)
    undo_stack.undo()
    assert undo_stack.n_commands() == 1
    undo_stack.redo()
    assert undo_stack.n_commands() == 0
    assert undo_stack.index() == 0


def test_commands_obsolete_after_redo_reset_clean_state(undo_stack, undo_spy):
    mock = MockUndoCommand()
    mock.obsolete_after_call(mock.redo_mock)

    undo_stack.push(mock)
    undo_stack.set_clean()
    undo_stack.undo()
    undo_spy.reset()
    undo_stack.redo()
    assert not undo_stack.is_clean()
    assert undo_stack.clean_index() == -1


def test_calling_undo_redo_out_of_index_does_nothing(undo_stack):
    undo_stack.undo()
    undo_stack.redo()


class AsyncListAppendCommand(ListAppendCommand):
    async def undo_async(self) -> None:
        await asyncio.sleep(0.01)
        await super().undo_async()

    async def redo_async(self) -> None:
        await asyncio.sleep(0.01)
        await super().redo_async()


@pytest.mark.asyncio
async def test_is_compatible_with_async_undo_redo(undo_stack):
    a_list = []

    for i in range(10):
        await undo_stack.push_async(AsyncListAppendCommand(a_list, i))

    await undo_stack.undo_async()
    await undo_stack.redo_async()

    assert a_list == list(range(10))


@pytest.mark.asyncio
async def test_is_compatible_with_async_undo_redo_group(undo_stack):
    a_list = []

    with undo_stack.group_undo_commands():
        for i in range(10):
            await undo_stack.push_async(AsyncListAppendCommand(a_list, i))

    await undo_stack.undo_async()
    await undo_stack.undo_async()
    assert a_list == []

    await undo_stack.redo_async()
    await undo_stack.redo_async()
    assert a_list == list(range(10))


@pytest.mark.asyncio
async def test_push_async_obsolete_calls_redo_async(undo_stack):
    mock = MockUndoCommand()
    mock._is_obsolete = True

    await undo_stack.push_async(mock)
    mock.redo_async_mock.assert_called_once()
