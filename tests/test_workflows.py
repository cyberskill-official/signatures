"""Workflow definition checks.

These exist because of a real failure. The request workflow skipped silently
three times on its first live test, and the cause was not the logic - it was
YAML:

    if: >-
      contains(a, 'x') &&
      contains(fromJSON('[...]'),
               github.event.issue.author_association)

A folded scalar (`>-`) folds newlines into spaces only for lines at the SAME
indentation. The third line was indented deeper for readability, so YAML kept
its newline literally. GitHub received an expression with a line break inside
contains(), evaluated it false, and skipped the job with no error anywhere.

Nothing about that is visible in review. A test is the only thing that catches
it, so here it is.
"""
import glob
import os
import re

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOWS = sorted(glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")))


def conditions(doc):
    """Every `if:` in a workflow, as (location, value)."""
    for jname, job in (doc.get("jobs") or {}).items():
        if job.get("if") is not None:
            yield f"jobs.{jname}.if", job["if"]
        for i, step in enumerate(job.get("steps") or []):
            if step.get("if") is not None:
                name = step.get("name", f"steps[{i}]")
                yield f"jobs.{jname}.{name}.if", step["if"]


def test_there_are_workflows():
    assert WORKFLOWS, "no workflow files found - has the path changed?"


@pytest.mark.parametrize("path", WORKFLOWS, ids=os.path.basename)
def test_workflow_parses(path):
    assert yaml.safe_load(open(path, encoding="utf-8")) is not None


@pytest.mark.parametrize("path", WORKFLOWS, ids=os.path.basename)
def test_no_newline_inside_a_condition(path):
    """The bug that cost a live debugging session. Never again."""
    doc = yaml.safe_load(open(path, encoding="utf-8"))
    for where, expr in conditions(doc):
        assert "\n" not in str(expr), (
            f"{os.path.basename(path)} {where} contains a literal newline.\n"
            f"  {expr!r}\n"
            f"A folded scalar only folds lines at the same indentation. Put "
            f"the whole expression on one line, or align every continuation "
            f"line with the first.")


@pytest.mark.parametrize("path", WORKFLOWS, ids=os.path.basename)
def test_conditions_have_balanced_parentheses(path):
    """A truncated expression evaluates false and skips silently."""
    doc = yaml.safe_load(open(path, encoding="utf-8"))
    for where, expr in conditions(doc):
        s = str(expr)
        assert s.count("(") == s.count(")"), \
            f"{os.path.basename(path)} {where} has unbalanced parentheses: {s!r}"


@pytest.mark.parametrize("path", WORKFLOWS, ids=os.path.basename)
def test_third_party_actions_are_pinned_to_a_sha(path):
    """A mutable tag on an action is remote code execution into a workflow
    that holds contents:write and pages:write."""
    text = open(path, encoding="utf-8").read()
    for m in re.finditer(r"uses:\s*([^\s#]+)", text):
        ref = m.group(1)
        if ref.startswith("./") or ref.startswith("docker://"):
            continue
        assert "@" in ref, f"{os.path.basename(path)}: {ref} has no ref at all"
        pin = ref.split("@", 1)[1]
        assert re.fullmatch(r"[0-9a-f]{40}", pin), (
            f"{os.path.basename(path)}: {ref} is pinned to {pin!r}, not a "
            f"full commit SHA")


@pytest.mark.parametrize("path", WORKFLOWS, ids=os.path.basename)
def test_permissions_are_declared(path):
    """Without an explicit block the job inherits whatever the repository
    default happens to be, which is not a decision anyone made here."""
    doc = yaml.safe_load(open(path, encoding="utf-8"))
    has_top = "permissions" in doc
    for jname, job in (doc.get("jobs") or {}).items():
        assert has_top or "permissions" in job, \
            f"{os.path.basename(path)}: jobs.{jname} has no permissions block"


def test_issue_body_is_never_interpolated_into_a_shell():
    """`${{ github.event.issue.body }}` inside run: is shell injection - the
    body is written by whoever opened the issue. It must arrive via env or a
    file."""
    for path in WORKFLOWS:
        doc = yaml.safe_load(open(path, encoding="utf-8"))
        for jname, job in (doc.get("jobs") or {}).items():
            for i, step in enumerate(job.get("steps") or []):
                run = step.get("run")
                if not run:
                    continue
                assert "github.event.issue.body" not in run, (
                    f"{os.path.basename(path)} jobs.{jname}.steps[{i}] "
                    f"interpolates the issue body into a shell command")
                assert "github.event.issue.title" not in run, (
                    f"{os.path.basename(path)} jobs.{jname}.steps[{i}] "
                    f"interpolates the issue title into a shell command")
