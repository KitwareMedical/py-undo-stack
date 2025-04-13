from unittest.mock import MagicMock

from .signal import Signal
from .signal_container import SignalContainer


class SignalContainerSpy:
    """
    Helper class to spy on a signal container for testing purposes.
    For each signal contained in the signal container creates an associated mock.

    Each mock can be accessed using item indexing with the input signal as its argument.
    """

    def __init__(self, signal_container: SignalContainer):
        self._mocks: dict[Signal, MagicMock] = {}
        for sig in signal_container.signals():
            mock = MagicMock()
            sig.connect(mock)
            self._mocks[sig] = mock

    def reset(self):
        """
        Resets all mocks in the spy.
        """
        for mock in self._mocks.values():
            mock.reset_mock()

    def get_mock(self, sig: Signal) -> MagicMock:
        """
        Returns mock associated with the input signal.
        """
        return self._mocks[sig]

    def __getitem__(self, item: Signal) -> MagicMock:
        """
        Returns mock associated with the input signal.
        """
        return self.get_mock(item)
