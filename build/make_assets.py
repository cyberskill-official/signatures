#!/usr/bin/env python3
"""
Build every image the signatures need.

  shared:      logo + four icons  -> docs/assets/shared/
  per person:  circle avatar      -> docs/assets/people/<id>/

Shapes are baked into the PNGs because Gmail strips border-radius. Alpha is
transparent outside the shape so the images sit correctly on a light or dark
surface - a white matte would show as a white ring in dark mode.

  --sheet   also writes a contact sheet of every avatar crop, so a new hire's
            framing can be checked before it ships.
"""
import argparse
import os
import re
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import (ACCENT, AVATAR, AVATAR_SIZES, ICON_NAMES, LOGO, LOGO_SIZES, OCHRE, PEOPLE_ASSETS,
                   SHARED_ASSETS, SRC, UMBER, load_company, load_people)

SS = 8  # supersample factor for smooth baked edges


def save_stable(img, path):
    """Write only when the pixels actually change.

    PNG byte output varies with the Pillow and zlib versions doing the
    encoding, so re-baking an unchanged photo on a different machine produces
    a different file for identical pixels. Every asset URL carries a
    ?v=<content-hash>, so that churn would rewrite URLs and show up as a diff
    on every unrelated build. Comparing decoded pixels instead makes a rebuild
    idempotent no matter who runs it.
    """
    if os.path.isfile(path):
        try:
            old = Image.open(path).convert("RGBA")
            if old.size == img.size and \
                    old.tobytes() == img.convert("RGBA").tobytes():
                return False
        except Exception:
            pass          # unreadable or truncated - just overwrite it
    img.save(path, "PNG", optimize=True)
    return True
LUCIDE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "vendor", "node_modules", "lucide-static", "icons")

ICON_PAGE = """<!doctype html><html><head><meta charset="utf-8"/>
<style>html,body{{margin:0;padding:0;background:transparent;}}
#w{{width:{px}px;height:{px}px;line-height:0;}}
svg{{width:{px}px;height:{px}px;display:block;color:{colour};}}</style>
</head><body><div id="w">{svg}</div></body></html>"""


def circle_bake(src_img, box, out_px, path):
    c = src_img.crop(box).convert("RGB").resize((out_px * 4, out_px * 4), Image.LANCZOS)
    big = out_px * SS
    m = Image.new("L", (big, big), 0)
    ImageDraw.Draw(m).ellipse((0, 0, big - 1, big - 1), fill=255)
    m = m.resize((out_px * 4, out_px * 4), Image.LANCZOS)
    out = Image.new("RGBA", (out_px * 4, out_px * 4), (0, 0, 0, 0))
    out.paste(c, (0, 0), m)
    save_stable(out.resize((out_px, out_px), Image.LANCZOS), path)


def rounded_bake(src_img, out_px, radius_ratio, path):
    c = src_img.convert("RGB").resize((out_px * 4, out_px * 4), Image.LANCZOS)
    big = out_px * SS
    m = Image.new("L", (big, big), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, big - 1, big - 1),
                                        radius=int(big * radius_ratio), fill=255)
    m = m.resize((out_px * 4, out_px * 4), Image.LANCZOS)
    out = Image.new("RGBA", (out_px * 4, out_px * 4), (0, 0, 0, 0))
    out.paste(c, (0, 0), m)
    save_stable(out.resize((out_px, out_px), Image.LANCZOS), path)


BRAND_FONT = os.path.join(SRC, "fonts", "BeVietnamPro-SemiBold.ttf")


def find_font(size):
    """The brand face, from the repo. One path, no fallbacks, fatal if absent.

    This used to scan five system paths and return whatever it found first,
    which made the link-preview card non-reproducible: the same inputs
    produced 31,087 bytes on macOS and 32,241 on Ubuntu, because one machine
    resolved Liberation Sans and the other DejaVu. requirements.txt pins
    Pillow precisely to stop that class of drift, and this reopened it - and
    it matters, because CI fails a pull request whose docs/ does not match a
    clean rebuild. A local commit could fail for a reason unrelated to the
    change.

    Bundling the font also settles a design-system point. CDS requires the
    wordmark in Be Vietnam Pro SemiBold and the signature markup cannot honour
    that - a webfont needs a <style> block and Gmail strips those. The card is
    an image, so here it can, and does.

    Failing rather than degrading is deliberate. The old version returned None
    and silently shipped a card with no text on it.
    """
    from PIL import ImageFont
    if not os.path.isfile(BRAND_FONT):
        raise SystemExit(
            f"{BRAND_FONT} is missing.\n"
            f"It is committed to the repo so every machine renders the "
            f"link-preview card identically. Restore it from git rather than "
            f"substituting a system font - a different face means different "
            f"bytes, and CI compares docs/ against a clean build.")
    return ImageFont.truetype(BRAND_FONT, size)


