"""Tests for the pull request preview strip.

The reason these are worth writing: the first design for this feature was to
base64 the screenshot into the comment as a data: URI. That fails silently -
GitHub's sanitiser drops the attribute and the image renders as nothing, with
no error anywhere. A green check and an invisible image is exactly the kind of
failure this repository keeps producing, so the scheme and the size are both
asserted here rather than trusted.
"""
import base64
import importlib.util
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, ".github", "scripts", "pr_previews.py")

# GitHub rejects a comment body over this. One base64 screenshot is roughly
# twice it on its own.
COMMENT_LIMIT = 65536


def load():
    spec = importlib.util.spec_from_file_location("pr_previews", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def pv(tmp_path, monkeypatch):
    """The module, pointed at a fake screenshot directory."""
    mod = load()
    shots = tmp_path / "shots"
    shots.mkdir()
    monkeypatch.setattr(mod, "SHOTS", str(shots))
    mod._shots = shots
    return mod


def make_shots(pv, pid):
    for suffix, _, _ in pv.VIEWS:
        (pv._shots / f"{pid}-{suffix}.png").write_bytes(b"\x89PNG\r\n\x1a\n")


def run(pv, tmp_path, ids, note=None, built=None, pr="7"):
    monkey = built if built is not None else ids
    pv.changed_ids = lambda base: (ids, note)
    pv.published_ids = lambda: monkey
    stage = tmp_path / "stage"
    stage.mkdir(exist_ok=True)
    out = tmp_path / "out.md"
    import sys
    sys.argv = ["x", "--base-ref", "main", "--repo", "o/r", "--pr", pr,
                "--sha", "abcdef0123456789", "--stage", str(stage),
                "--out", str(out)]
    pv.main()
    return out.read_text(), stage


def test_nothing_changed_says_so_instead_of_crashing(pv, tmp_path):
    md, stage = run(pv, tmp_path, [], built=["someone"])
    assert "nothing to preview" in md.lower()
    assert list(stage.rglob("*.png")) == []


def test_one_person_gets_three_views(pv, tmp_path):
    make_shots(pv, "mai-tran")
    md, stage = run(pv, tmp_path, ["mai-tran"])
    assert len(list(stage.rglob("*.png"))) == 3
    for _, label, _ in pv.VIEWS:
        assert label in md


def test_images_are_https_never_data_uris(pv, tmp_path):
    """The whole reason this is not inlined. A data: URI is silently stripped."""
    make_shots(pv, "mai-tran")
    md, _ = run(pv, tmp_path, ["mai-tran"])
    assert "data:" not in md
    assert 'src="https://raw.githubusercontent.com/' in md


def test_path_carries_the_sha_so_camo_cannot_serve_a_stale_image(pv, tmp_path):
    make_shots(pv, "mai-tran")
    md, stage = run(pv, tmp_path, ["mai-tran"])
    assert "abcdef012345" in md
    assert any("abcdef012345" in str(p) for p in stage.rglob("*.png"))


def test_a_second_push_does_not_reuse_the_first_url(pv, tmp_path):
    """Two SHAs must not collide, or the reviewer reviews the old picture."""
    make_shots(pv, "mai-tran")
    first, _ = run(pv, tmp_path, ["mai-tran"])
    pv_two = load()
    pv_two.SHOTS = pv.SHOTS
    pv_two.changed_ids = lambda base: (["mai-tran"], None)
    pv_two.published_ids = lambda: ["mai-tran"]
    out = tmp_path / "second.md"
    import sys
    sys.argv = ["x", "--base-ref", "main", "--repo", "o/r", "--pr", "7",
                "--sha", "9999999999999999", "--stage", str(tmp_path / "s2"),
                "--out", str(out)]
    (tmp_path / "s2").mkdir(exist_ok=True)
    pv_two.main()
    assert out.read_text() != first


def test_company_wide_change_explains_why_everyone_is_shown(pv, tmp_path):
    for pid in ("a", "b"):
        make_shots(pv, pid)
    md, _ = run(pv, tmp_path, None, note="company-wide change",
                built=["a", "b"])
    assert "company-wide change" in md
    assert "`a`" in md and "`b`" in md


def test_large_change_is_capped_and_says_what_it_hid(pv, tmp_path):
    ids = [f"p{i}" for i in range(pv.MAX_PEOPLE + 3)]
    for pid in ids:
        make_shots(pv, pid)
    md, stage = run(pv, tmp_path, ids)
    assert len(list(stage.rglob("*.png"))) == pv.MAX_PEOPLE * len(pv.VIEWS)
    assert "3 more not shown" in md
    for pid in ids[pv.MAX_PEOPLE:]:
        assert f"`{pid}`" in md


def test_missing_screenshot_is_reported_not_swallowed(pv, tmp_path):
    md, stage = run(pv, tmp_path, ["ghost"])
    assert "no screenshot" in md.lower()
    assert list(stage.rglob("*.png")) == []


def test_unpublished_id_is_dropped(pv, tmp_path):
    """A record set to active: false has no page and no screenshot."""
    make_shots(pv, "leaver")
    md, _ = run(pv, tmp_path, ["leaver"], built=[])
    assert "nothing to preview" in md.lower()


def test_comment_stays_well_under_githubs_limit(pv, tmp_path):
    ids = [f"p{i}" for i in range(pv.MAX_PEOPLE + 10)]
    for pid in ids:
        make_shots(pv, pid)
    md, _ = run(pv, tmp_path, ids)
    assert len(md) < COMMENT_LIMIT // 4, (
        f"preview markdown is {len(md)} chars; the rest of the comment still "
        f"has to fit in {COMMENT_LIMIT}")


def test_inlining_would_have_blown_the_limit(pv, tmp_path):
    """Documents the constraint that killed the original design, using the
    real screenshot rather than an assertion about it."""
    real = os.path.join(ROOT, "validation", "screenshots",
                        "stephen-cheng-desktop-loaded.png")
    if not os.path.isfile(real):
        pytest.skip("no render evidence in this checkout")
    encoded = len(base64.b64encode(open(real, "rb").read())) + len("data:image/png;base64,")
    assert encoded > COMMENT_LIMIT, (
        "a screenshot now fits in a comment - the previews branch could be "
        "replaced with an inline data: URI, if GitHub ever allowed one")
