"""Connection, persistence and mocked Gemini checks; never call a live API."""
from __future__ import annotations

from argparse import Namespace
from contextlib import closing, redirect_stdout
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import agent_lab
from gemini_api import GeminiAPIError, gemini_proposal
from openworld_bridge import REQUIRED_FILES, resolve_openworld_root


class RootResolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.addon = self.base / "gemini_world"
        self.addon.mkdir()
        self.environment = patch.dict(os.environ, {"OPENWORLD_ROOT": ""})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def core(self, path):
        for name in REQUIRED_FILES:
            target = path / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
        return path.resolve()

    def test_sibling_layout_independent_of_working_directory(self):
        core = self.core(self.base / "OpenWorld-main")
        self.assertEqual(resolve_openworld_root(self.addon), core)

    def test_installed_extension_uses_ancestor_core(self):
        core = self.core(self.base / "OpenWorld_Clean")
        nested = core / "extensions" / "gemini_world"
        nested.mkdir(parents=True)
        self.assertEqual(resolve_openworld_root(nested), core)

    def test_config_selects_one_of_multiple_projects(self):
        self.core(self.base / "OpenWorld-main")
        chosen = self.core(self.base / "OpenWorld_Clean")
        (self.addon / "openworld_config.json").write_text(
            json.dumps({"openworld_root": "../OpenWorld_Clean"}), encoding="utf-8")
        self.assertEqual(resolve_openworld_root(self.addon), chosen)

    def test_ambiguous_layout_requires_explicit_selection(self):
        self.core(self.base / "OpenWorld-main")
        self.core(self.base / "OpenWorld_Clean")
        with self.assertRaisesRegex(RuntimeError, "nhieu ban"):
            resolve_openworld_root(self.addon)

    def test_environment_override_and_invalid_override(self):
        core = self.core(self.base / "custom-core")
        with patch.dict(os.environ, {"OPENWORLD_ROOT": str(core)}):
            self.assertEqual(resolve_openworld_root(self.addon), core)
        with patch.dict(os.environ, {"OPENWORLD_ROOT": str(self.base / "absent")}):
            with self.assertRaisesRegex(RuntimeError, "tro sai"):
                resolve_openworld_root(self.addon)

    def test_invalid_config_does_not_silently_choose_other_core(self):
        self.core(self.base / "OpenWorld-main")
        config = self.addon / "openworld_config.json"
        for contents in ("not json", "[]", '{"openworld_root":""}',
                         '{"openworld_root":"missing"}'):
            with self.subTest(contents=contents):
                config.write_text(contents, encoding="utf-8")
                with self.assertRaises(RuntimeError):
                    resolve_openworld_root(self.addon)


