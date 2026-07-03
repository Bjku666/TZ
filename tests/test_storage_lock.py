from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from src import storage


class StorageLockTests(TestCase):
    def test_file_write_lock_has_non_posix_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "sample.csv"
            lock_path = target.with_name(".sample.csv.lock")

            with patch.object(storage, "fcntl", None):
                with storage.file_write_lock(target):
                    self.assertTrue(lock_path.exists())

            self.assertFalse(lock_path.exists())
