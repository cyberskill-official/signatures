#!/usr/bin/env python3
"""
Cross-client and cross-browser audit.

Rendering the raw signature in one browser proves almost nothing about email.
Every client rewrites the markup before it draws it, and they do not all use
the same engine. So each run here does two things a plain render does not:

  1. Applies that client's sanitiser or layout engine as a TRANSFORM, so what
     gets rendered is what the client would actually be handed - including
     uncommenting the <!--[if mso]--> branch for Outlook and deleting every
     CSS property the Word engine does not implement.

  2. Renders the result in the engine that client really uses. WebKit is the
     engine behind Apple Mail on macOS and iOS and every iOS mail app; Gecko
     is Thunderbird; Blink is Chrome, Edge, Android WebViews and the web
     clients. Those are real engines, not approximations.

What that does NOT give you is Word. Outlook for Windows renders through
Microsoft Word's HTML engine, which cannot be installed here. The Outlook rows
model it by removing what Word drops and rendering the remainder - that
reliably catches layout that DEPENDS on a dropped property, which is the
failure that matters, but it is a model and is labelled as one.

  python3 validation/crossclient.py                  # every engine available
  python3 validation/crossclient.py --engines chromium
  python3 validation/crossclient.py --skip-site      # signature only
"""
import argparse
import http.server
import json
import math
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "build"))
from styles import STYLES
from model import DOCS, load_company, load_people          # noqa: E402

OUT = os.path.join(HERE, "crossclient")
os.makedirs(OUT, exist_ok=True)

# --------------------------------------------------------------------------
# Client transforms
# --------------------------------------------------------------------------
MSO_OPEN = re.compile(r"<!--\[if\s+[^\]]*mso[^\]]*\]>", re.I)
MSO_CLOSE = re.compile(r"<!\[endif\]-->", re.I)
STYLE_ATTR = re.compile(r'(<\s*([a-zA-Z][\w-]*)\b[^>]*?\sstyle=")([^"]*)(")')


def map_styles(html, fn):
    """Rewrite every inline style attribute through fn(declarations, tagname)."""
    return STYLE_ATTR.sub(
        lambda m: m.group(1) + fn(m.group(3), m.group(2).lower()) + m.group(4),
        html)


def strip_head_css(html):
    """Every webmail client strips <style>, class and id from message bodies.

    This markup carries none of them, so these substitutions are no-ops - which
    is the point. The report records whether a transform changed anything, so a
    no-op is evidence rather than an untested assumption.
    """
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.S | re.I)
    html = re.sub(r"<(script|link)\b[^>]*>.*?</\1>", "", html, flags=re.S | re.I)
    html = re.sub(r'\s(class|id)="[^"]*"', "", html, flags=re.I)
    return html


# Properties Microsoft Word's HTML engine does not implement. Anything here is
# silently discarded by Outlook for Windows, so the layout has to survive
# without it.
WORD_DROPS = {
    "max-width", "min-width", "max-height", "min-height",
    "border-radius", "box-shadow", "text-shadow",
    "float", "position", "z-index", "opacity",
    "background-image", "background-size", "background-position",
    "outline", "white-space", "letter-spacing", "text-overflow",
}
OUTLOOK_LINK_BLUE = "#0563C1"


def _word_decls(decls, tag):
    out = []
    for d in decls.split(";"):
        d = d.strip()
        if not d or ":" not in d:
            continue
        prop, val = (x.strip() for x in d.split(":", 1))
        prop = prop.lower()
        if prop in WORD_DROPS:
            continue
        # Word honours padding on table cells and nowhere else. Padding on a
        # div, a paragraph or an anchor is discarded.
        if prop.startswith("padding") and tag not in ("td", "th", "table"):
            continue
        # color:inherit is not implemented. Outlook paints hyperlinks in its
        # own blue no matter what the markup asks for.
        if prop == "color" and val.lower() == "inherit":
            out.append(f"color:{OUTLOOK_LINK_BLUE}" if tag == "a" else "color:#000000")
            continue
        out.append(f"{prop}:{val}")
    return ";".join(out) + (";" if out else "")


