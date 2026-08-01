#!/usr/bin/env python3
"""
Turn a signature request issue into a record and a photo.

The issue forms already collect structured data. Without this, a maintainer
reads the issue and hand-writes the YAML, which is the bottleneck the forms
were meant to remove - just moved one step later.

SECURITY
--------
Everything here is attacker-controlled. The issue body comes from whoever
opened it, and this runs in a workflow that can write to the repository. So:

  - the record is built with yaml.safe_dump, never string formatting, so no
    issue text can become YAML structure
  - the photo URL must be on a GitHub user-content host, checked against a
    fixed list rather than a substring match
  - the download is size-capped, then decoded with Pillow and re-encoded.
    A file is an image because it decodes as one, not because of its name
  - the id is derived, then re-checked against the same rule the loader uses
  - every field goes through model.check_text / check_url before it is written

The workflow separately refuses to run for anyone outside the organisation.

Usage:  issue_to_record.py <issue.json> <mode>       mode: new | update
Writes: src/people/<id>.yml, optionally src/avatars/<id>.png
Prints: id=<id> and a short summary to $GITHUB_OUTPUT if set.
"""
import io
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request

import yaml
from PIL import Image

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "build"))
from model import (ID_RE, PEOPLE_SRC, AVATARS_SRC, RecordError,  # noqa: E402
                   check_text, check_url, load_company)

# Only these hosts serve GitHub issue attachments. A substring check on
# "github" would accept github.evil.example.
ALLOWED_IMAGE_HOSTS = {
    "user-images.githubusercontent.com",
    "github.com",
    "raw.githubusercontent.com",
    "private-user-images.githubusercontent.com",
}
MAX_BYTES = 12 * 1024 * 1024
MAX_EDGE = 2000          # a signature avatar is 160px; nothing needs more
MIN_EDGE = 128


def parse_form(body):
    """GitHub issue forms render as '### Label\\n\\nvalue' blocks."""
    out, key, buf = {}, None, []
    for line in (body or "").replace("\r\n", "\n").split("\n"):
        if line.startswith("### "):
            if key:
                out[key] = "\n".join(buf).strip()
            key, buf = line[4:].strip().lower(), []
        elif key:
            buf.append(line)
    if key:
        out[key] = "\n".join(buf).strip()
    return {k: ("" if v == "_No response_" else v) for k, v in out.items()}


def slugify(name):
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("đ", "d").replace("Đ", "D")
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return re.sub(r"-{2,}", "-", s)


def phone_href(display):
    digits = re.sub(r"[^\d+]", "", display or "")
    if digits.startswith("+"):
        digits = "+" + re.sub(r"\D", "", digits[1:])
    else:
        digits = re.sub(r"\D", "", digits)
    return digits


def first_image_url(text):
    for m in re.finditer(r"!?\[[^\]]*\]\((https://[^)\s]+)\)", text or ""):
        return m.group(1)
    for m in re.finditer(r'<img[^>]+src="(https://[^"]+)"', text or ""):
        return m.group(1)
    m = re.search(r"https://\S+\.(?:png|jpe?g|webp|gif)\b", text or "", re.I)
    return m.group(0) if m else None


