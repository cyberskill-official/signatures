"""The validation scripts, checked without a browser.

check.py and crossclient.py need three browsers and minutes to run, so in
practice they run in CI and rarely anywhere else. That makes a mistake in
them expensive to find: V14 shipped reading `hostScrollW`, which is
crossclient.py's key name and not check.py's, and the error surfaced only
when someone with a browser ran it.

A KeyError is the lucky version. Written as `d.get("hostScrollW", 0)` the
same mistake would have made the check silently never fire - a check that
passes because it looked at nothing, which is the failure this repository
keeps finding in itself.

These tests read the source rather than running it, so they cost nothing and
run everywhere.
"""
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VALIDATION = os.path.join(ROOT, "validation")


def _src(name):
    p = os.path.join(VALIDATION, name)
    if not os.path.isfile(p):
        pytest.skip(f"{name} not present")
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def _probe_keys(src, marker):
    """The keys the in-page probe actually returns."""
    i = src.index(marker)
    body = src[i:]
    body = body[:body.index("};")]
    keys = set(re.findall(r"(\w+)\s*:", body))
    # shorthand properties - `return { fontProbe, tableW: ... }`
    for chunk in re.split(r"[,{}]", body):
        chunk = chunk.strip()
        if re.fullmatch(r"\w+", chunk):
            keys.add(chunk)
    return keys


@pytest.mark.parametrize("script,marker", [
    ("check.py", "return { fontProbe"),
    ("crossclient.py", "return {"),
])
def test_every_probe_key_read_is_a_key_the_probe_returns(script, marker):
    """The bug that shipped: reading a key from the wrong script's probe."""
    src = _src(script)
    try:
        keys = _probe_keys(src, marker)
    except ValueError:
        pytest.skip(f"{script}: could not locate the probe return")
    read = set(re.findall(r'd\["(\w+)"\]', src))
    read |= set(re.findall(r"d\['(\w+)'\]", src))
    read |= set(re.findall(r'd\.get\("(\w+)"', src))
    # Keys the script adds to the dict itself after probing, rather than
    # reading back from the page.
    added = set(re.findall(r"d\.update\(([^)]*)\)", src))
    for chunk in added:
        keys |= set(re.findall(r"(\w+)\s*=", chunk))
    keys |= {"person", "width", "images", "style", "screenshot", "engine",
             "client", "label", "transform", "transformed", "scheme",
             "copyOk", "status", "kind"}
    missing = sorted(k for k in read if k not in keys)
    assert not missing, (
        f"{script} reads {missing} from the probe result, and the probe does "
        f"not return them. Written with .get() this would have failed "
        f"silently instead of raising.")


def test_no_probe_key_is_read_with_a_silent_default():
    """`d.get("k", 0)` on a probe key turns a missing measurement into a
    passing check. If the key is absent the run is not clean, it is blind."""
    offenders = []
    for script in ("check.py", "crossclient.py"):
        src = _src(script)
        for m in re.finditer(r'd\.get\("(\w+)",\s*([^)]+)\)', src):
            offenders.append(f"{script}: d.get({m.group(1)!r}, {m.group(2)})")
    assert not offenders, (
        "a probe key read with a fallback default - if the measurement is "
        f"missing the check quietly passes: {offenders}")


@pytest.mark.parametrize("script", ["check.py", "crossclient.py"])
def test_every_check_id_is_unique_and_sequential(script):
    """A duplicated id makes two different defects report as one thing, and
    a gap usually means a check was deleted without anyone noticing."""
    src = _src(script)
    prefix = "V" if script == "check.py" else "X"
    ids = sorted({int(n) for n in
                  re.findall(rf'"{prefix}(\d+)"', src)})
    assert ids, f"{script} declares no {prefix}n check ids"
    gaps = [n for n in range(min(ids), max(ids) + 1) if n not in ids]
    undeclared = [n for n in gaps
                  if f"{prefix}{n} is retired" not in src]
    assert not undeclared, (
        f"{script} has no {prefix}{undeclared}. If a check was removed, say "
        f'so in the source with "{prefix}<n> is retired" and do not reuse the '
        f"number - an old report and a new one would then disagree about "
        f"what it meant. A silent gap usually means a check was lost.")


@pytest.mark.parametrize("script", ["check.py", "crossclient.py"])
def test_findings_are_counted_after_the_last_one_is_added(script):
    """The gate reads the counts, so anything added after they are computed
    is reported but not enforced.

    This shipped: V14 and V15 were appended below the counts, so a run with
    two HIGH findings printed them, wrote them to report.json, and exited 0.
    CI would have gone green on a real defect. The findings list is shared by
    reference, which is exactly why it looked correct everywhere except the
    one place that mattered.
    """
    src = _src(script)
    if "counts = {" not in src:
        pytest.skip(f"{script} does not compute counts")
    tail = src[src.index("counts = {"):]
    stragglers = re.findall(r"\n\s+add\(\s*[\"'](HIGH|MED|LOW)", tail)
    assert not stragglers, (
        f"{script} adds {len(stragglers)} finding(s) after counting them "
        f"({sorted(set(stragglers))}). They will be printed and never "
        f"enforced - move the count below every check.")
