from unittest.mock import MagicMock

import pytest

from undo_stack import Signal
from undo_stack.signal import Slot


def test_can_be_used_as_class_property_or_as_instance():
    class A:
        signal1 = Signal(float, int, str)

        def __init__(self, slot1, slot2):
            self.signal1.connect(slot1)
            self.signal2 = Signal()
            self.signal2.connect(slot2)

    m1 = MagicMock()
    m2 = MagicMock()
    a = A(m1, m2)

    assert A.signal1.type_info == a.signal1.type_info

    a.signal1()
    a.signal2()
    m1.assert_called_once()
    m2.assert_called_once()

    assert a.signal1 != A.signal1

    a2 = A(m1, m2)
    assert a2.signal1 != a.signal1

    m3 = MagicMock()
    A.signal1.connect(m3)

    a.signal1()
    a2.signal1()
    m3.assert_not_called()

    A.signal1()
    m3.assert_called_once()


def test_can_be_connected_to_slots():
    s = Signal()

    m = MagicMock()
    s.connect(m)

    s.emit(42, 58)
    m.assert_called_once_with(42, 58)


def test_can_be_disconnected_using_connection_id():
    s = Signal()

    m = MagicMock()
    s_id = s.connect(m)
    s.disconnect(s_id)
    s()
    m.assert_not_called()


def test_can_be_connected_to_variadic_slots():
    s = Signal()

    mocks = [MagicMock() for _ in range(5)]
    s.connect(mocks[0])
    s.connect(*mocks[1:])

    s.emit(42)
    assert all(m.call_count == 1 for m in mocks)


def test_can_disconnect_multiple():
    s = Signal()
    mocks = [MagicMock() for _ in range(5)]
    ids = s.connect(*mocks)
    s.disconnect(*ids)

    s.emit(42)
    assert all(m.call_count == 0 for m in mocks)


def test_can_disconnect_all():
    s = Signal()
    mocks = [MagicMock() for _ in range(5)]
    s.connect(*mocks)
    s.disconnect_all()

    s.emit(42)
    assert all(m.call_count == 0 for m in mocks)


def test_when_blocked_signal_is_not_emitted():
    s = Signal()
    mocks = [MagicMock() for _ in range(5)]
    s.connect(*mocks)
    was_blocked = s.block_signals(True)
    assert not was_blocked

    s.emit(42)
    assert all(m.call_count == 0 for m in mocks)

    was_blocked = s.block_signals(False)
    assert was_blocked
    s.emit(42)
    assert all(m.call_count == 1 for m in mocks)


def test_added_signals_during_emit_are_ignored():
    s = Signal()

    mock = MagicMock()

    def add_to_signal():
        mock()
        s.connect(add_to_signal)

    s.connect(add_to_signal)
    s.emit()
    assert mock.call_count == 1


def test_removed_signals_during_emit_are_ignored():
    s = Signal()

    mock = MagicMock()

    def remove_signal():
        mock()
        s.disconnect_all()

    s.connect(remove_signal)
    s.emit()
    assert mock.call_count == 1


def test_can_remove_signals_using_slot_directly():
    s = Signal()
    mock = MagicMock()
    s.connect(mock)
    assert s.disconnect(mock)
    s.emit()
    mock.assert_not_called()


def test_connecting_same_slot_twice_returns_same_id_and_triggers_once_on_emit():
    s = Signal()
    mock = MagicMock()
    idx = s.connect(mock)
    assert s.connect(mock) == idx
    s.emit()
    mock.assert_called_once()


def test_deleted_slots_dont_raise_on_emit():
    mock = MagicMock()

    class A:
        def a_slot(self):
            print(self)
            mock()

    s = Signal()
    a = A()
    s.connect(a.a_slot)
    del a
    s.emit()
    mock.assert_not_called()


def test_signals_are_compatible_with_lambda():
    mock = MagicMock()
    s = Signal()
    s.connect(lambda: mock())
    s.emit()
    mock.assert_called_once()


def test_signals_are_compatible_with_functions():
    mock = MagicMock()

    def a_function():
        mock()

    s = Signal()
    s.connect(a_function)
    s.emit()
    mock.assert_called_once()


def test_can_emit_once():
    s = Signal()
    mock = MagicMock()
    s.connect(mock)

    with s.emit_once():
        for _ in range(10):
            s.emit()

    mock.assert_called_once()


def test_emit_once_in_cascade_emits_once():
    s = Signal()
    mock = MagicMock()
    s.connect(mock)

    with s.emit_once():
        s.emit()

        with s.emit_once():
            for _ in range(10):
                s.emit()

    mock.assert_called_once()


def test_emit_once_emits_only_last_value():
    s = Signal()
    mock = MagicMock()
    s.connect(mock)

    with s.emit_once():
        for i in range(42):
            s.emit(i, kw=i)

    mock.assert_called_once_with(41, kw=41)


def test_emit_once_doesnt_emit_if_no_call():
    s = Signal()
    mock = MagicMock()
    s.connect(mock)

    with s.emit_once():
        pass

    mock.assert_not_called()


def test_signal_instance_preserve_their_names():
    class A:
        my_signal = Signal()

    assert A.my_signal.name == "my_signal"

    a = A()
    assert a.my_signal.name == "my_signal"


def test_connection_to_deleted_slot_are_removed():
    mock = MagicMock()

    class A:
        def bound(self):
            print(self)
            mock()

    a = A()
    s = Slot(a.bound)
    del a
    assert s.is_obsolete()
    s()
    mock.assert_not_called()


def test_connecting_to_empty_slot_raises():
    s = Signal()
    with pytest.raises(RuntimeError):
        s.connect()

    with pytest.raises(RuntimeError):
        s.disconnect()


def test_can_contain_type_info():
    s = Signal(int, float)
    assert s.type_info == (int, float)


def test_bound_slots_are_not_connected_twice():
    mock = MagicMock()

    class A:
        def bound(self):
            print(self)
            mock()

    a = A()
    s = Signal()
    s.connect(a.bound)
    s.connect(a.bound)
    s.emit()
    mock.assert_called_once()
