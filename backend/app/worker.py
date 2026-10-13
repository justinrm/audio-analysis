from __future__ import annotations

import sqlite3


class AnalysisWorker:
    """Future one-at-a-time analysis worker.

    Milestone 0 never queues a job. This method must not mark a job completed.
    When analysis exists, the worker will claim `queued` rows and move them
    through queued, running, completed, failed, or canceled.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def run_available(self) -> int:
        return 0