class AdapterTests(unittest.TestCase):
    def test_rest_request_and_json_response_without_network(self):
        response = {"candidates": [{"content": {"parts": [
            {"text": '{"action":"signal","reason":"need resources"}'}]}}]}
        with patch.dict(os.environ, {"GEMINI_API_KEY": "unit-test-key",
                                     "GEMINI_MODEL": "unit-test-model"}, clear=True):
            with patch("gemini_api.request.urlopen", return_value=io.StringIO(json.dumps(response))) as call:
                result = gemini_proposal("synthetic observation only")
        self.assertEqual(result["proposal"]["action"], "signal")
        request = call.call_args.args[0]
        self.assertTrue(request.full_url.endswith("/unit-test-model:generateContent"))
        self.assertEqual(json.loads(request.data)["generationConfig"]["responseMimeType"], "application/json")
        self.assertNotIn("unit-test-key", request.data.decode())

    def test_missing_key_does_not_call_network(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("gemini_api.request.urlopen") as call:
                with self.assertRaises(GeminiAPIError):
                    gemini_proposal("test")
                call.assert_not_called()

    def test_http_error_redacts_key(self):
        error = HTTPError("https://example.invalid", 401, "denied", {},
                          io.BytesIO(b"invalid unit-test-key"))
        with patch.dict(os.environ, {"GEMINI_API_KEY": "unit-test-key"}, clear=True):
            with patch("gemini_api.request.urlopen", side_effect=error):
                with self.assertRaises(GeminiAPIError) as caught:
                    gemini_proposal("test")
        self.assertNotIn("unit-test-key", str(caught.exception))
        self.assertIn("[REDACTED]", str(caught.exception))


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name) / "run"

    def run_lab(self, steps, mode="offline"):
        args = Namespace(data_dir=self.folder, fresh=False, steps=steps, mode=mode, auto=True)
        with redirect_stdout(io.StringIO()):
            agent_lab.run(args)
        return [json.loads(line) for line in (self.folder / "trace.jsonl").read_text(encoding="utf-8").splitlines()]

    def test_offline_reaches_goal_using_real_core_and_sqlite(self):
        records = self.run_lab(6)
        self.assertEqual([r["validated_action"] for r in records], ["signal", "transfer", "signal", "transfer"])
        self.assertEqual(records[-1]["world_after"]["balances"], {"alice": 1, "bob": 2})
        self.assertTrue(all(r["replay"] == "PASS" for r in records))
        self.assertTrue(all(r["openworld_root"] == str(agent_lab.ROOT) for r in records))
        self.assertTrue((self.folder / "XEM_DU_LIEU.html").is_file())
        with closing(sqlite3.connect(self.folder / "memory.sqlite3")) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM exact_events").fetchone()[0], 4)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM agent_state").fetchone()[0], 2)

    def test_resume_adds_only_new_events(self):
        self.run_lab(1)
        records = self.run_lab(1)
        self.assertEqual([r["actor"] for r in records], ["bob", "alice"])
        self.assertEqual(records[-1]["world_after"]["balances"], {"alice": 2, "bob": 1})
        with closing(sqlite3.connect(self.folder / "memory.sqlite3")) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM exact_events").fetchone()[0], 2)

    def test_mocked_gemini_proposals_follow_same_guarded_world_path(self):
        decisions = [{"proposal": {"action": action, "reason": "mock response"},
                      "source": "MOCK_GEMINI_API", "model": "unit-test-model"}
                     for action in ("signal", "transfer", "signal", "transfer")]
        with patch("agent_lab.gemini_proposal", side_effect=decisions) as model:
            records = self.run_lab(6, "gemini")
        self.assertEqual(model.call_count, 4)
        self.assertTrue(all(r["source"] == "MOCK_GEMINI_API" for r in records))
        self.assertEqual(records[-1]["world_after"]["balances"]["bob"], 2)
        self.assertIn("TRANG THAI DUOC PHEP QUAN SAT", model.call_args.args[0])

    def test_invalid_model_action_is_not_executed_or_trained(self):
        decision = {"proposal": {"action": "delete_world"},
                    "source": "MOCK_GEMINI_API", "model": "unit-test-model"}
        with patch("agent_lab.gemini_proposal", return_value=decision):
            with self.assertRaises(ValueError):
                self.run_lab(1, "gemini")
        _, world = agent_lab.load_checkpoint(self.folder / "world.sqlite3")
        self.assertEqual(world.tick, 0)
        self.assertEqual(dict(world.balances), {"alice": 3, "bob": 0})
        with closing(sqlite3.connect(self.folder / "memory.sqlite3")) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM exact_events").fetchone()[0], 0)

    def test_capability_is_issued_after_a_slow_model_response(self):
        clock = [agent_lab.time.time()]

        def slow_response(prompt):
            clock[0] += 7200
            return {"proposal": {"action": "signal"},
                    "source": "MOCK_GEMINI_API", "model": "unit-test-model"}

        with patch("agent_lab.time.time", side_effect=lambda: clock[0]):
            with patch("agent_lab.gemini_proposal", side_effect=slow_response):
                records = self.run_lab(1, "gemini")
        self.assertEqual(records[0]["validated_action"], "signal")
        self.assertEqual(records[0]["world_after"]["tick"], 1)

    def test_hold_has_no_fabricated_feedback(self):
        decision = {"proposal": {"action": "hold"},
                    "source": "MOCK_GEMINI_API", "model": "unit-test-model"}
        with patch("agent_lab.gemini_proposal", return_value=decision):
            records = self.run_lab(1, "gemini")
        self.assertIsNone(records[0]["feedback"])
        self.assertIsNone(records[0]["memory_event_id"])
        self.assertEqual(records[0]["memory_after"]["n"], 0)

    def test_resume_refuses_world_memory_mismatch(self):
        self.run_lab(1)
        with closing(sqlite3.connect(self.folder / "memory.sqlite3")) as db:
            state = json.loads(db.execute("SELECT state_json FROM agent_state").fetchone()[0])
            state["seq"] = 0
            db.execute("UPDATE agent_state SET state_json=?", (json.dumps(state),))
            db.commit()
        with self.assertRaisesRegex(RuntimeError, "khong khop"):
            self.run_lab(1)


if __name__ == "__main__":
    unittest.main()
