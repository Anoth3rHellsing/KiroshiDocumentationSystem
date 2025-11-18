from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from unittest import TestCase

from KiroshiApp.core.model import CaseData
from KiroshiApp.core.storage import (
    iter_case_files,
    load_autosave,
    save_autosave,
    save_case_to_db,
)


class StorageTests(TestCase):
    def test_save_autosave_writes_expected_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            case = CaseData(company_name="Acme", case_id="A-1")

            autosave_path = save_autosave(case, base_path=base_path)

            self.assertTrue(autosave_path.exists())
            data = json.loads(autosave_path.read_text(encoding="utf-8"))
            self.assertEqual(data["company_name"], "Acme")
            self.assertTrue(data.get("last_modified"))

    def test_load_autosave_converts_remote_steps_legacy_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            autosave_payload = {
                "remote_steps": "Step summary",
                "case_id": "A-1",
            }
            autosave_path = base_path / "autosave.json"
            autosave_path.parent.mkdir(parents=True, exist_ok=True)
            autosave_path.write_text(json.dumps(autosave_payload), encoding="utf-8")

            case = load_autosave(base_path=base_path)

            assert case is not None
            self.assertEqual(case.case_id, "A-1")
            self.assertEqual(len(case.remote_sessions), 1)
            self.assertEqual(case.remote_sessions[0].notes, "Step summary")
            self.assertEqual(case.remote_sessions[0].title, "Session 1")

    def test_save_case_to_db_sanitizes_filename_and_stores_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            case = CaseData(company_name="Acme", case_id="Case:Alpha/Beta")

            saved_path = save_case_to_db(case, base_path=base_path)

            self.assertTrue(saved_path.exists())
            self.assertEqual(saved_path.name, "Case-Alpha-Beta.json")
            payload = json.loads(saved_path.read_text(encoding="utf-8"))
            self.assertIn("saved_at", payload)
            self.assertEqual(payload["case"]["case_id"], "Case:Alpha/Beta")

    def test_iter_case_files_returns_sorted_by_mtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            case_new = CaseData(company_name="New", case_id="new")
            case_old = CaseData(company_name="Old", case_id="old")

            old_path = save_case_to_db(case_old, base_path=base_path)
            # Ensure the second file is newer by touching it after a brief pause
            time.sleep(0.01)
            new_path = save_case_to_db(case_new, base_path=base_path)

            # Make the first file older
            old_time = old_path.stat().st_mtime - 100
            old_path.touch()
            os.utime(old_path, (old_time, old_time))

            files = list(iter_case_files(base_path=base_path))

            self.assertEqual(files[0], new_path)
            self.assertEqual(files[1], old_path)
