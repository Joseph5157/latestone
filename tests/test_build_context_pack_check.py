"""`--check` must validate without writing. That is its whole contract.

The flag exists so a read-only agent can satisfy AGENTS.md Step 0 without
violating a no-write charter. If it ever starts writing again the flag is
worse than useless — the caller has been told the tree is untouched and it
is not — so the guarantee is pinned here rather than left to review.

These tests call `main()` in-process and restore both outputs afterwards, so
a regression fails the suite instead of dirtying the developer's tree.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "build_context_pack.py"


def _load_module():
    """Import the script by path. `scripts/` is not a package."""
    spec = importlib.util.spec_from_file_location("build_context_pack", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_context_pack"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def pack():
    module = _load_module()
    # Snapshot both outputs; a broken --check would otherwise leave the real
    # docs/context/CURRENT_STATE.md rewritten on a failing run.
    saved = {
        path: (path.read_bytes() if path.exists() else None)
        for path in (module.START_HERE, module.CURRENT_STATE)
    }
    try:
        yield module
    finally:
        for path, data in saved.items():
            if data is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(data)


def test_check_does_not_touch_the_tracked_snapshot(pack):
    before = pack.CURRENT_STATE.read_bytes()
    pack.main(["--check", "--skip-tests"])
    assert pack.CURRENT_STATE.read_bytes() == before


def test_check_does_not_create_the_gitignored_pack(pack):
    pack.START_HERE.unlink(missing_ok=True)
    pack.main(["--check", "--skip-tests"])
    assert not pack.START_HERE.exists()


def test_check_reports_the_same_verdict_as_a_real_run(pack, capsys):
    """A dry run that disagreed with the real one would be worse than none."""
    checked = pack.main(["--check", "--skip-tests"])
    check_out = capsys.readouterr().out

    written = pack.main(["--skip-tests"])
    write_out = capsys.readouterr().out

    assert checked == written
    verdict = lambda out: out.splitlines()[0]  # noqa: E731 - "build_context_pack: <status>"
    assert verdict(check_out) == verdict(write_out)


def test_check_says_it_wrote_nothing(pack, capsys):
    pack.main(["--check", "--skip-tests"])
    out = capsys.readouterr().out
    assert "working tree untouched" in out
    assert "wrote" not in out.replace("would write", "")


def test_a_real_run_still_writes(pack):
    """The guard against fixing the dry run by breaking the normal path."""
    pack.START_HERE.unlink(missing_ok=True)
    pack.main(["--skip-tests"])
    assert pack.START_HERE.exists()
