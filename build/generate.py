#!/usr/bin/env python3
"""
Generate every signature style for every employee.

There are ten styles and one record. Nobody gets different facts - what
changes is where the colour sits, whether the photo leads, and how tall the
block ends up. People pick from their own page; `style:` in the record makes
that choice permanent, and the default is whatever STYLES lists first.

Read styles.py for the four rules every style has to satisfy, model.py for
the tokens, and README.md for why the colour architecture is what it is.

Rules that must not be quietly changed:
  - All text inherits the client's colour unless the cell pins its own
    background. Accent lives in icons and in pinned blocks only.
  - color:inherit on <a> is load-bearing: omitting a colour does NOT make a
    link inherit, the UA stylesheet still paints it link-blue (1.75:1 on dark).
  - The real table is width="100%" capped by max-width. A hard width pins it
    at 520px on a 320px phone and forces horizontal scroll.
  - The mso wrapper is width="100%", NOT a fixed 520. Word ignores max-width,
    so a fixed wrapper pinned the table at 520px inside Outlook's reading pane
    and overflowed it by 36px at 500px and 136px at 400px.
  - Every image is decorative and carries alt="": all information is already
    present as real text, so alt would duplicate it for a screen reader.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import DOCS_PEOPLE, load_company, load_people  # noqa: E402
from styles import DEFAULT_STYLE, STYLES, render  # noqa: E402

GMAIL_LIMIT = 10000


def one(rec, company, base, style_id):
    """Render and flatten. Newlines are stripped except before an mso
    conditional, which has to start its own line to be recognised."""
    return re.sub(r"\n(?!<!--\[if)", "", render(style_id, rec, company, base))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=None,
                    help="Override the base URL (default: company.yml)")
    ap.add_argument("--out-root", default=DOCS_PEOPLE,
                    help="Where to write <id>/. Validation points this at a "
                         "temp dir so a localhost base URL never lands in the "
                         "published tree.")
    ap.add_argument("--only-style", default=None,
                    help="Render just one style. For quick iteration; the "
                         "real build always writes all of them.")
    args = ap.parse_args()

    company = load_company()
    base = args.base or company["base_url"]
    if not base.endswith("/"):
        base += "/"
    people = load_people(company)
    if not people:
        raise SystemExit("No employee records found in src/people/")

    wanted = ([s for s in STYLES if s[0] == args.only_style]
              if args.only_style else STYLES)
    if not wanted:
        raise SystemExit(f"unknown style '{args.only_style}'")

    manifest = {"base": base, "styles": [
        {"id": s, "label": l, "note": n} for s, l, n, _ in STYLES],
        "people": []}
    worst = 0

    for rec in people:
        d = os.path.join(args.out_root, rec["id"])
        os.makedirs(d, exist_ok=True)
        chosen = rec.get("style") or DEFAULT_STYLE
        sizes, over_any = {}, []

        for sid, _label, _note, _fn in wanted:
            markup = one(rec, company, base, sid)
            sizes[sid] = len(markup)
            worst = max(worst, len(markup))
            if len(markup) >= GMAIL_LIMIT:
                over_any.append(sid)
            with open(os.path.join(d, f"sig-{sid}.html"), "w",
                      encoding="utf-8") as fh:
                fh.write(markup)

        # signature.html stays the person's chosen style, so every link and
        # bookmark that already points at it keeps working.
        if not args.only_style:
            with open(os.path.join(d, "signature.html"), "w",
                      encoding="utf-8") as fh:
                fh.write(one(rec, company, base, chosen))

        manifest["people"].append({
            "id": rec["id"], "name": rec["name"], "role": rec["role"],
            "style": chosen, "chars": sizes.get(chosen, 0),
            "sizes": sizes, "over_limit": bool(over_any),
            "over_styles": over_any,
        })
        flag = f"  OVER GMAIL LIMIT: {', '.join(over_any)}" if over_any else ""
        biggest = max(sizes.values()) if sizes else 0
        print(f"  {rec['id']:22} {len(sizes):>2} styles, "
              f"largest {biggest:>5} chars "
              f"({biggest / GMAIL_LIMIT * 100:4.1f}% of Gmail limit), "
              f"using '{chosen}'{flag}")

    # Only the real build owns the manifest. Validation regenerates against a
    # localhost base URL into a temp dir; letting that write here would leave
    # build/manifest.json describing signatures nobody ships, with character
    # counts short by the length of the real domain.
    if os.path.abspath(args.out_root) == os.path.abspath(DOCS_PEOPLE):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "manifest.json"), "w") as fh:
            json.dump(manifest, fh, indent=2)
    else:
        print("  (temp out-root: build/manifest.json left alone)")
    print(f"{len(people)} person(s) x {len(wanted)} style(s) -> "
          f"{args.out_root}/<id>/sig-<style>.html")


if __name__ == "__main__":
    main()
