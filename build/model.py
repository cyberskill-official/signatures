#!/usr/bin/env python3
"""
Shared model: paths, palette, geometry, and employee-record loading.

Every build script imports from here so there is exactly one definition of the
design tokens and one definition of what an employee record may contain.
"""
import hashlib
import os
import re

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
PEOPLE_SRC = os.path.join(SRC, "people")
AVATARS_SRC = os.path.join(SRC, "avatars")

# GitHub Pages is configured to publish from /docs, which keeps generated
# output completely separate from authored source. Nothing in docs/ is
# hand-edited; the whole tree is reproducible from src/ plus build/.
DOCS = os.path.join(ROOT, "docs")
ASSETS = os.path.join(DOCS, "assets")
SHARED_ASSETS = os.path.join(ASSETS, "shared")
PEOPLE_ASSETS = os.path.join(ASSETS, "people")
DOCS_PEOPLE = os.path.join(DOCS, "people")

# --------------------------------------------------------------------------
# Design tokens - see README "The colour architecture"
# --------------------------------------------------------------------------
OCHRE = "#F4BA17"    # rule only, never text
UMBER = "#45210E"    # logo plate, baked into the PNG
ACCENT = "#9E5E3E"   # icon glyphs only, baked into the icon PNGs

SANS = "Arial, 'Helvetica Neue', Helvetica, 'Segoe UI', Roboto, sans-serif"
MSO = "mso-line-height-rule:exactly;"
ZWSP = "&#8203;"

TABLE_W = 520
AVATAR = 80
GUTTER = 16
RULE_W = 3
ICON = 18
ICON_GAP = 10
LOGO = 36

ICON_NAMES = ("mail", "phone", "globe", "users")

REQUIRED = ("name", "role", "email")
ALLOWED = {
    "name", "name_vi", "role", "email", "phone", "phone_href",
    "website", "website_href", "socials", "avatar", "crop", "order",
}

ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class RecordError(ValueError):
    pass


def load_company():
    with open(os.path.join(SRC, "company.yml"), encoding="utf-8") as fh:
        c = yaml.safe_load(fh)
    base = c.get("base_url", "")
    if not base.startswith("https://") or not base.endswith("/"):
        raise RecordError(
            "company.yml: base_url must be https:// and end with a slash")
    domain = c.get("custom_domain")
    if domain and domain not in base:
        raise RecordError(
            f"company.yml: custom_domain '{domain}' does not appear in "
            f"base_url '{base}' - one of them is stale")
    return c


def load_people(company):
    """Load, validate and normalise every employee record.

    Company defaults are merged in here so downstream code never has to ask
    whether a value came from the person or the company.
    """
    if not os.path.isdir(PEOPLE_SRC):
        return []
    people = []
    for fn in sorted(os.listdir(PEOPLE_SRC)):
        if not fn.endswith((".yml", ".yaml")):
            continue
        # _template.yml and anything else underscore-prefixed is scaffolding
        # for contributors, not a person. Skipping it here means the template
        # can carry placeholder values without failing every build.
        if fn.startswith("_"):
            continue
        pid = os.path.splitext(fn)[0]
        if not ID_RE.match(pid):
            raise RecordError(
                f"{fn}: filename must be lowercase kebab-case - it becomes "
                f"the person's URL")
        with open(os.path.join(PEOPLE_SRC, fn), encoding="utf-8") as fh:
            rec = yaml.safe_load(fh) or {}

        unknown = set(rec) - ALLOWED
        if unknown:
            raise RecordError(f"{fn}: unknown field(s) {sorted(unknown)}")
        missing = [k for k in REQUIRED if not rec.get(k)]
        if missing:
            raise RecordError(f"{fn}: missing required field(s) {missing}")
        if "@" not in rec["email"]:
            raise RecordError(f"{fn}: email does not look like an address")
        if rec.get("phone") and not rec.get("phone_href"):
            raise RecordError(
                f"{fn}: phone is set but phone_href is missing - the tel: "
                f"link needs digits only")

        rec["id"] = pid
        rec["company"] = company["name"]
        rec.setdefault("website", company.get("website"))
        rec.setdefault("website_href", company.get("website_href"))
        rec.setdefault("socials", company.get("socials") or [])
        rec.setdefault("order", 999)
        rec.setdefault("name_vi", None)

        if rec.get("avatar"):
            path = os.path.join(AVATARS_SRC, rec["avatar"])
            if not os.path.isfile(path):
                raise RecordError(
                    f"{fn}: avatar '{rec['avatar']}' not found in src/avatars/")
            rec["avatar_path"] = path
        else:
            rec["avatar_path"] = None

        crop = rec.get("crop")
        if crop is not None:
            if (not isinstance(crop, (list, tuple)) or len(crop) != 3
                    or not all(isinstance(v, int) for v in crop)):
                raise RecordError(f"{fn}: crop must be [x, y, size] integers")

        people.append(rec)

    people.sort(key=lambda r: (r["order"], r["name"]))
    ids = [p["id"] for p in people]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise RecordError(f"duplicate employee ids: {sorted(dupes)}")
    return people


def digest(path, n=8):
    """Short content hash, used as a ?v= cache-buster.

    Gmail proxies images through googleusercontent.com and caches them at
    paste time, so replacing a file at the same URL may never reach mail
    already sent. Hashing the content means any change produces a new URL
    automatically, which is more reliable than remembering to bump a version
    directory by hand.
    """
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:n]


def asset_url(base, rel_path, local_path=None):
    url = base + rel_path
    if local_path and os.path.isfile(local_path):
        return f"{url}?v={digest(local_path)}"
    return url


def shared_asset(name):
    return os.path.join(SHARED_ASSETS, name)


def person_asset(pid, name):
    return os.path.join(PEOPLE_ASSETS, pid, name)
