"""The documentation, checked against the code it describes.

Every other kind of drift in this repository is caught by something. Prose is
not, and prose is what a new contributor reads first. The audit that prompted
this file found nine stale claims, and the two that would actually have cost
someone an afternoon were both instructions: CONTRIBUTING listed a style id
that no longer builds, and OUTLOOK.md told the person doing the manual Word
pass to open a file that now 404s. Nobody had touched either line - they went
stale because something else changed.

The rest were measurements that had quietly stopped being true: "81 tests"
when there were 326, and "248px tall in both, the layout does not reflow"
when the layout reflows in six of the nine styles. A number in a README is a
claim, and an unchecked claim decays into a lie without anyone lying.

So these tests read the prose and compare it to the thing it describes. They
need no browser and no network, and they run in the same second as everything
else.
"""
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")
sys.path.insert(0, os.path.join(ROOT, "build"))

import styles as S  # noqa: E402

LIVE = {sid for sid, _fn in S.STYLES}

# Every style function that exists, registered or not. `s_split` still sits in
# styles.py so the layout is recoverable; it is not in STYLES, so naming it in
# a document is an instruction to do something impossible.
DEFINED = {n[2:] for n in dir(S) if n.startswith("s_")}
RETIRED = DEFINED - LIVE

DOCS = ["README.md", "CONTRIBUTING.md", os.path.join("validation", "OUTLOOK.md")]


def _read(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        pytest.skip(f"{rel} not present")
    with open(p, encoding="utf-8") as fh:
        return fh.read()


# --------------------------------------------------------------------------
# Style ids


@pytest.mark.parametrize("rel", DOCS)
def test_no_document_names_a_retired_style(rel):
    """The bug that shipped twice.

    A retired style may still be named, but only on a line that says it is
    retired - otherwise the reader takes it as a live option.
    """
    if not RETIRED:
        pytest.skip("no retired styles to confuse anyone with")
    src = _read(rel)
    offenders = []
    for n, line in enumerate(src.splitlines(), 1):
        if "retired" in line.lower():
            continue
        for sid in sorted(RETIRED):
            if re.search(rf"`{sid}`", line):
                offenders.append(f"{rel}:{n}: `{sid}`")
    assert not offenders, (
        f"{offenders} name a style that is not in STYLES. Anyone following "
        f"that instruction gets a build failure, or opens a file that 404s. "
        f"Either re-register the style or say on the same line that it was "
        f"retired.")


def test_contributing_lists_exactly_the_live_styles():
    """The list a contributor copies from has to be the list that builds."""
    src = _read("CONTRIBUTING.md")
    m = re.search(r"Valid values are the ids in[^:]*:(.+?)\.\s", src, re.S)
    assert m, "CONTRIBUTING no longer states the valid style ids"
    listed = set(re.findall(r"`([a-z][a-z-]*)`", m.group(1)))
    assert listed == LIVE, (
        f"CONTRIBUTING lists {sorted(listed)}; STYLES has {sorted(LIVE)}. "
        f"Missing from the docs: {sorted(LIVE - listed)}. "
        f"Named but not registered: {sorted(listed - LIVE)}.")


# --------------------------------------------------------------------------
# Validation gates


def test_every_check_id_is_documented_and_every_documented_id_exists():
    """The README gate table is the list people actually read.

    V13, V14 and V15 were added to check.py and never reached it, so the
    published summary of what the suite guarantees was three gates short.
    """
    check = os.path.join(ROOT, "validation", "check.py")
    if not os.path.isfile(check):
        pytest.skip("check.py not present")
    with open(check, encoding="utf-8") as fh:
        declared = set(re.findall(r'"(V\d+)"', fh.read()))

    readme = _read("README.md")
    documented = set(re.findall(r"^\|\s*(V\d+)\s*\|", readme, re.M))

    assert declared == documented, (
        f"check.py declares {sorted(declared, key=_num)}; the README table "
        f"documents {sorted(documented, key=_num)}. "
        f"Undocumented: {sorted(declared - documented, key=_num)}. "
        f"Documented but gone: {sorted(documented - declared, key=_num)}.")


def _num(v):
    return int(v[1:])


# --------------------------------------------------------------------------
# Measurements


def test_the_test_count_in_the_readme_is_the_real_one(request):
    """A stated count is a measurement, and this one had drifted 4x.

    Read from the live session rather than by parsing test files, because
    parametrised tests make any static count wrong.
    """
    readme = _read("README.md")
    m = re.search(r"pytest tests/ -q\s*#\s*([\d,]+) tests", readme)
    assert m, "the README no longer states a test count next to the command"
    stated = int(m.group(1).replace(",", ""))

    items = request.session.items
    ran = {os.path.basename(str(getattr(i, "path", i.fspath))) for i in items}
    present = {f for f in os.listdir(TESTS) if re.fullmatch(r"test_.*\.py", f)}
    if ran != present:
        pytest.skip(f"partial run - collected {sorted(ran)}, not {sorted(present)}")

    assert len(items) == stated, (
        f"README says {stated} tests; the suite collects {len(items)}. "
        f"Update the number - it is the only claim in the README a reader "
        f"can check in one command, so it is the first one they will notice "
        f"is wrong.")


def test_every_file_named_in_the_readme_tree_exists():
    """The repository layout drifted silently as files were added.

    Only concrete names are checked. `<id>.yml` and `sig-<style>.html` are
    placeholders and are skipped.
    """
    readme = _read("README.md")
    m = re.search(r"\n```\nsignature/\n(.+?)\n```", readme, re.S)
    assert m, "the README no longer contains a repository tree"

    named = set()
    for tok in re.findall(r"[\w.\-]+\.(?:py|json|md|yml|txt|sh|html|png)",
                          m.group(1)):
        if "<" not in tok:
            named.add(tok)
    assert named, "parsed no filenames out of the tree - the regex has rotted"

    on_disk = set()
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in {".git", "node_modules", "__pycache__",
                                    ".pytest_cache", "vendor"}]
        on_disk.update(filenames)

    missing = sorted(named - on_disk)
    assert not missing, (
        f"the README tree names {missing}, which are not in the repository. "
        f"A layout diagram that lists files nobody can find is worse than no "
        f"diagram.")
