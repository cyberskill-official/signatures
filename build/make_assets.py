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
from model import (ACCENT, AVATAR, ICON_NAMES, LOGO, PEOPLE_ASSETS, SHARED_ASSETS,
                   SRC, load_company, load_people)

SS = 8  # supersample factor for smooth baked edges
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
    out.resize((out_px, out_px), Image.LANCZOS).save(path, "PNG", optimize=True)


def rounded_bake(src_img, out_px, radius_ratio, path):
    c = src_img.convert("RGB").resize((out_px * 4, out_px * 4), Image.LANCZOS)
    big = out_px * SS
    m = Image.new("L", (big, big), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, big - 1, big - 1),
                                        radius=int(big * radius_ratio), fill=255)
    m = m.resize((out_px * 4, out_px * 4), Image.LANCZOS)
    out = Image.new("RGBA", (out_px * 4, out_px * 4), (0, 0, 0, 0))
    out.paste(c, (0, 0), m)
    out.resize((out_px, out_px), Image.LANCZOS).save(path, "PNG", optimize=True)


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
    rounded_bake(Image.open(os.path.join(SRC, "logo.png")), LOGO * 2, 0.18,
                 os.path.join(SHARED_ASSETS, f"logo-{LOGO}-2x.png"))

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
        circle_bake(im, box, AVATAR * 2, os.path.join(d, f"avatar-{AVATAR}-2x.png"))
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