def t_word(html):
    """Outlook for Windows: the mso branch becomes real, the rest degrades."""
    html = MSO_OPEN.sub("", html)
    html = MSO_CLOSE.sub("", html)
    return map_styles(html, _word_decls)


TRANSFORMS = {
    "none": lambda h: h,
    "webmail": strip_head_css,
    "word": t_word,
}

# --------------------------------------------------------------------------
# The matrix
#
# engine  - the rendering engine that client genuinely uses
# xform   - which sanitiser/layout model to apply first
# widths  - realistic viewport widths for that client
# schemes - which appearance modes that client actually offers
# --------------------------------------------------------------------------
CLIENTS = [
    ("gmail-web-chrome",   "Gmail web (Chrome/Edge)",   "chromium", "webmail",
     [1024, 700], ["light", "dark"]),
    ("gmail-web-safari",   "Gmail web (Safari)",        "webkit",   "webmail",
     [1024], ["light", "dark"]),
    ("gmail-android",      "Gmail app (Android)",       "chromium", "webmail",
     [412], ["light", "dark-invert"]),
    ("gmail-ios",          "Gmail app (iOS)",           "webkit",   "webmail",
     [390], ["light", "dark"]),
    ("apple-mail-macos",   "Apple Mail (macOS)",        "webkit",   "none",
     [900], ["light", "dark"]),
    ("apple-mail-ios",     "Apple Mail (iOS)",          "webkit",   "none",
     [390, 320], ["light", "dark"]),
    # 400 and 500 model a three-pane Outlook window on a laptop, where the
    # reading pane is narrower than the signature used to assume.
    ("outlook-win",        "Outlook Windows (Word)",    "chromium", "word",
     [1100, 900, 500, 400], ["light"]),
    ("outlook-web",        "Outlook.com / OWA",         "chromium", "webmail",
     [1024], ["light", "dark"]),
    ("outlook-mobile",     "Outlook mobile",            "chromium", "webmail",
     [390], ["light", "dark-invert"]),
    ("outlook-mac-new",    "Outlook for Mac (new)",     "webkit",   "webmail",
     [900], ["light", "dark"]),
    ("thunderbird",        "Thunderbird",               "firefox",  "none",
     [900], ["light", "dark"]),
    ("yahoo-web",          "Yahoo / AOL Mail",          "chromium", "webmail",
     [1024], ["light"]),
    ("proton-web",         "Proton Mail",               "chromium", "webmail",
     [1024], ["light", "dark"]),
    ("samsung-mail",       "Samsung Mail (Android)",    "chromium", "none",
     [412], ["dark-invert"]),
]

# fg=None models a client that darkens the surface without setting a text
# colour. No client we know of does this, but the signature deliberately lets
# text inherit, so the consequence is worth measuring rather than assuming.
SCHEMES = {
    "light":       dict(bg="#FFFFFF", fg="#000000", invert=False),
    "dark":        dict(bg="#1B1B1B", fg="#E6E6E6", invert=False),
    "dark-invert": dict(bg="#FFFFFF", fg="#000000", invert=True),
    "dark-bgonly": dict(bg="#1B1B1B", fg=None,      invert=False),
}

# Hostile host styles. A signature sits inside the client's own compose or
# read container and must not inherit anything from it.
HOSTILE = (
    "font-size:20px;line-height:3;font-family:'Comic Sans MS',cursive;"
    "letter-spacing:2px;text-align:center;font-weight:900;color:#CC0000;"
)

PAGE = """<!doctype html><html><head><meta charset="utf-8"/><style>
 html,body{{margin:0;padding:0;background:{bg};{fg}}}
 #host{{padding:16px;box-sizing:border-box;width:{w}px;background:{bg};{host}}}
 #host img{{{img}}}
</style></head><body><div id="host">{sig}</div></body></html>"""


