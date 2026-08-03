#!/usr/bin/env python3
"""The record nobody has yet, which the render suites must survive anyway.

Every pixel-level check in this repo - validation/check.py and
validation/crossclient.py - runs against `load_people()`, which means it only
ever sees the people who actually work here. Today that is one record: one
name length, one role, one avatar, four contact rows.

That gap is not theoretical. CI failed on 2026-08-03 because an email address
grew by ten characters, which pushed two styles past the 288px content box at
phone width. No test anticipated it, because no test had ever rendered
anything but the real record. The content moved and the code did not.

So the suites also render this: every text field at the length the schema
permits, the maximum sensible number of social links, and a name_vi built
from the stacked diacritics CDS names as its clipping canary. If a style
holds for this, it holds for whoever is hired next. If it does not, that is
a defect discovered before a person exists rather than during their first
week.

This is deliberately NOT a file under src/people/. It must never publish, and
a real record that happened to be named `_worstcase.yml` would be skipped by
the loader anyway - which would make it invisible to exactly the suites that
need it.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import TEXT_LIMITS, AVATARS_SRC   # noqa: E402

# Real Vietnamese words, padded to the cap rather than a wall of one letter:
# a repeated character is a best case for line breaking, and the point here
# is the worst one. The diacritics are the CDS canary set.
_LONG_NAME = "Nguyễn Thị Ánh Nguyệt Trầm Hương Lê Hoàng Phước Vĩnh An"
_LONG_ROLE = ("Senior Principal Software Engineer and Head of Platform "
              "Architecture")
_CANARY = "ỚẾỰỎÃỸ Trịnh Thái Anh Nguyễn Thị Ánh Nguyệt"


def _cap(text, field):
    """Fill the field to its limit without inventing characters past it."""
    limit = TEXT_LIMITS[field]
    if len(text) >= limit:
        return text[:limit].rstrip()
    return (text + " " + text)[:limit].rstrip()


def worst_case(company, avatar_from=None):
    """A fully-populated record at the edge of every limit the schema allows.

    `avatar_from` borrows a real baked avatar so the image columns render at
    their true size; without one the portrait column collapses and the test
    measures a layout nobody will ever be sent.
    """
    domain = company["email_domains"][0]
    # The longest local part that still leaves room for the domain, so the
    # address is as wide as a record could legally make it.
    local = "nguyen-thi.anh-nguyet-tram-huong"
    email = f"{local}@{domain}"
    if len(email) > TEXT_LIMITS["email"]:
        email = f"{local[:TEXT_LIMITS['email'] - len(domain) - 1]}@{domain}"

    rec = {
        "id": "_worstcase",
        "name": _cap(_LONG_NAME, "name"),
        "name_vi": _cap(_CANARY, "name_vi"),
        "role": _cap(_LONG_ROLE, "role"),
        "email": email,
        "phone": "(+84) 906 878 091 ext. 4021",
        "phone_href": "+849068780914021",
        "website": company.get("website"),
        "website_href": company.get("website_href"),
        # Six networks. The style tests already prove a growing list costs no
        # extra rows; this proves the resulting line still fits the box.
        "socials": [
            {"label": "LinkedIn", "href": "https://linkedin.com/company/x"},
            {"label": "Facebook", "href": "https://facebook.com/x"},
            {"label": "Zalo", "href": "https://zalo.me/x"},
            {"label": "GitHub", "href": "https://github.com/x"},
            {"label": "YouTube", "href": "https://youtube.com/@x"},
            {"label": "TikTok", "href": "https://tiktok.com/@x"},
        ],
        "company": company["name"],
        "active": True,
        "order": 999,
        "avatar": None,
        "avatar_path": None,
    }
    if avatar_from and avatar_from.get("avatar_path"):
        # Point at the real person's baked files. The fixture never gets its
        # own assets baked, and a missing image would silently shrink the
        # portrait column - the opposite of a worst case.
        rec["id"] = avatar_from["id"]
        rec["avatar"] = avatar_from.get("avatar")
        rec["avatar_path"] = avatar_from["avatar_path"]
    return rec


if __name__ == "__main__":
    from model import load_company, load_people
    c = load_company()
    people = load_people(c)
    w = worst_case(c, people[0] if people else None)
    for k in ("name", "name_vi", "role", "email", "phone"):
        print(f"  {k:8} {len(str(w[k])):3} chars  {w[k]}")
    print(f"  socials  {len(w['socials'])}")
