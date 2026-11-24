"""Gemini proposals connected to the original OpenWorld W3/HyperMemory modules.

Observe -> HyperMemory -> Gemini proposal -> Validate -> Capability Guard ->
W3 World reducer -> HyperMemory record -> World checkpoint -> JSON trace.
This is a SIMULATED, SAME-OWNER learning lab, NOT a production trusted runtime.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys
sys.dont_write_bytecode = True  # keep original src/ free of generated __pycache__
import time

APP_DIR = Path(__file__).resolve().parent
ADDON_DIR = APP_DIR.parent
from openworld_bridge import activate_openworld

ROOT = activate_openworld(ADDON_DIR)
from gemini_api import (  # noqa: E402
    GeminiAPIError, gemini_proposal, load_local_env, offline_proposal,
)
from openworld_superkernel.hyper_memory_p1e import HyperMemoryP1e, Observation as MemoryObservation
from openworld_superkernel.memory_contracts import MemoryEvent, Provenance
from openworld_superkernel.trust_boundaries import CapabilityAuthority
from openworld_superkernel.world_fixture import Agent, Action, create_world, verify_replay
from openworld_superkernel.world_guard import AuthorizedWorldAction, GuardedWorldGateway
from openworld_superkernel.world_persistence import load_checkpoint, save_checkpoint

OWNER = "local-research-owner"
PRINCIPAL = "trusted-local-lab"
GOAL_BOB_BALANCE = 2
START_ALICE, START_BOB = 3, 0


def world_data(world) -> dict:
    return {"tick": world.tick, "balances": dict(world.balances),
            "weather": dict(world.weather), "event_count": len(world.events),
            "fingerprint": world.fingerprint()}


def public_observation(actor: str, obs, world) -> dict:
    """W3 observation + explicit same-owner PUBLIC goal notice from host.

    The target balance is NOT part of raw W3.observe; the trusted host is
    deliberately publishing it for this synthetic same-owner classroom task.
    """
    return {"tick": obs.tick, "agent": actor,
            "my_resources": obs.balance, "region": obs.region,
            "weather": obs.weather, "neighbors": list(obs.neighbors),
            "inbox": list(obs.inbox),
            "public_goal_notice": {
                "task": f"Bob can dat {GOAL_BOB_BALANCE} don vi tai nguyen mo phong",
                "bob_balance": dict(world.balances)["bob"],
                "target": GOAL_BOB_BALANCE,
            }}


def make_prompt(actor: str, observation: dict, memory_state: dict, prediction: float) -> str:
    roles = (
        f"Ban la BOB. Ban muon nhan du {GOAL_BOB_BALANCE} don vi tai nguyen. "
        "Neu thieu, gui tin hieu cho Alice. Neu du, chon hold. "
        "Chi duoc chon: signal, hold."
        if actor == "bob" else
        f"Ban la ALICE. Muc tieu giup Bob dat {GOAL_BOB_BALANCE} don vi tai nguyen. "
        "Neu Bob chua du va ban co tai nguyen, chuyen dung 1 don vi. "
        "Chi duoc chon: transfer, signal, hold."
    )
    return (
        "OpenWorld W3 la MO PHONG. Ban chi DE XUAT mot hanh dong, "
        "khong duoc sua so du, khong goi cong cu, khong tu cap quyen.\n"
        + roles + "\n"
        "Tra ve duy nhat JSON: {\"action\":\"...\",\"reason\":\"ly do ngan bang tieng Viet\"}.\n"
        "TRANG THAI DUOC PHEP QUAN SAT:\n"
        + json.dumps(observation, ensure_ascii=False) + "\n"
        "BO NHO RIENG (chi la thong ke du doan):\n"
        + json.dumps({"n": memory_state["n"], "successes": memory_state["successes"],
                      "selected": memory_state["selected"], "estimate": round(prediction, 4)},
                     ensure_ascii=False)
    )


def validate_action(actor: str, proposal: dict, obs, world) -> str:
    action = proposal.get("action", "")
    allowed = {"bob": {"signal", "hold"},
               "alice": {"transfer", "signal", "hold"}}[actor]
    if action not in allowed:
        raise ValueError(f"LLM de xuat hanh dong khong duoc phep: {action!r}")
    if action == "transfer":
        if obs.balance < 1:
            raise ValueError("Alice khong du tai nguyen de chuyen")
        if dict(world.balances)["bob"] >= GOAL_BOB_BALANCE:
            raise ValueError("Bob da dat muc tieu: khong chuyen them")
    return action


def outcome_from_simulation(actor: str, action: str, before, after) -> int:
    """A documented synthetic task reward, not actual partner feedback."""
    b0 = dict(before.balances)["bob"]
    b1 = dict(after.balances)["bob"]
    if actor == "alice":
        return int(action == "transfer" and b0 < GOAL_BOB_BALANCE and b1 == b0 + 1)
    return int(action == "signal" and b0 < GOAL_BOB_BALANCE)


def ensure_memory_matches_world(world, memory: HyperMemoryP1e) -> None:
    for agent_id in ("alice", "bob"):
        count = sum(ev.actor == agent_id and ev.kind in {"transfer", "signal"}
                    for ev in world.events)
        state = memory.get_state(owner_id=OWNER, agent_id=agent_id,
                                 requester_owner_id=OWNER)
        if count != state["seq"]:
            raise RuntimeError(
                f"World/HyperMemory khong khop: {agent_id} world={count} memory={state['seq']}. "
                "Dung tai day. Khong tu dong ghi de hay reset: can phuc hoi thu cong."
            )


def new_world():
    return create_world((Agent("alice", OWNER, "lab", START_ALICE),
                         Agent("bob", OWNER, "lab", START_BOB)),
                        (("alice", "bob"),), seed=2026)


def run(args) -> Path:
    load_local_env(ADDON_DIR)
    folder = args.data_dir or (ADDON_DIR / "runs" / "lab")
    if args.fresh:
        folder = folder.with_name(folder.name + "_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    folder.mkdir(parents=True, exist_ok=True)
    db_world, db_memory, tracefile = (folder / "world.sqlite3", folder / "memory.sqlite3",
                                      folder / "trace.jsonl")
    if db_world.exists() != db_memory.exists():
        raise RuntimeError("Chi mot DB ton tai: khong the tu dong phuc hoi an toan")
    if db_world.exists():
        genesis, world = load_checkpoint(db_world)
        if tuple((a.agent_id, a.owner_id, a.resources) for a in genesis.agents) != (
            ("alice", OWNER, START_ALICE), ("bob", OWNER, START_BOB)
        ):
            raise RuntimeError("Checkpoint khong phai the gioi demo hien tai")
        print("Tiep tuc the gioi da luu: tick", world.tick)
    else:
        genesis = world = new_world()
        print(f"Tao the gioi moi. Alice=3, Bob=0, muc tieu Bob>={GOAL_BOB_BALANCE}")
    authority = CapabilityAuthority(os.urandom(32), issuer="ow-gemini-local", audience="world")
    gateway = GuardedWorldGateway(authority, authenticated_principal=lambda: PRINCIPAL)
    def capability(agent_id: str, permission: str) -> str:
        now = int(time.time())
        return authority.issue(principal=PRINCIPAL, owner=OWNER, resource=agent_id,
                               action=permission, valid_from=now-10, expires_at=now+120)

    with HyperMemoryP1e(db_memory) as memory:
        ensure_memory_matches_world(world, memory)
        # Save the initial world so both databases exist for clean resume.
        if not db_world.exists():
            save_checkpoint(db_world, genesis, world)
        records = []
        if tracefile.exists():
            for line in tracefile.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    records.append(json.loads(line))
        if len(records) != world.tick or any(item.get("tick") != idx for idx, item in enumerate(records)):
            raise RuntimeError(
                "Trace JSON va checkpoint world khong khop, khong tu dong tiep tuc. "
                "Tao the gioi moi voi --fresh; du lieu cu van duoc giu nguyen."
            )
        for _ in range(args.steps):
            if dict(world.balances)["bob"] >= GOAL_BOB_BALANCE:
                print(f"[XONG] Bob da du {GOAL_BOB_BALANCE} don vi tai nguyen.")
                break
            actor = "bob" if world.tick % 2 == 0 else "alice"
            observation = gateway.observe(world, agent_id=actor,
                                          signed_capability=capability(actor, "read_world"))
            mem_before = memory.get_state(owner_id=OWNER, agent_id=actor,
                                          requester_owner_id=OWNER)
            probability, estimator = memory.predict(owner_id=OWNER, agent_id=actor,
                                                     requester_owner_id=OWNER)
            visible = public_observation(actor, observation, world)
            prompt = make_prompt(actor, visible, mem_before, probability)
            if args.mode == "gemini":
                decision = gemini_proposal(prompt)
            else:
                decision = offline_proposal(actor, observation.balance,
                                             dict(world.balances)["bob"], GOAL_BOB_BALANCE)
            proposal = decision["proposal"]
            action_kind = validate_action(actor, proposal, observation, world)
            print(f"\nTICK {world.tick} - {actor.upper()} ({decision['source']})")
            print("Quan sat:", json.dumps(visible, ensure_ascii=False))
            print("HyperMemory:", f"n={mem_before['n']}, xac suat={probability:.2%}")
            print("De xuat:", json.dumps(proposal, ensure_ascii=False))
            if not args.auto:
                answer = input("Nhap Enter de CHO PHEP ap dung; go 'n' de dung: ").strip().lower()
                if answer in ("n", "no", "khong"):
                    print("Da dung. KHONG sua world o luot nay.")
                    break
            before = world
            if action_kind == "hold":
                step = gateway.advance(world, actions=(), external=(), max_actions=1)
                event_id = None
                outcome = None
            else:
                request_id = f"gemini-lab-{world.tick}-{actor}"
                command = Action(request_id=request_id, tick=world.tick,
                                 principal=OWNER, actor=actor,
                                 target="alice" if actor == "bob" else "bob",
                                 kind=action_kind, amount=1 if action_kind == "transfer" else 0)
                step = gateway.advance(world, actions=(AuthorizedWorldAction(
                    command, capability(actor, "write_agent")),), external=(), max_actions=1)
                if step.accepted != (request_id,) or step.rejected:
                    raise RuntimeError(f"World tu choi action: {step.rejected}")
                outcome = outcome_from_simulation(actor, action_kind, before, step.world)
                event_id = f"gemini-lab-{world.tick}-{actor}"
                payload = json.dumps({
                    "source": "SIMULATED", "actor": actor,
                    "action": action_kind, "outcome": outcome,
                    "world_before": before.fingerprint(),
                    "world_after": step.world.fingerprint(),
                }, ensure_ascii=False, sort_keys=True).encode("utf-8")
                memory.apply_batch((MemoryObservation(
                    event=MemoryEvent(event_id=event_id, owner_id=OWNER,
                                      event_type="synthetic_goal_progress",
                                      provenance=Provenance.SIMULATED,
                                      payload=payload, protected=True),
                    agent_id=actor, sequence_number=mem_before["seq"]+1,
                    outcome=outcome,
                ),), requester_owner_id=OWNER)
            if not verify_replay(genesis, step.world):
                raise RuntimeError("World replay khong hop le")
            world = step.world
            # TWO STORES ARE NOT ATOMIC TOGETHER: detectable by next-start consistency check.
            save_checkpoint(db_world, genesis, world)
            mem_after = memory.get_state(owner_id=OWNER, agent_id=actor,
                                         requester_owner_id=OWNER)
            record = {
                "tick": before.tick, "actor": actor, "source": decision["source"],
                "model": decision["model"], "goal": f"Bob >= {GOAL_BOB_BALANCE} simulated resources",
                "observation": visible, "memory_before": {
                    "n": mem_before["n"], "successes": mem_before["successes"],
                    "prediction": round(probability, 4), "estimator": estimator,
                }, "proposal": proposal,
                "validated_action": action_kind,
                "feedback": outcome, "memory_event_id": event_id,
                "world_before": world_data(before), "world_after": world_data(world),
                "memory_after": {"n": mem_after["n"],
                                 "successes": mem_after["successes"]},
                "replay": "PASS", "provenance": "SIMULATED",
                "openworld_root": str(ROOT),
                "files": [str(APP_DIR / "agent_lab.py"),
                          str(APP_DIR / "gemini_api.py"),
                          str(ROOT / "src/openworld_superkernel/world_guard.py"),
                          str(ROOT / "src/openworld_superkernel/world_fixture.py"),
                          str(ROOT / "src/openworld_superkernel/hyper_memory_p1e.py"),
                          str(ROOT / "src/openworld_superkernel/world_persistence.py")],
                "prompt": prompt,
            }
            with tracefile.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            records.append(record)
            print("Da ghi:", json.dumps(world_data(world), ensure_ascii=False))
            print("SQLite memory:", f"n={mem_after['n']}, success={mem_after['successes']}")
        try:
            from report import write_report
            write_report(folder / "XEM_DU_LIEU.html", records)
        except ImportError:
            print("Khong tim thay app/report.py (bao cao HTML).")
    print("\nTRANG THAI MUC TIEU:", "HOAN THANH" if dict(world.balances)["bob"] >= GOAL_BOB_BALANCE else "CHUA HOAN THANH")
    print("\nDU LIEU LUU TAI:", folder)
    print("Xem tung buoc:", folder / "XEM_DU_LIEU.html")
    print("Nhat ky JSON:", tracefile)
    return folder


def main():
    p = argparse.ArgumentParser(description="Gemini AI de xuat action trong OpenWorld W3")
    p.add_argument("--mode", choices=("offline", "gemini"), default="offline")
    p.add_argument("--steps", type=int, default=4, help="So luot chay (1..20)")
    p.add_argument("--auto", action="store_true", help="Bo qua xac nhan tung luot (chi mo phong)")
    p.add_argument("--fresh", action="store_true", help="Tao the gioi moi, khong ghi de du lieu cu")
    p.add_argument("--data-dir", type=Path)
    args = p.parse_args()
    if not 1 <= args.steps <= 20:
        p.error("--steps phai trong 1..20")
    try:
        run(args)
    except (GeminiAPIError, ValueError, PermissionError, RuntimeError, OSError) as exc:
        print(f"\n[LOI] {exc}", file=sys.stderr)
        print("Du lieu cu duoc giu lai; khong tu dong sua/ghi de.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
