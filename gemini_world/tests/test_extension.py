"""Focused tests for the adapter and action validation; no Gemini key needed."""
import sys
sys.dont_write_bytecode = True  # keep original src/ free of generated __pycache__
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from openworld_bridge import activate_openworld

ROOT = activate_openworld()

from gemini_api import _json_proposal, offline_proposal, GeminiAPIError
from openworld_superkernel.world_fixture import Agent, create_world, observe
from agent_lab import validate_action, OWNER


class GeminiWorldLabTests(unittest.TestCase):
    def setUp(self):
        self.world = create_world((Agent("alice", OWNER, "lab", 3),
                                   Agent("bob", OWNER, "lab", 0)),
                                  (("alice", "bob"),), seed=2026)
        self.alice = observe(self.world, OWNER, "alice")
        self.bob = observe(self.world, OWNER, "bob")

    def test_offline_brain_has_bounded_actions(self):
        self.assertEqual(offline_proposal("bob", 0, 0, 2)["proposal"]["action"], "signal")
        self.assertEqual(offline_proposal("alice", 3, 0, 2)["proposal"]["action"], "transfer")

    def test_model_output_cannot_grant_any_action(self):
        parsed = _json_proposal('{"action":"delete_world", "reason":"test"}')
        with self.assertRaises(ValueError):
            validate_action("alice", parsed, self.alice, self.world)
        with self.assertRaises(ValueError):
            validate_action("bob", {"action":"transfer"}, self.bob, self.world)

    def test_json_invalid_is_rejected(self):
        with self.assertRaises(GeminiAPIError):
            _json_proposal("not JSON")

    def test_valid_transfer_for_alice(self):
        self.assertEqual(validate_action("alice", {"action":"transfer"},
                                         self.alice, self.world), "transfer")


if __name__ == "__main__":
    unittest.main()