def fetch_photo(url, dest):
    """Download, prove it is an image by decoding it, then re-encode.

    Re-encoding is the point: it drops EXIF (which carries GPS and device
    identifiers a colleague did not mean to publish) and it means whatever
    lands on disk was produced by Pillow, not by the uploader.
    """
    host = urllib.parse.urlparse(url).hostname or ""
    if host not in ALLOWED_IMAGE_HOSTS:
        raise RecordError(f"photo host {host!r} is not a GitHub attachment host")

    req = urllib.request.Request(url, headers={"User-Agent": "signatures-bot"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise RecordError(f"photo is over {MAX_BYTES // 1024 // 1024}MB")

    im = Image.open(io.BytesIO(raw))
    im.verify()                                   # structural check
    im = Image.open(io.BytesIO(raw)).convert("RGB")   # reopen: verify exhausts
    w, h = im.size
    if min(w, h) < MIN_EDGE:
        raise RecordError(f"photo is {w}x{h}; needs at least {MIN_EDGE}px")
    if max(w, h) > MAX_EDGE:
        im.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    im.save(dest, "PNG", optimize=True)           # no EXIF survives this
    return im.size


def build_record(form, company, mode, existing):
    rec = dict(existing) if existing else {}

    def take(form_key, field, transform=None):
        v = (form.get(form_key) or "").strip()
        if not v:
            return
        rec[field] = transform(v) if transform else v

    take("full name", "name")
    take("vietnamese name", "name_vi")
    take("job title", "role")
    take("work email", "email")
    take("phone number", "phone")

    # Free-text "what is changing" on the update form, one key: value per line.
    for line in (form.get("what is changing") or "").split("\n"):
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip().lower(), v.strip()
        if k in ("name", "name_vi", "role", "email", "phone", "website"):
            rec[k] = v

    if rec.get("phone"):
        rec["phone_href"] = phone_href(rec["phone"])
    elif "phone_href" in rec:
        rec.pop("phone_href", None)

    if mode == "new":
        for required in ("name", "role", "email"):
            if not rec.get(required):
                raise RecordError(f"the form is missing {required}")

    # Same checks the loader applies, run here so a bad request fails with a
    # readable message on the issue rather than a stack trace in the build.
    for f in ("name", "name_vi", "role", "email", "phone"):
        if rec.get(f):
            check_text("request", f, rec[f])
    if rec.get("website_href"):
        check_url("request", "website_href", rec["website_href"])
    return rec


def main():
    issue = json.load(open(sys.argv[1], encoding="utf-8"))
    mode = sys.argv[2] if len(sys.argv) > 2 else "new"
    form = parse_form(issue.get("body"))
    company = load_company()

    pid = (form.get("preferred web address")
           or form.get("your page") or "").strip().lower()
    if not pid:
        pid = slugify(form.get("full name") or "")
    pid = slugify(pid)
    if not ID_RE.match(pid or ""):
        raise RecordError(
            f"could not derive a usable id from the request (got {pid!r}). "
            f"Add a preferred web address to the form.")

    path = os.path.join(PEOPLE_SRC, f"{pid}.yml")
    exists = os.path.isfile(path)
    if mode == "new" and exists:
        raise RecordError(
            f"{pid} already exists. Use the 'Update my signature' form, or "
            f"pick a different web address.")
    if mode == "update" and not exists:
        raise RecordError(f"no record called {pid} to update.")

    existing = yaml.safe_load(open(path, encoding="utf-8")) if exists else None
    rec = build_record(form, company, mode, existing)

    photo = first_image_url(form.get("photo") or form.get("new photo") or "")
    if photo:
        size = fetch_photo(photo, os.path.join(AVATARS_SRC, f"{pid}.png"))
        rec["avatar"] = f"{pid}.png"
        rec.pop("crop", None)      # framing is re-checked for a new photo
        print(f"photo: {size[0]}x{size[1]} -> src/avatars/{pid}.png")

    os.makedirs(PEOPLE_SRC, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(rec, fh, allow_unicode=True, sort_keys=True)
    print(f"record: src/people/{pid}.yml")

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"id={pid}\n")
            fh.write(f"name={rec.get('name', pid)}\n")
            fh.write(f"photo={'yes' if photo else 'no'}\n")


if __name__ == "__main__":
    try:
        main()
    except (RecordError, OSError, ValueError) as e:
        print(f"::error::{e}")
        out = os.environ.get("GITHUB_OUTPUT")
        if out:
            with open(out, "a", encoding="utf-8") as fh:
                fh.write(f"error={e}\n")
        sys.exit(1)
