"""Independent NBOT worker runtimes without cross-worker eager imports."""

__all__ = ["ExecutionWorker", "ObservationWorker"]


def __getattr__(name):
    if name == "ExecutionWorker":
        from workers.execution_worker import ExecutionWorker

        return ExecutionWorker
    if name == "ObservationWorker":
        from workers.observation_worker import ObservationWorker

        return ObservationWorker
    raise AttributeError(name)
