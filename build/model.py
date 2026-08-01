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
# Baked at these display sizes, each at 2x. Styles must display an avatar at
# one of them: a 160px source shown at 48px is 3.3x, which downloads four
# times the pixels it draws for every recipient of every mail.
AVATAR_SIZES = (80, 56)
GUTTER = 16
RULE_W = 3
ICON = 18
ICON_GAP = 10
LOGO = 36
# Same rule as AVATAR_SIZES. Every displayed size must be baked, or the
# source is not exactly 2x and V7 says so - which is how ten styles asking
# for logos at 26, 28, 32, 34 and 40 against one 72px file were found.
LOGO_SIZES = (36, 28)
ICON_SIZES = (18,)

ICON_NAMES = ("mail", "phone", "globe", "users")

REQUIRED = ("name", "role", "email")
ALLOWED = {
    "name", "name_vi", "role", "email", "phone", "phone_href",
    "website", "website_href", "socials", "avatar", "crop", "order",
    "active", "style",
}

ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# --------------------------------------------------------------------------
# Input safety
#
# Records arrive by pull request from people who are not reviewing their own
# HTML. Every value here is interpolated into markup that is both published on
# the site and pasted into mail clients, so a record is untrusted input.
#
# Three layers, because each catches what the others cannot:
#   1. escaping at render time  - handles quotes and angle brackets
#   2. scheme allowlisting here - escaping does NOT stop javascript: URLs
#   3. shape limits here        - a job title has no business containing markup
# --------------------------------------------------------------------------
SAFE_SCHEMES = ("https://", "mailto:", "tel:")
PHONE_HREF_RE = re.compile(r"^\+?[0-9]{4,20}$")
CTRL_RE = re.compile("[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\\x7f"         "\\u200b-\\u200f\\u2028\\u2029\\u202a-\\u202e\\ufeff]")
ANGLE_RE = re.compile(r"[<>]")
TEXT_LIMITS = {"name": 60, "name_vi": 60, "role": 80, "email": 120,
               "phone": 40, "website": 80, "label": 40}


class RecordError(ValueError):
    pass


def check_text(where, field, value, limit=None):
    """Reject anything a name or job title has no reason to contain."""
    if not isinstance(value, str):
        raise RecordError(f"{where}: {field} must be text, got {type(value).__name__}")
    if ANGLE_RE.search(value):
        raise RecordError(f"{where}: {field} contains < or >, which is markup, "
                          f"not a name")
    if CTRL_RE.search(value):
        raise RecordError(f"{where}: {field} contains control or zero-width "
                          f"characters")
    limit = limit or TEXT_LIMITS.get(field, 200)
    if len(value) > limit:
        raise RecordError(f"{where}: {field} is {len(value)} characters, "
                          f"over the {limit} limit")
    return value


def check_url(where, field, value):
    """Allowlist schemes. This is the layer escaping cannot provide.

    Escaping a javascript: URL produces a working javascript: URL - the
    dangerous part is the scheme, not the punctuation.
    """
    if not isinstance(value, str):
        raise RecordError(f"{where}: {field} must be text")
    if not value.startswith(SAFE_SCHEMES):
        raise RecordError(
            f"{where}: {field} is {value[:40]!r} - only "
            f"{', '.join(SAFE_SCHEMES)} are allowed")
    if CTRL_RE.search(value) or ANGLE_RE.search(value) or '"' in value:
        raise RecordError(f"{where}: {field} contains characters that cannot "
                          f"appear in a URL here")
    return value


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

    # company.yml is edited less often than a person record, but it reaches
    # every signature, so it gets the same checks rather than being trusted
    # because a maintainer wrote it.
    for field in ("name", "tagline", "website"):
        if c.get(field):
            check_text("company.yml", field, c[field], limit=120)
    for field in ("website_href", "repo"):
        if c.get(field):
            check_url("company.yml", field, c[field])
    for i, s in enumerate(c.get("socials") or []):
        if not isinstance(s, dict) or "label" not in s or "href" not in s:
            raise RecordError(
                f"company.yml: socials[{i}] needs both a label and an href")
        check_text("company.yml", "label", s["label"])
        check_url("company.yml", f"socials[{i}].href", s["href"])
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
        if rec.get("phone_href") and not PHONE_HREF_RE.match(str(rec["phone_href"])):
            raise RecordError(
                f"{fn}: phone_href must be digits with an optional leading + "
                f"- it goes straight into a tel: link")

        rec["id"] = pid
        rec["company"] = company["name"]
        rec.setdefault("website", company.get("website"))
        rec.setdefault("website_href", company.get("website_href"))
        rec.setdefault("socials", company.get("socials") or [])
        rec.setdefault("order", 999)
        rec.setdefault("name_vi", None)
        rec.setdefault("active", True)

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

        # ---- input safety, after defaults are merged so company-wide values
        # are checked too. A bad social link in company.yml would otherwise
        # reach every signature unvalidated.
        for field in ("name", "name_vi", "role", "email", "phone", "website"):
            if rec.get(field):
                check_text(fn, field, rec[field])
        if rec.get("website_href"):
            check_url(fn, "website_href", rec["website_href"])
        if not isinstance(rec["socials"], list):
            raise RecordError(f"{fn}: socials must be a list")
        for i, s in enumerate(rec["socials"]):
            if not isinstance(s, dict) or "label" not in s or "href" not in s:
                raise RecordError(
                    f"{fn}: socials[{i}] needs both a label and an href")
            if set(s) - {"label", "href"}:
                raise RecordError(
                    f"{fn}: socials[{i}] has unknown key(s) "
                    f"{sorted(set(s) - {'label', 'href'})}")
            check_text(fn, "label", s["label"])
            check_url(fn, f"socials[{i}].href", s["href"])

        # Checked against the registry rather than just being a string, so a
        # typo fails here instead of silently publishing the default and
        # leaving someone wondering why their choice did not stick.
        if rec.get("style"):
            from styles import BY_ID
            if rec["style"] not in BY_ID:
                raise RecordError(
                    f"{fn}: style '{rec['style']}' is not one of "
                    f"{', '.join(sorted(BY_ID))}")

        if not isinstance(rec["active"], bool):
            raise RecordError(f"{fn}: active must be true or false")
        if not rec["active"]:
            # Kept in the repo so the record and its history survive, but not
            # built and not published. See README, "When someone leaves".
            print(f"  {pid:22} active: false - skipped")
            continue

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
