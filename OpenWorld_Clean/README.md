# OpenWorld Clean

A small local learning copy of the working OpenWorld simulation core. It keeps
eight runtime modules, one runnable example, and one integration test file.
The full research project is the repository root (`..`).

Vietnamese walkthrough and file map: [Start here](docs/vi/BAT_DAU.txt).

## Run

Use Python 3.11 or newer. From this directory:

```console
python -B examples/r0_agent_cycle.py
python -B -m unittest discover -s tests -v
```

On Windows, `CHAY.bat` runs the example and leaves its output visible.
The retained code uses the Python standard library; no package installation or
API key is needed for this example.

## Retained behavior

The example observes a simulated world, reads SQLite memory, chooses an action,
checks capability permissions, updates the world, records synthetic feedback,
and verifies replay. Its agents use a rule-based policy. The example supplies
the feedback sequence `(0, 1, 1)` and produces two transfers and one signal.
Alice and Bob start with three resources each and finish with one and five.

The world lives in RAM. The example creates its SQLite memory in a temporary
directory, which is removed on normal exit. `world_persistence.py` separately
provides SQLite checkpoint save/load functions; the example does not call them.
World updates and memory writes are separate consistency boundaries.

The original runtime, example, and test files are retained without code changes.
Research benchmarks, mathematical experiments, extra demos, and project-wide
automation are available in the full source project. Their tests are outside
this copy's scope.

## Gemini extension

The sibling `gemini_world` extension is separate. Its configuration (`..`)
selects the full repository root. To check imports against this copy in a
PowerShell session, from this directory:

```powershell
$env:OPENWORLD_ROOT = (Get-Location).Path
python -B ..\gemini_world\app\verify_integration.py
Remove-Item Env:OPENWORLD_ROOT
```

This checks local integration only. It does not call the Gemini API.

## License

Original OpenWorld files retain their Apache-2.0 license; see `LICENSE`.

## Local verification — 2026-11-24

The demo and Windows launcher completed with replay PASS and final balances
Alice 1 / Bob 5. The Gemini integration check, using a process-local
`OPENWORLD_ROOT` override, imported modules from this copy and created a world.
It did not test live model calls.

All 178 files in the original source tree retained their SHA-256 hashes during
the reduction. All 13 copied files retained here match that source; four local
documentation/launcher files bring the total to 17. Runtime code was unchanged.

Retained integration test log, produced with
`python -B -m unittest discover -s tests -v`:

```text
test_full_cycle_changes_policy_and_preserves_simulated_provenance (test_r0_agent_cycle.R0CycleTests.test_full_cycle_changes_policy_and_preserves_simulated_provenance) ... ok
test_hold_never_fabricates_reward_or_memory_event (test_r0_agent_cycle.R0CycleTests.test_hold_never_fabricates_reward_or_memory_event) ... ok
test_hold_with_outcome_denied (test_r0_agent_cycle.R0CycleTests.test_hold_with_outcome_denied) ... ok
test_invalid_feedback_denied_pre_action (test_r0_agent_cycle.R0CycleTests.test_invalid_feedback_denied_pre_action) ... ok
test_missing_or_wrong_read_capability_denied (test_r0_agent_cycle.R0CycleTests.test_missing_or_wrong_read_capability_denied) ... ok
test_non_neighbor_denied (test_r0_agent_cycle.R0CycleTests.test_non_neighbor_denied) ... ok
test_revoked_write_capability_denied_before_memory_write (test_r0_agent_cycle.R0CycleTests.test_revoked_write_capability_denied_before_memory_write) ... ok
test_single_command_demo_outputs_verifiable_simulated_trace (test_r0_agent_cycle.R0CycleTests.test_single_command_demo_outputs_verifiable_simulated_trace) ... ok
test_world_rejection_does_not_update_memory (test_r0_agent_cycle.R0CycleTests.test_world_rejection_does_not_update_memory) ... ok
test_world_replay_tampering_rejected (test_r0_agent_cycle.R0CycleTests.test_world_replay_tampering_rejected) ... ok
test_wrong_actor_claim_denied (test_r0_agent_cycle.R0CycleTests.test_wrong_actor_claim_denied) ... ok
test_wrong_owner_target_denied (test_r0_agent_cycle.R0CycleTests.test_wrong_owner_target_denied) ... ok

----------------------------------------------------------------------
Ran 12 tests in 0.301s

OK
```
