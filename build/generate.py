#!/usr/bin/env python3
"""
Generate one signature per employee.

The markup is identical to the design that passed validation - only the
content varies per person. Read model.py for the tokens and README.md for why
the colour architecture is what it is.

Rules that must not be quietly changed:
  - All text inherits the client's colour. Accent lives in icons only.
  - color:inherit on <a> is load-bearing: omitting a colour does NOT make a
    link inherit, the UA stylesheet still paints it link-blue (1.75:1 on dark).
  - The real table is width="100%" capped by max-width. A hard width pins it
    at 520px on a 320px phone and forces horizontal scroll.
  - The mso wrapper is width="100%", NOT a fixed 520. Word ignores max-width,
    so a fixed wrapper pinned the table at 520px inside Outlook's reading pane
    and overflowed it by 36px at 500px and 136px at 400px. The cap bought
    nothing to pay for that: every element in the block is left-aligned and
    the widest line of ink is about 285px, so removing the cap changes only
    how much empty space trails the content. Measured identical at 400px and
    1400px, height 244px at both.
  - Every image is decorative and carries alt="": all information is already
    present as real text, so alt would duplicate it for a screen reader.
"""
import argparse
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import (ACCENT, AVATAR, DOCS_PEOPLE, GUTTER, ICON, ICON_GAP, LOGO,
                   MSO, OCHRE, RULE_W, SANS, TABLE_W, ZWSP, asset_url,
                   load_company, load_people, person_asset, shared_asset)


def esc(v):
    """Escape for a text node or a double-quoted attribute.

    Records arrive by pull request, so every value that reaches markup goes
    through here. model.py separately allowlists URL schemes, which escaping
    cannot do - an escaped javascript: URL still runs.
    """
    return html.escape("" if v is None else str(v), quote=True)


def link(text, href, size=14):
    return (f'<a href="{esc(href)}" style="color:inherit;'
            f'text-decoration:underline;font-size:{size}px;">'
            f'<span style="white-space:nowrap;">{esc(text)}</span></a>')


def img(src, w, h, extra=""):
    return (f'<img src="{esc(src)}" width="{w}" height="{h}" alt="" '
            f'style="display:block;width:{w}px;height:{h}px;border:0;'
            f'outline:none;-ms-interpolation-mode:bicubic;{extra}"/>')


def rows_for(rec):
    """Build the contact rows. A missing field drops its row entirely."""
    rows = []
    rows.append(("mail", [(rec["email"], f'mailto:{rec["email"]}')]))
    if rec.get("phone"):
        rows.append(("phone", [(rec["phone"], f'tel:{rec["phone_href"]}')]))
    if rec.get("website"):
        rows.append(("globe", [(rec["website"], rec["website_href"])]))
    if rec.get("socials"):
        rows.append(("users", [(s["label"], s["href"]) for s in rec["socials"]]))
    return rows


def contact_table(rec, base):
    out = []
    rows = rows_for(rec)
    for i, (icon, links) in enumerate(rows):
        last = i == len(rows) - 1
        url = asset_url(base, f"assets/shared/icon-{icon}-2x.png",
                        shared_asset(f"icon-{icon}-2x.png"))
        body = '<span style="font-size:14px;"> | </span>'.join(
            link(t, h) for t, h in links)
        out.append(
            f'<tr>'
            f'<td width="{ICON}" valign="top" style="width:{ICON}px;'
            f'padding:2px 0 0 0;line-height:0;font-size:0;">'
            f'{img(url, ICON, ICON)}</td>'
            f'<td valign="top" style="padding:0 0 0 {ICON_GAP}px;font-size:14px;'
            f'line-height:22px;{MSO}">{body}</td></tr>')
        if not last:
            out.append(f'<tr><td colspan="2" height="6" style="height:6px;'
                       f'font-size:0;line-height:0;{MSO}">&nbsp;</td></tr>')
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" '
            f'border="0" style="border-collapse:collapse;">{"".join(out)}</table>')


def identity_block(rec):
    parts = [f'<div style="font-size:22px;line-height:28px;font-weight:bold;'
             f'letter-spacing:-0.2px;{MSO}">{esc(rec["name"])}</div>']
    if rec.get("name_vi"):
        parts.append(f'<div style="font-size:15px;line-height:20px;'
                     f'padding-top:2px;{MSO}" lang="vi">'
                     f'{esc(rec["name_vi"])}</div>')
    parts.append(f'<div style="font-size:14px;line-height:20px;padding-top:2px;'
                 f'{MSO}">{esc(rec["role"])} - {esc(rec["company"])}</div>')
    return "".join(parts)


