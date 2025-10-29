"""Helpers to offload blocking work to a :class:`QThreadPool`."""
from __future__ import annotations

from typing import Any, Callable, Iterable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class TaskSignals(QObject):
    """Signals emitted by :class:`FunctionTask` when executed."""

    finished = Signal(object)
    error = Signal(object)


class FunctionTask(QRunnable):
    """Wrap a callable so it can be executed on a worker thread."""

    def __init__(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._function = function
        self._args = args
        self._kwargs = kwargs
        self.signals = TaskSignals()

    def run(self) -> None:  # pragma: no cover - Qt thread dispatch
        try:
            result = self._function(*self._args, **self._kwargs)
        except Exception as exc:  # pylint: disable=broad-except - surfaced via signal
            self.signals.error.emit(exc)
        else:
            self.signals.finished.emit(result)


def run_in_threadpool(
    function: Callable[..., Any],
    *,
    args: Iterable[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
    on_success: Callable[[Any], None] | None = None,
    on_error: Callable[[Exception], None] | None = None,
    thread_pool: QThreadPool | None = None,
) -> None:
    """Execute ``function`` on a background worker thread.

    ``on_success`` and ``on_error`` callbacks are executed on the main Qt thread
    thanks to the signal bridge provided by :class:`TaskSignals`.
    """

    task = FunctionTask(function, *(args or ()), **(kwargs or {}))
    if on_success:
        task.signals.finished.connect(on_success)
    if on_error:
        task.signals.error.connect(on_error)
    (thread_pool or QThreadPool.globalInstance()).start(task)
