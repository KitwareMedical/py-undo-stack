from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import (
    AbstractContextManager,
    contextmanager,
)
from itertools import count
from weakref import WeakMethod


class Slot:
    """
    Wrapper around callable to allow for weak references over any bound method.
    Call forwards to callable when the associated callable still exists.
    Is compatible with both bound methods and lambdas.
    """

    def __init__(self, slot: Callable):
        try:
            self._slot = WeakMethod(slot)
        except TypeError:
            self._slot = slot

    def is_obsolete(self) -> bool:
        """
        Checks if the slot is obsolete (i.e., the referenced callable no longer exists).

        :return: True if obsolete, False otherwise.
        """
        return self.slot is None

    def __eq__(self, other: Callable) -> bool:
        return self.slot == other

    def __call__(self, *args, **kwargs) -> None:
        """
        Invokes the stored callable with the provided arguments if the slot is not obsolete.
        Otherwise, does nothing.
        """
        if self.is_obsolete():
            return
        self.slot(*args, **kwargs)

    @property
    def slot(self) -> Callable[...] | None:
        """
        Retrieves the actual callable stored in this slot.

        :return: Callable if available, None if obsolete.
        """
        return self._slot if not isinstance(self._slot, WeakMethod) else self._slot()


class Signal:
    """
    Signal implementation.
    Can be connected to one or more callables.
    When called, will call associated callables with the provided args and kwargs.

    Provides utility methods and contextmanager to control signal execution.
    Can be used both as class property and instance.

    :param type_info: Types of arguments expected by the signal.
    """

    def __init__(self, *type_info: type):
        self._id = count()
        self._connect_dict: dict[int, Slot] = {}
        self._type_info = type_info
        self._name = ""
        self._private_name = ""
        self._is_signal_blocked = False
        self._last_call_args = None
        self._is_retaining_call_args = False

    @property
    def type_info(self) -> tuple[type]:
        """
        Call arguments expected by the signal.
        """
        return self._type_info

    def __del__(self):
        self.disconnect_all()

    def __set_name__(self, owner: type, name: str) -> None:
        """
        Stores signal name when used as property.
        When used in instances, signal will be stored in _private_name attribute.
        """
        self._name = name
        self._private_name = f"_{name}"

    def __get__(self, instance, owner: type) -> Signal:
        """
        Returns the signal associated with the input instance if any.
        If used from the class, will return the class Signal.
        If the instance doesn't already store the signal, will create
        a new signal first and attach it to the instance.
        """
        if instance is None:
            return self

        if not hasattr(instance, self._private_name):
            signal = Signal(*self._type_info)
            signal._name = self._name
            signal._private_name = self._private_name
            setattr(instance, self._private_name, signal)

        return getattr(instance, self._private_name)

    def emit(self, *args, **kwargs) -> None:
        """
        Emits the signal to all connected, non-obsolete, slots with the input args, kwargs.
        If signal is currently blocked, will not forward to the slots.
        If signal call args are retained, will store last args regardless of block status.
        """
        if self._is_retaining_call_args:
            self._last_call_args = (args, kwargs)

        self._remove_obsolete_slots()

        if self._is_signal_blocked:
            return

        for slot in self._slots():
            slot(*args, **kwargs)

    def connect(self, *slots) -> int | list[int]:
        """
        Connects the Signal to one or more callable and returns the associated connection ID(s).
        Connection ids can be used to disconnect the slot.
        Slot instances will be connected only once. Trying to connect the same instance to
        the signal will be ignored.

        :raises: RuntimeError if called without any args.
        """
        slots = list(slots)
        if not slots:
            _msg = "Trying to connect to empty slot."
            raise RuntimeError(_msg)

        connect_ids = []
        for slot in slots:
            if self._contains_slot(slot):
                connect_ids.append(self._slot_idx(slot))
                continue

            next_id = next(self._id)
            self._connect_dict[next_id] = Slot(slot)
            connect_ids.append(next_id)
        return connect_ids if len(connect_ids) > 1 else connect_ids[0]

    def disconnect(self, *slots: int | Callable) -> bool:
        """
        Disconnects the input slot(s) using either the slot instance or its connection id.
        If slot or connection id is not present in the signal, the call will be ignored.
        :param slots: Slot or connection id to disconnect
        :return: status or list of status of disconnection
        """
        slots = list(slots)
        if not slots:
            _msg = "Trying to disconnect with empty connection ID."
            raise RuntimeError(_msg)

        status = []
        for connect_id in slots:
            slot_idx = self._slot_idx(connect_id)
            if slot_idx in self._connect_dict:
                del self._connect_dict[slot_idx]
                status.append(True)
            else:
                status.append(False)
        return status if len(slots) > 1 else status[0]

    def disconnect_all(self) -> None:
        """
        Disconnects all currently connected slots.
        """
        for connectId in list(self._connect_dict.keys()):
            self.disconnect(connectId)

    def block_signals(self, is_blocked: bool) -> bool:
        """
        Set the signal blocked or enabled and returns the previous block status.
        """
        was_blocked = self.is_signal_blocked()
        self._is_signal_blocked = is_blocked
        return was_blocked

    def is_signal_blocked(self) -> bool:
        """
        Returns True if the signal is currently blocked, False otherwise.
        """
        return self._is_signal_blocked

    def __call__(self, *args, **kwargs) -> None:
        """
        Emits the signal with the input args, kwargs.
        """
        self.emit(*args, **kwargs)

    @property
    def name(self) -> str:
        """
        Returns name attached to the current signal.
        """
        return self._name

    def _slot_idx(self, slot: int | Callable) -> int | None:
        """
        Returns connection ID associated with the input slot.
        If slot is not found in the signal connection dict, returns None.
        """
        if isinstance(slot, int):
            return slot if slot in self._connect_dict else None

        for key, val in self._connect_dict.items():
            if val == slot:
                return key
        return None

    def _contains_slot(self, slot: int | Callable) -> bool:
        """
        Returns true if slot is contained in the connection dict, False otherwise.
        """
        return self._slot_idx(slot) is not None

    def _remove_obsolete_slots(self) -> None:
        """
        Removes any slot which is obsolete (i.e. bound method instances have been garbage collected).
        """
        self._connect_dict = {
            k: v for k, v in self._connect_dict.items() if not v.is_obsolete()
        }

    def _retain_last_call_args(self, do_retain: bool) -> bool:
        """
        Set the signal to retain its last call args.
        Returns the previous retain status.
        When called with False, will reset the last args to None.
        """
        was_retaining = self._is_retaining_call_args
        self._is_retaining_call_args = do_retain
        if not do_retain:
            self._last_call_args = None
        return was_retaining

    @contextmanager
    def _last_args_retained(self, captured_args: list) -> Generator[None, None, None]:
        """
        Context manager to retain the last args during context execution.
        Will push the captured args to the input captured_args param.
        """
        was_retained = self._retain_last_call_args(True)
        try:
            yield
        finally:
            captured_args.append(self._last_call_args)
            self._retain_last_call_args(was_retained)

    @contextmanager
    def emit_once(self) -> AbstractContextManager:
        """
        Context manager allowing to only emit once during context execution.
        Signal emit will be done with the last call args after context exits.
        """
        last_args = []
        with self._last_args_retained(last_args), self.emit_blocked() as was_blocked:
            yield

        last_args = last_args[0]
        if was_blocked or last_args is None:
            return

        args, kwargs = last_args
        self.emit(*args, **kwargs)

    @contextmanager
    def emit_blocked(self) -> AbstractContextManager:
        """
        Context manager allowing to block signal during context execution.
        """

        was_blocked = self.block_signals(True)
        try:
            yield was_blocked
        finally:
            self.block_signals(was_blocked)

    def _slots(self) -> list[Slot]:
        return list(self._connect_dict.values())
