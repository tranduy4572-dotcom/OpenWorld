"""Check this extension sees the ORIGINAL OpenWorld src tree."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True  # keep original src/ free of generated __pycache__

from openworld_bridge import activate_openworld

ADDON = Path(__file__).resolve().parent.parent

def check():
    try:
        ROOT = activate_openworld(ADDON)
    except RuntimeError as exc:
        print("[LOI]", exc)
        return 1
    print("OpenWorld root:", ROOT)
    import openworld_superkernel.world_fixture as fixture
    import openworld_superkernel.world_guard as guard
    import openworld_superkernel.hyper_memory_p1e as hypermemory
    import openworld_superkernel.world_persistence as persistence
    for module in (fixture, guard, hypermemory, persistence):
        if not Path(module.__file__).resolve().is_relative_to(ROOT / "src"):
            print("[LOI] Module dang duoc nap tu ban OpenWorld khac:", module.__file__)
            return 1
    from openworld_superkernel.world_fixture import Agent, create_world
    from openworld_superkernel.world_guard import GuardedWorldGateway
    from openworld_superkernel.hyper_memory_p1e import HyperMemoryP1e
    from openworld_superkernel.world_persistence import save_checkpoint
    world = create_world((Agent("alice", "owner", "lab", 1), Agent("bob", "owner", "lab", 0)), (("alice", "bob"),))
    print("[OK] Import cac module goc THANH CONG")
    print("[OK] W3 tao world, tick=",world.tick, "balance=",dict(world.balances))
    print("[OK] Module duoc nap tu dung cay src cua OpenWorld da chon")
    return 0

if __name__ == "__main__":
    raise SystemExit(check())
