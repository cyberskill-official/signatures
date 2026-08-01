#!/usr/bin/env python3
"""Pick which signature previews a pull request should show, and write the
markdown that embeds them.

Why this exists
---------------
CI already screenshots every signature at three widths and three appearances,
then uploads them as a zip. Reviewing a change therefore means downloading a
file and opening PNGs, which nobody does - so signatures get reviewed by
reading YAML. Almost every rendering defect found in this project was found by
looking at a picture, not by reading an assertion.

Why the images are pushed to a branch instead of inlined
--------------------------------------------------------
The obvious approach - base64 the PNG into the comment as a data: URI - does
not work, for two independent reasons:

  1. GitHub's markdown sanitiser only allows http, https and relative URLs in
     an <img src>. A data: URI is stripped, and the image renders as nothing.
  2. Even if it were allowed, one screenshot is ~130,000 characters once
     base64-encoded, against a 65,536-character comment limit. A single image
     is twice the entire budget.

So the PNGs go to an orphan `previews` branch and the comment links them from
raw.githubusercontent.com. The commit SHA is in the path because GitHub proxies
images through camo, which caches by URL - without a unique path per push, a
re-pushed branch would keep showing the first screenshot taken.

This only works on a public repository. On a private one raw.githubusercontent
requires auth and the images render broken; the guard for that is in the
workflow, not here.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SHOTS = os.path.join(ROOT, "validation", "screenshots")

# The three views worth a reviewer's attention, and what each one is for.
# Deliberately not all seven - a wall of images is skipped as fast as a zip.
VIEWS = [
    ("desktop-loaded", "Desktop", 300),
    ("narrow-loaded",  "Phone",   210),
    ("dark-gmaildark", "Gmail dark", 300),
]

# Above this many people, the comment links the artifact instead. A company-wide
# change touching 30 records should not paste 90 images into a pull request.
MAX_PEOPLE = 4


def changed_ids(base_ref):
    """Which people this pull request actually affects.

    A record or avatar change affects one person. A change to company.yml or
    anything under build/ changes the output for everyone, because both feed
    every signature.
    """
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", f"origin/{base_ref}...HEAD"],
            capture_output=True, text=True, check=True, cwd=ROOT).stdout
    except subprocess.CalledProcessError as e:
        print(f"could not diff against origin/{base_ref}: {e}", file=sys.stderr)
        return None, "diff failed"

    files = [f.strip() for f in out.splitlines() if f.strip()]
    everyone = any(
        f == "src/company.yml" or f.startswith("build/") for f in files)
    if everyone:
        return None, "company-wide change"

    ids = set()
    for f in files:
        if f.startswith("src/people/") or f.startswith("src/avatars/"):
            stem = os.path.splitext(os.path.basename(f))[0]
            if stem and not stem.startswith("_"):
                ids.add(stem)
    return sorted(ids), None


def published_ids():
    """Everyone the build actually produced, in manifest order."""
    try:
        m = json.load(open(os.path.join(ROOT, "build", "manifest.json")))
        return [p["id"] for p in m["people"]]
    except Exception as e:
        print(f"could not read manifest: {e}", file=sys.stderr)
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-ref", required=True)
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--branch", default="previews")
    ap.add_argument("--stage", required=True, help="directory to copy PNGs into")
    ap.add_argument("--out", required=True, help="markdown output file")
    args = ap.parse_args()

    built = published_ids()
    ids, why_all = changed_ids(args.base_ref)
    if ids is None:                       # company-wide, or the diff failed
        ids, note = built, why_all
    else:
        ids, note = [i for i in ids if i in built], None

    short = args.sha[:12]
    md, staged = [], 0

    if not ids:
        # Not a failure. A docs-only or workflow-only pull request changes no
        # signature, and saying so is more useful than an empty heading.
        open(args.out, "w").write(
            "_No signature changed in this pull request, so there is "
            "nothing to preview._\n")
        print("nothing to preview")
        return 0

    shown, hidden = ids[:MAX_PEOPLE], ids[MAX_PEOPLE:]

    for pid in shown:
        cells, heads = [], []
        for suffix, label, width in VIEWS:
            src = os.path.join(SHOTS, f"{pid}-{suffix}.png")
            if not os.path.isfile(src):
                continue
            rel = f"pr-{args.pr}/{short}/{pid}-{suffix}.png"
            dst = os.path.join(args.stage, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            staged += 1
            url = (f"https://raw.githubusercontent.com/{args.repo}/"
                   f"{args.branch}/{rel}")
            heads.append(label)
            cells.append(f'<img src="{url}" width="{width}" alt="{pid}, {label}">')

        if not cells:
            md.append(f"**`{pid}`** - no screenshot was produced.\n")
            continue

        md.append(f"**`{pid}`**\n")
        md.append("| " + " | ".join(heads) + " |")
        md.append("|" + "---|" * len(heads))
        md.append("| " + " | ".join(cells) + " |")
        md.append("")

    if note:
        md.append(f"_Showing everyone because this is a {note} - "
                  f"it changes every signature._\n")
    if hidden:
        md.append(f"_{len(hidden)} more not shown: "
                  + ", ".join(f"`{i}`" for i in hidden)
                  + ". All screenshots are in the run artifact._\n")

    md.append("_Dark is Gmail's own inversion, which is the case that actually "
              "breaks. The full set - blocked images, forced dark, three "
              "engines - is in the `render-evidence` artifact._")

    open(args.out, "w").write("\n".join(md) + "\n")
    print(f"staged {staged} image(s) for {len(shown)} person(s)")

    gho = os.environ.get("GITHUB_OUTPUT")
    if gho:
        with open(gho, "a") as f:
            f.write(f"staged={staged}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