def build_site_images(logo_src, company):
    """Favicon, touch icon and the Open Graph card.

    This URL gets pasted into Slack, Zalo and email when staff are told about
    it. Without these it renders as a bare link with no title card, on a page
    whose whole job is to look trustworthy enough that people hand over a
    photograph.
    """
    os.makedirs(SHARED_ASSETS, exist_ok=True)
    logo = Image.open(logo_src).convert("RGBA")

    for px, name in ((32, "favicon-32.png"), (180, "apple-touch-icon.png")):
        rounded_bake(logo, px, 0.18, os.path.join(SHARED_ASSETS, name))

    # 1200x630 is the size every major platform crops toward.
    W, HT = 1200, 630
    card = Image.new("RGB", (W, HT), UMBER)
    d = ImageDraw.Draw(card)
    d.rectangle((0, HT - 10, W, HT), fill=OCHRE)

    mark = logo.resize((150, 150), Image.LANCZOS)
    card.paste(mark, (90, 150), mark)

    font_lg, font_sm = find_font(70), find_font(32)
    d.text((90, 340), company["name"], font=font_lg, fill="#FFFFFF")
    d.text((90, 430), "Email signatures", font=font_lg, fill=OCHRE)
    d.text((90, 520), company.get("tagline", ""), font=font_sm, fill="#E8D9CD")
    save_stable(card, os.path.join(SHARED_ASSETS, "og-card.png"))
    print("  site images: favicon-32, apple-touch-icon, og-card")


def default_crop(im):
    """Centre a square on the upper third - a sane default for a portrait.

    Explicit `crop` in the person's record always wins. This exists so a new
    hire is never blocked on someone hand-tuning coordinates; check the
    contact sheet and add a crop if the framing is off.
    """
    w, h = im.size
    size = int(min(w, h) * 0.62)
    return [max(0, (w - size) // 2), max(0, int(h * 0.10)), size]


def icons_present():
    return all(os.path.isfile(os.path.join(SHARED_ASSETS, f"icon-{n}-2x.png"))
               for n in ICON_NAMES)


def build_icons():
    """Rasterise the shared icons. Needs Playwright and the vendored Lucide.

    Both are only required to CHANGE the icon set. They are build-time tools,
    not runtime dependencies, so if the icons are already committed we skip
    rather than fail - otherwise a routine rebuild or a --verify-remote run
    breaks on any machine that has not installed Playwright.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        if icons_present():
            print("  icons: Playwright not installed - reusing committed PNGs")
            return
        raise SystemExit(
            "Icons are missing and Playwright is not installed.\n"
            "  pip install playwright --break-system-packages\n"
            "  python3 -m playwright install chromium")
    if not os.path.isdir(LUCIDE):
        if icons_present():
            print("  icons: Lucide not vendored - reusing committed PNGs")
            return
        raise SystemExit("Lucide not vendored: cd build/vendor && npm install lucide-static")
    os.makedirs(SHARED_ASSETS, exist_ok=True)
    px = 36
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
        page = b.new_page(viewport={"width": px, "height": px})
        for name in ICON_NAMES:
            with open(os.path.join(LUCIDE, f"{name}.svg"), encoding="utf-8") as fh:
                svg = fh.read()
            svg = re.sub(r"<!--.*?-->", "", svg, flags=re.DOTALL)
            svg = re.sub(r'\swidth="\d+"', "", svg, count=1)
            svg = re.sub(r'\sheight="\d+"', "", svg, count=1)
            page.set_content(ICON_PAGE.format(px=px, colour=ACCENT, svg=svg.strip()))
            page.wait_for_timeout(60)
            page.locator("#w").screenshot(
                path=os.path.join(SHARED_ASSETS, f"icon-{name}-2x.png"),
                omit_background=True)
        b.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", action="store_true",
                    help="also write docs/assets/_avatar-sheet.png")
    ap.add_argument("--skip-icons", action="store_true")
    args = ap.parse_args()

    company = load_company()
    people = load_people(company)

    if not args.skip_icons:
        build_icons()
    os.makedirs(SHARED_ASSETS, exist_ok=True)
    logo_src = os.path.join(SRC, "logo.png")
    for px in LOGO_SIZES:
        rounded_bake(Image.open(logo_src), px * 2, 0.18,
                     os.path.join(SHARED_ASSETS, f"logo-{px}-2x.png"))
    build_site_images(logo_src, company)

    crops = []
    for rec in people:
        if not rec["avatar_path"]:
            print(f"  {rec['id']:22} no avatar - signature will render without one")
            continue
        im = Image.open(rec["avatar_path"])
        crop = rec.get("crop") or default_crop(im)
        x, y, s = crop
        box = (x, y, x + s, y + s)
        d = os.path.join(PEOPLE_ASSETS, rec["id"])
        os.makedirs(d, exist_ok=True)
        for px in AVATAR_SIZES:
            circle_bake(im, box, px * 2, os.path.join(d, f"avatar-{px}-2x.png"))
        crops.append((rec, im, box))
        tag = "explicit" if rec.get("crop") else "DEFAULT - check the sheet"
        print(f"  {rec['id']:22} avatar {s}px crop at ({x},{y})  [{tag}]")

    if args.sheet and crops:
        cell = 160
        sheet = Image.new("RGB", (cell * len(crops), cell + 22), "#FFFFFF")
        d = ImageDraw.Draw(sheet)
        for i, (rec, im, box) in enumerate(crops):
            c = im.crop(box).convert("RGB").resize((cell, cell), Image.LANCZOS)
            m = Image.new("L", (cell, cell), 0)
            ImageDraw.Draw(m).ellipse((0, 0, cell - 1, cell - 1), fill=255)
            o = Image.new("RGB", (cell, cell), "#FFFFFF"); o.paste(c, (0, 0), m)
            sheet.paste(o, (i * cell, 22))
            d.text((i * cell + 4, 6), rec["id"][:24], fill="black")
        sheet.save(os.path.join(os.path.dirname(SHARED_ASSETS), "_avatar-sheet.png"))
        print("  contact sheet -> docs/assets/_avatar-sheet.png")

    n = len([f for f in os.listdir(SHARED_ASSETS)])
    print(f"shared assets: {n}   people with avatars: {len(crops)}")


if __name__ == "__main__":
    main()