def footer_lockup(company, base):
    url = asset_url(base, f"assets/shared/logo-{LOGO}-2x.png",
                    shared_asset(f"logo-{LOGO}-2x.png"))
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" '
            f'border="0" style="border-collapse:collapse;"><tr>'
            f'<td width="{LOGO}" valign="middle" style="width:{LOGO}px;'
            f'line-height:0;font-size:0;">{img(url, LOGO, LOGO)}</td>'
            f'<td width="10" style="width:10px;font-size:0;line-height:0;">'
            f'&nbsp;</td>'
            f'<td valign="middle" style="font-size:12px;line-height:16px;{MSO}">'
            f'{esc(company["tagline"])}</td></tr></table>')


def build(rec, company, base):
    cols = 5
    has_avatar = bool(rec.get("avatar_path"))
    if has_avatar:
        url = asset_url(base, f"assets/people/{rec['id']}/avatar-{AVATAR}-2x.png",
                        person_asset(rec["id"], f"avatar-{AVATAR}-2x.png"))
        left = (f'<td width="{AVATAR}" valign="top" style="width:{AVATAR}px;'
                f'line-height:0;font-size:0;">{img(url, AVATAR, AVATAR)}</td>'
                f'<td width="{GUTTER}" style="width:{GUTTER}px;font-size:0;'
                f'line-height:0;">&nbsp;</td>')
    else:
        # No photo: drop the avatar column entirely rather than leaving a hole.
        # The Ochre rule still anchors the block.
        left = ""
        cols = 3

    return f'''<!--[if mso]><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td><![endif]-->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;max-width:{TABLE_W}px;font-family:{SANS};">
<tr>
{left}<td width="{RULE_W}" bgcolor="{OCHRE}" style="width:{RULE_W}px;background-color:{OCHRE};font-size:0;line-height:0;">&nbsp;</td>
<td width="{GUTTER}" style="width:{GUTTER}px;font-size:0;line-height:0;">&nbsp;</td>
<td valign="top" style="vertical-align:top;">{identity_block(rec)}<div style="height:16px;font-size:0;line-height:0;{MSO}">&nbsp;</div>{contact_table(rec, base)}</td>
</tr>
<tr><td colspan="{cols}" height="18" style="height:18px;font-size:0;line-height:0;{MSO}">&nbsp;</td></tr>
<tr><td colspan="{cols}">{footer_lockup(company, base)}</td></tr>
</table>
<!--[if mso]></td></tr></table><![endif]-->'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=None,
                    help="Override the base URL (default: company.yml)")
    ap.add_argument("--out-root", default=DOCS_PEOPLE,
                    help="Where to write <id>/signature.html. Validation "
                         "points this at a temp dir so a localhost base URL "
                         "never lands in the published tree.")
    args = ap.parse_args()

    company = load_company()
    base = args.base or company["base_url"]
    if not base.endswith("/"):
        base += "/"
    people = load_people(company)
    if not people:
        raise SystemExit("No employee records found in src/people/")

    manifest = {"base": base, "people": []}
    for rec in people:
        html = re.sub(r"\n(?!<!--\[if)", "", build(rec, company, base))
        d = os.path.join(args.out_root, rec["id"])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "signature.html"), "w", encoding="utf-8") as fh:
            fh.write(html)
        over = len(html) >= 10000
        manifest["people"].append({
            "id": rec["id"], "name": rec["name"], "role": rec["role"],
            "chars": len(html), "over_limit": over,
        })
        flag = "  OVER GMAIL LIMIT" if over else ""
        print(f"  {rec['id']:22} {len(html):>5} chars "
              f"({len(html)/10000*100:4.1f}% of Gmail limit){flag}")

    # Only the real build owns the manifest. Validation regenerates against a
    # localhost base URL into a temp dir; letting that write here would leave
    # build/manifest.json describing signatures nobody ships, with character
    # counts short by the length of the real domain. CI reads this file to
    # report each signature's size, so a stale one is a wrong answer rather
    # than a missing one.
    if os.path.abspath(args.out_root) == os.path.abspath(DOCS_PEOPLE):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "manifest.json"), "w") as fh:
            json.dump(manifest, fh, indent=2)
    else:
        print(f"  (temp out-root: build/manifest.json left alone)")
    print(f"{len(people)} signature(s) -> {args.out_root}/<id>/signature.html")


if __name__ == "__main__":
    main()
