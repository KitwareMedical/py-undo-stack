from unittest.mock import MagicMock

from undo_stack import Signal, SignalContainer


def test_can_block_contained_signals():
    class A(SignalContainer):
        s1 = Signal()
        s2 = Signal()

    mock = MagicMock()
    a = A()
    a.s1.connect(mock)
    a.s2.connect(mock)

    with a.signals_blocked():
        a.s1()
        a.s2()

    mock.assert_not_called()
    a.s1()

    mock.assert_called_once()


def test_block_is_not_recursive():
    class A(SignalContainer):
        s1 = Signal()

    class B(SignalContainer):
        def __init__(self):
            self.a = A()

    mock = MagicMock()
    b = B()
    b.a.s1.connect(mock)
    with b.signals_blocked():
        b.a.s1()

    mock.assert_called_once()


def test_can_iterate_over_signals():
    class A(SignalContainer):
        s1 = Signal()
        s2 = Signal()

        def __init__(self):
            self.mock_f = MagicMock()

        def f(self):
            self.mock_f()

    a = A()
    assert len(a.signals()) == 2
    assert a.s1 in a.signals()
    assert a.s2 in a.signals()
    assert a.f not in a.signals()
    assert a.mock_f not in a.signals()
    a.mock_f.assert_not_called()


def test_signal_iteration_is_not_recursive():
    class A(SignalContainer):
        s1 = Signal()

    class B(SignalContainer):
        def __init__(self):
            self.a = A()

    b = B()
    assert len(b.signals()) == 0


def test_can_disconnect_all_contained_signals():
    class A(SignalContainer):
        s1 = Signal()
        s2 = Signal()

    mock = MagicMock()
    a = A()
    a.s1.connect(mock)
    a.s2.connect(mock)

    a.disconnect_all()
    a.s1()
    a.s2()
    mock.assert_not_called()


def test_can_emit_signals_only_once():
    class A(SignalContainer):
        s1 = Signal()
        s2 = Signal()
        s3 = Signal()

    a = A()
    signals = a.signals()
    mocks = [MagicMock() for _ in range(len(signals))]

    for mock, signal in zip(mocks, signals):
        signal.connect(mock)

    with a.emit_signals_once():
        for _ in range(10):
            for signal in signals:
                signal.emit(signal.name)

    for mock, signal in zip(mocks, signals):
        mock.assert_called_with(signal.name)