# --------------------------------------------------------------------------
# Colour maths, including the CSS filter a force-inverting client applies
# --------------------------------------------------------------------------
def _lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb):
    r, g, b = (_lin(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg, bg):
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return round((hi + 0.05) / (lo + 0.05), 2)


def parse_rgb(s):
    m = re.findall(r"[\d.]+", s or "")
    return tuple(int(float(x)) for x in m[:3]) if len(m) >= 3 else None


# invert(1) hue-rotate(180deg), per the Filter Effects spec. getComputedStyle
# reports colours BEFORE the filter, so contrast under a force-inverting client
# has to be computed rather than read.
_A = math.radians(180)
_C, _S = math.cos(_A), math.sin(_A)
_HUE = (
    (0.213 + 0.787 * _C - 0.213 * _S, 0.715 - 0.715 * _C - 0.715 * _S,
     0.072 - 0.072 * _C + 0.928 * _S),
    (0.213 - 0.213 * _C + 0.143 * _S, 0.715 + 0.285 * _C + 0.140 * _S,
     0.072 - 0.072 * _C - 0.283 * _S),
    (0.213 - 0.213 * _C - 0.787 * _S, 0.715 - 0.715 * _C + 0.715 * _S,
     0.072 + 0.928 * _C + 0.072 * _S),
)


def apply_invert(rgb):
    r, g, b = (255 - v for v in rgb)
    out = []
    for row in _HUE:
        v = row[0] * r + row[1] * g + row[2] * b
        out.append(max(0, min(255, int(round(v)))))
    return tuple(out)


# --------------------------------------------------------------------------
PROBE = r"""
() => {
  const host = document.getElementById('host'), cs = getComputedStyle;
  const table = host.querySelector('table');
  const r = table ? table.getBoundingClientRect() : null;

  function effBg(el) {
    let n = el;
    while (n && n !== document.documentElement) {
      const b = cs(n).backgroundColor;
      if (b && b !== 'rgba(0, 0, 0, 0)' && b !== 'transparent') return b;
      n = n.parentElement;
    }
    return cs(document.body).backgroundColor;
  }

  const texts = [];
  host.querySelectorAll('div,span,a,td,p').forEach(el => {
    const own = Array.from(el.childNodes)
      .filter(n => n.nodeType === 3 && n.textContent.trim().length > 1)
      .map(n => n.textContent.trim()).join(' ');
    if (!own) return;
    const st = cs(el);
    if (parseFloat(st.fontSize) < 2) return;
    texts.push({ text: own.slice(0, 60), color: st.color, bg: effBg(el),
                 fontSize: parseFloat(st.fontSize),
                 fontWeight: parseInt(st.fontWeight, 10) || 400,
                 fontFamily: st.fontFamily });
  });

  const links = Array.from(host.querySelectorAll('a')).map(a => ({
    href: a.getAttribute('href'), text: (a.textContent || '').trim(),
    decoration: cs(a).textDecorationLine, color: cs(a).color,
    box: (b => [Math.round(b.width), Math.round(b.height)])(a.getBoundingClientRect()),
  }));

  const imgs = Array.from(host.querySelectorAll('img')).map(im => ({
    src: (im.getAttribute('src') || '').split('/').pop(),
    wAttr: im.getAttribute('width'), hAttr: im.getAttribute('height'),
    box: (b => [Math.round(b.width), Math.round(b.height)])(im.getBoundingClientRect()),
    natural: [im.naturalWidth, im.naturalHeight],
    loaded: im.complete && im.naturalWidth > 0,
  }));

  // Glyph coverage. A character with no glyph in any available font is drawn
  // as the font's .notdef box, which measures the same as a deliberately
  // unassigned codepoint. Comparing widths finds tofu that a screenshot only
  // reveals to a human eye.
  const cv = document.createElement('canvas').getContext('2d');
  const missing = [];
  host.querySelectorAll('[lang]').forEach(el => {
    cv.font = cs(el).fontSize + ' ' + cs(el).fontFamily;
    const notdef = cv.measureText('￿').width;
    for (const ch of (el.textContent || '')) {
      if (ch.trim() && cv.measureText(ch).width === notdef) missing.push(ch);
    }
  });

  return {
    tableW: r ? Math.round(r.width) : 0,
    tableH: r ? Math.round(r.height) : 0,
    scrollW: document.documentElement.scrollWidth,
    hostScrollW: host.scrollWidth, hostClientW: host.clientWidth,
    texts, links, imgs, missingGlyphs: [...new Set(missing)],
    textContent: host.innerText.replace(/\s+/g, ' ').trim(),
  };
}
"""


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve(root, port):
    h = lambda *a, **k: Quiet(*a, directory=root, **k)   # noqa: E731
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


# --------------------------------------------------------------------------
def audit_signature(engines, sig_by_id, people, findings, runs):
    def add(sev, scope, check, msg):
        findings.append({"severity": sev, "scope": scope, "check": check,
                         "message": msg})

    with sync_playwright() as p:
        launched = {}
        for name in engines:
            launched[name] = getattr(p, name).launch(
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
                if name == "chromium" else [])

        for rec in people:
            pid = rec["id"]
            raw = sig_by_id[pid]
            baseline = None

            jobs = [(cid, label, eng, xf, w, sc)
                    for cid, label, eng, xf, widths, schemes in CLIENTS
                    for w in widths for sc in schemes]
            # Robustness probes, run on the plain markup in every engine.
            for eng in engines:
                jobs.append((f"probe-bgonly-{eng}",
                             f"Probe: dark surface, no text colour ({eng})",
                             eng, "none", 900, "dark-bgonly"))
                jobs.append((f"probe-hostile-{eng}",
                             f"Probe: hostile host styles ({eng})",
                             eng, "none", 900, "light"))

            for cid, label, eng, xf, width, scheme in jobs:
                if eng not in launched:
                    # Do NOT skip silently. A client whose engine is missing is
                    # untested, not passing, and the report has to say so.
                    findings.append({
                        "severity": "UNCOVERED", "scope": f"{pid}--{cid}",
                        "check": "X0",
                        "message": f"{label} not tested - {eng} unavailable"})
                    continue
                sig = TRANSFORMS[xf](raw)
                s = SCHEMES[scheme]
                hostile = cid.startswith("probe-hostile")

                page = launched[eng].new_page(
                    viewport={"width": width, "height": 900},
                    device_scale_factor=2)
                page.set_content(PAGE.format(
                    bg=s["bg"],
                    fg=f"color:{s['fg']};" if s["fg"] else "",
                    w=width,
                    host=("filter:invert(1) hue-rotate(180deg);" if s["invert"] else "")
                         + (HOSTILE if hostile else ""),
                    img="filter:invert(1) hue-rotate(180deg);" if s["invert"] else "",
                    sig=sig))
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                d = page.evaluate(PROBE)

                tag = f"{pid}--{cid}--{width}--{scheme}"
                page.locator("#host").screenshot(
                    path=os.path.join(OUT, f"{tag}.png"))
                page.close()

                d.update(person=pid, client=cid, label=label, engine=eng,
                         transform=xf, transformed=(sig != raw), width=width,
                         scheme=scheme, screenshot=f"{tag}.png")
                runs.append(d)

                # ---- assertions ------------------------------------------
                if d["hostScrollW"] - d["hostClientW"] > 1:
                    add("HIGH", tag, "X1",
                        f"horizontal overflow {d['hostScrollW']-d['hostClientW']}px "
                        f"at {width}px")

                if d["missingGlyphs"]:
                    add("HIGH", tag, "X6",
                        f"no glyph for {d['missingGlyphs']} - renders as tofu")

                if not d["links"]:
                    add("HIGH", tag, "X3", "every link was stripped")
                for a in d["links"]:
                    if "underline" not in a["decoration"]:
                        add("MED", tag, "X3",
                            f"link '{a['text'][:24]}' lost its underline")
                    if a["box"][0] < 8 or a["box"][1] < 8:
                        add("HIGH", tag, "X3",
                            f"link '{a['text'][:24]}' collapsed to {a['box']}")

                for im in d["imgs"]:
                    if not im["wAttr"] or not im["hAttr"]:
                        add("HIGH", tag, "X5",
                            f"{im['src']} has no width/height attribute - "
                            f"Outlook scales it by 1.25 at 120 DPI")

                # Contrast. Under a force-inverting client the computed values
                # are pre-filter, so both sides get the filter applied first.
                if scheme != "dark-bgonly":
                    for t in d["texts"]:
                        fg, bg = parse_rgb(t["color"]), parse_rgb(t["bg"])
                        if not fg or not bg:
                            continue
                        if s["invert"]:
                            fg, bg = apply_invert(fg), apply_invert(bg)
                        ratio = contrast(fg, bg)
                        large = (t["fontSize"] >= 24
                                 or (t["fontSize"] >= 18.66 and t["fontWeight"] >= 700))
                        need = 3.0 if large else 4.5
                        if ratio < need:
                            add("HIGH", tag, "X2",
                                f"{ratio}:1 < {need}:1 for {t['fontSize']:g}px/"
                                f"{t['fontWeight']} '{t['text'][:28]}'")

                # Geometry must not depend on the host's inherited styles.
                if hostile:
                    # Against THIS signature's own plain render. `runs` is
                    # global, so without the person filter this matched the
                    # first apple-mail run ever recorded - classic - and every
                    # other style was measured against a layout it has no
                    # reason to resemble. It reported eight leaks that were
                    # just ten styles being ten different heights, and in
                    # doing so tested nine of them against nothing.
                    plain = next((r for r in runs
                                  if r.get("person") == pid
                                  and r["client"] == "apple-mail-macos"
                                  and r["engine"] == eng and r["width"] == 900
                                  and r["scheme"] == "light"), None)
                    if plain is None:
                        add("MED", tag, "X7",
                            "no plain render to compare against - host-leak "
                            "check did not run")
                    else:
                        if abs(plain["tableW"] - d["tableW"]) > 1 or \
                                abs(plain["tableH"] - d["tableH"]) > 2:
                            add("HIGH", tag, "X7",
                                f"host styles leak in: "
                                f"{plain['tableW']}x{plain['tableH']} plain vs "
                                f"{d['tableW']}x{d['tableH']} hostile")

                # Nothing may be lost to a sanitiser.
                if baseline is None and scheme == "light" and xf == "none":
                    baseline = d["textContent"]
                elif baseline and d["textContent"] != baseline:
                    add("HIGH", tag, "X4",
                        "rendered text differs from the untransformed baseline")

        for b in launched.values():
            b.close()


# --------------------------------------------------------------------------
def audit_site(engines, people, findings, runs):
    """The install page is a web page, so it gets browser testing too.

    The clipboard is the part most likely to differ: write() needs transient
    user activation, and the engines disagree about how long that survives an
    await.
    """
    def add(sev, scope, check, msg):
        findings.append({"severity": sev, "scope": scope, "check": check,
                         "message": msg})

    port = free_port()
    serve(DOCS, port)
    local = f"http://127.0.0.1:{port}/"
    company = load_company()
    published = company["base_url"]

    with sync_playwright() as p:
        for eng in engines:
            browser = getattr(p, eng).launch(
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
                if eng == "chromium" else [])
            for width, label in ((1280, "desktop"), (390, "phone")):
                ctx = browser.new_context(
                    viewport={"width": width, "height": 900},
                    device_scale_factor=2)
                if eng == "chromium":
                    try:
                        ctx.grant_permissions(
                            ["clipboard-read", "clipboard-write"], origin=local)
                    except Exception:
                        pass

                page = ctx.new_page()
                # The pages reference the published asset URLs. Serve those from
                # the local build so the audit tests the real page rather than a
                # rewritten copy, without depending on the network.
                page.route(
                    published + "**",
                    lambda route: route.fulfill(
                        path=os.path.join(
                            DOCS, route.request.url[len(published):].split("?")[0])
                    ) if os.path.isfile(os.path.join(
                        DOCS, route.request.url[len(published):].split("?")[0]))
                    else route.abort())

                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))

                # The directory and the help page are what staff hit first, so
                # they get the same overflow and dead-link checks as the
                # install pages.
                #
                # Discovered from disk, not listed here. A hardcoded pair
                # silently stopped covering half the site the day a second
                # language was added, and a translated page is exactly where
                # an overflow or a dead relative link would appear first.
                pages = []
                for d, _, files in os.walk(DOCS):
                    if "index.html" not in files:
                        continue
                    rel = os.path.relpath(d, DOCS).replace(os.sep, "/")
                    rel = "" if rel == "." else rel + "/"
                    if "people/" in rel:
                        continue          # install pages, handled below
                    pages.append((rel, rel.rstrip("/") or "index"))
                if not pages:
                    raise SystemExit("no site pages found under docs/")

                # Install pages, in every language they were built in. This
                # was `people/<id>/` spelled out, which tested the copy button
                # - the one control anybody has to press - in English only,
                # while half the staff would open the Vietnamese page.
                installs = []
                for d, _, files in os.walk(DOCS):
                    if "index.html" not in files:
                        continue
                    rel = os.path.relpath(d, DOCS).replace(os.sep, "/")
                    parts = rel.split("/")
                    if len(parts) >= 2 and parts[-2] == "people":
                        installs.append((rel + "/", rel.replace("/", "-")))
                if len(installs) < len(people):
                    raise SystemExit(
                        f"found {len(installs)} install page(s) for "
                        f"{len(people)} person record(s) - the build writes "
                        f"one per person per language")

                # "vi/help" is a legitimate page name and an illegal filename
                # fragment - left alone it writes site--vi/help--*.png, which
                # creates a directory and slips past the .gitignore that only
                # matches PNGs one level down.
                pages = [(p, n.replace("/", "-")) for p, n in pages]

                for path, name in sorted(pages):
                    page.goto(local + path, wait_until="networkidle")
                    tag = f"site--{name}--{eng}--{label}"
                    page.screenshot(path=os.path.join(OUT, f"{tag}.png"),
                                    full_page=True)
                    over = page.evaluate(
                        "() => document.documentElement.scrollWidth - "
                        "document.documentElement.clientWidth")
                    if over > 1:
                        add("HIGH", tag, "S1",
                            f"{name} page scrolls horizontally by {over}px")
                    # An internal link that 404s strands whoever followed it.
                    dead = page.evaluate(
                        """() => Array.from(document.querySelectorAll('a[href]'))
                             .map(a => a.getAttribute('href'))
                             .filter(h => h && !/^(https?:|mailto:|tel:|#)/.test(h))""")
                    for href in set(dead):
                        r = page.request.get(local + path + href)
                        if not r.ok:
                            add("HIGH", tag, "S4",
                                f"{name} links to {href} -> {r.status}")
                    runs.append({"kind": "site", "person": name, "engine": eng,
                                 "width": width, "copyOk": None,
                                 "status": f"{len(set(dead))} internal link(s) ok",
                                 "screenshot": f"{tag}.png"})

                for rel, who in sorted(installs):
                    page.goto(local + rel, wait_until="networkidle")
                    page.wait_for_timeout(300)

                    tag = f"site--{who}--{eng}--{label}"
                    page.screenshot(path=os.path.join(OUT, f"{tag}.png"),
                                    full_page=True)

                    over = page.evaluate(
                        "() => document.documentElement.scrollWidth - "
                        "document.documentElement.clientWidth")
                    if over > 1:
                        add("HIGH", tag, "S1",
                            f"install page scrolls horizontally by {over}px")

                    page.click("#copy")
                    # Wait for a terminal class, not for the text to change.
                    # Keying on wording lets an intermediate message look like
                    # success and read the status before it has settled.
                    try:
                        page.wait_for_function(
                            "() => {const s=document.getElementById('status');"
                            "return s && /\\b(ok|err)\\b/.test(s.className);}",
                            timeout=25000)
                    except Exception:
                        pass
                    status = page.eval_on_selector(
                        "#status", "e => [e.className, e.textContent]")
                    ok = "ok" in status[0]
                    if not ok:
                        add("HIGH", tag, "S2",
                            f"copy failed in {eng}: {status[1][:110]}")
                    runs.append({"kind": "site", "person": who,
                                 "engine": eng, "width": width,
                                 "copyOk": ok, "status": status[1][:160],
                                 "screenshot": f"{tag}.png"})

                    page.screenshot(path=os.path.join(OUT, f"{tag}--copied.png"),
                                    full_page=True)

                if errors:
                    add("MED", f"site--{eng}--{label}", "S3",
                        f"page errors: {errors[:2]}")
                ctx.close()
            browser.close()


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engines", default="chromium,webkit,firefox")
    ap.add_argument("--require-engines", default="",
                    help="Comma-separated engines that MUST be present. Use in "
                         "CI so a missing engine fails the run instead of "
                         "quietly reducing coverage.")
    ap.add_argument("--skip-site", action="store_true")
    args = ap.parse_args()

    wanted = [e.strip() for e in args.engines.split(",") if e.strip()]
    engines = []
    with sync_playwright() as p:
        for e in wanted:
            # Launching is not enough - an engine can start and still fail to
            # create a web process. Render something before calling it usable.
            try:
                b = getattr(p, e).launch(
                    args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
                    if e == "chromium" else [])
                pg = b.new_page()
                pg.set_content("<p>probe</p>")
                pg.evaluate("() => document.body.innerText")
                b.close()
                engines.append(e)
            except Exception as ex:
                print(f"  engine {e} unavailable: {str(ex).splitlines()[0][:90]}")
    if not engines:
        raise SystemExit("No rendering engine available.")
    required = [e.strip() for e in args.require_engines.split(",") if e.strip()]
    absent = [e for e in required if e not in engines]
    if absent:
        raise SystemExit(
            f"Required engine(s) unavailable: {', '.join(absent)}.\n"
            f"Coverage would silently drop, so this is a failure rather than "
            f"a smaller run.")
    print(f"engines: {', '.join(engines)}")

    company = load_company()
    people = load_people(company)
    if not people:
        raise SystemExit("No employee records in src/people/")

    port = free_port()
    serve(DOCS, port)
    base = f"http://127.0.0.1:{port}/"
    tmp = tempfile.mkdtemp(prefix="crossclient-")
    subprocess.run([sys.executable, os.path.join(ROOT, "build", "generate.py"),
                    "--base", base, "--out-root", tmp],
                   check=True, capture_output=True)
    # Every style, not just the one signature.html holds. check.py already
    # does this; leaving it here would have tested one tenth of what ships
    # against 14 clients and called it coverage.
    sig_by_id = {}
    for rec in people:
        for sid, _fn in STYLES:
            fp = os.path.join(tmp, rec["id"], f"sig-{sid}.html")
            if not os.path.isfile(fp):
                raise SystemExit(f"{fp} missing - generate.py runs first")
            with open(fp, encoding="utf-8") as fh:
                sig_by_id[f'{rec["id"]}--{sid}'] = fh.read()
    if len(sig_by_id) != len(people) * len(STYLES):
        raise SystemExit("style coverage is incomplete")

    findings, runs = [], []
    variants = [dict(r, id=f'{r["id"]}--{sid}')
                for r in people for sid, _fn in STYLES]
    audit_signature(engines, sig_by_id, variants, findings, runs)
    if not args.skip_site:
        audit_site(engines, people, findings, runs)

    counts = {s: sum(1 for f in findings if f["severity"] == s)
              for s in ("HIGH", "MED", "LOW", "UNCOVERED")}
    missing_engines = sorted(set(c[2] for c in CLIENTS) - set(engines))
    uncovered = sorted({f["message"] for f in findings
                        if f["severity"] == "UNCOVERED"})
    report = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"),
              "engines": engines, "missingEngines": missing_engines,
              "uncovered": uncovered, "runs": runs, "findings": findings,
              "counts": counts}
    with open(os.path.join(OUT, "report.json"), "w") as fh:
        json.dump(report, fh, indent=2)

    sig_runs = [r for r in runs if r.get("kind") != "site"]
    print(f"\nsignature runs: {len(sig_runs)}   "
          f"site runs: {len(runs)-len(sig_runs)}   "
          f"screenshots: {len([f for f in os.listdir(OUT) if f.endswith('.png')])}")
    print(f"findings: HIGH={counts['HIGH']} MED={counts['MED']} "
          f"LOW={counts['LOW']}")
    seen = set()
    for f in findings:
        if f["severity"] == "UNCOVERED":
            continue
        k = (f["check"], f["message"])
        if k in seen:
            continue
        seen.add(k)
        print(f"  [{f['severity']:4}] {f['check']:3} {f['scope'][:44]:44} {f['message']}")

    if uncovered:
        print(f"\nNOT TESTED - engine unavailable: {', '.join(missing_engines)}")
        for u in uncovered:
            print(f"  - {u}")
        print("  These are untested, not passing. Re-run where the engine "
              "installs, or verify by hand.")
    return report


if __name__ == "__main__":
    r = main()
    sys.exit(1 if r["counts"]["HIGH"] or r["counts"]["MED"] else 0)
