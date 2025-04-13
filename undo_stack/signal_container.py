from contextlib import (
    AbstractContextManager,
    ExitStack,
    contextmanager,
)

from .signal import Signal


class SignalContainer:
    """
    Provides helper functions to iterate over signals.
    """

    def signals(self) -> list[Signal]:
        """
        Returns list of signals instance of the class.
        Call is not recursive and will not return the signals of signal containers contained
        by the instance.
        """
        return [
            getattr(self, v) for v in dir(self) if isinstance(getattr(self, v), Signal)
        ]

    @contextmanager
    def signals_blocked(self) -> AbstractContextManager:
        """
        Context manager to block all signals during context execution.
        """
        with ExitStack() as stack:
            for signal in self.signals():
                stack.enter_context(signal.emit_blocked())
            yield

    def disconnect_all(self):
        """
        Disconnects all slots connected to all signals of the class.
        :return:
        """
        for s in self.signals():
            s.disconnect_all()

    @contextmanager
    def emit_signals_once(self) -> AbstractContextManager:
        """
        Context manager to emit once for all signals connected to the class during context
        execution.
        """
        with ExitStack() as stack:
            for signal in self.signals():
                stack.enter_context(signal.emit_once())
            yield
