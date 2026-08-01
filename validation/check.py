#!/usr/bin/env python3
"""
Validate every employee's signature.

Per person: {900px, 320px} x {images loaded, images blocked} = 4 layout runs,
plus {light, dark, forced-inversion} = 3 appearance runs. Seven screenshots
each, all written to validation/screenshots/<id>-*.png.

Gate: HIGH 0, MED 0, LOW 0. No allowlist. If a contrast assertion fails,
coloured text has been reintroduced somewhere - find it rather than widening
the threshold.

Signatures are regenerated against the local server's own base URL into a
temp directory, so a localhost URL can never end up in the published tree.
"""
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "build"))
from model import DOCS, load_company, load_people   # noqa: E402
from styles import STYLES                          # noqa: E402
from model import OCHRE, UMBER                     # noqa: E402

SHOTS = os.path.join(HERE, "screenshots")
os.makedirs(SHOTS, exist_ok=True)

WIDTHS = {"desktop": 900, "narrow": 320}
HOST_PAD = 16
DARK_STATES = {
    "light":      ("#FFFFFF", "#000000", ""),
    "gmaildark":  ("#1F1F1F", "#E8E8E8", ""),
    "forceddark": ("#FFFFFF", "#000000", "filter:invert(1) hue-rotate(180deg);"),
}
DECORATIVE = re.compile(r"^[\W_]+$", re.UNICODE)


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]; s.close(); return p


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


def serve(root, port):
    h = lambda *a, **k: Quiet(*a, directory=root, **k)
    srv = ThreadingHTTPServer(("127.0.0.1", port), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def srgb_to_lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb):
    r, g, b = (srgb_to_lin(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg, bg):
    l1, l2 = luminance(fg), luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return round((hi + 0.05) / (lo + 0.05), 2)


def parse_rgb(s):
    m = re.findall(r"[\d.]+", s or "")
    return tuple(int(float(x)) for x in m[:3]) if len(m) >= 3 else None


HARNESS = """<!doctype html><html><head><meta charset="utf-8"/>
<style>
 html,body{{margin:0;padding:0;background:{page_bg};color:{page_fg};}}
 /* The host carries its own background so a filter-based inversion flips the
    surface and the text together, as a real inverting client does. */
 #host{{padding:{pad}px;box-sizing:border-box;width:{host_w}px;
        background:{page_bg};{extra}}}
 #host img{{{img_extra}}}
</style></head><body><div id="host">{sig}</div></body></html>"""

BLOCK_JS = """
() => {
  const imgs = Array.from(document.querySelectorAll('#host img'));
  const done = imgs.map((im, i) => new Promise(res => {
    im.addEventListener('error', () => res(true),  { once: true });
    im.addEventListener('load',  () => res(false), { once: true });
    im.setAttribute('src', '/__blocked__/missing-' + i + '.png');
  }));
  return Promise.all(done).then(r => ({count: imgs.length, errored: r.filter(Boolean).length}));
}
"""

PROBE_JS = open(os.path.join(HERE, "_probe.js")).read() if os.path.isfile(
    os.path.join(HERE, "_probe.js")) else """
() => {
  const host = document.getElementById('host'); const cs = getComputedStyle;
  const table = host.querySelector('table');
  const rect = table ? table.getBoundingClientRect() : null;

  const links = Array.from(host.querySelectorAll('a')).map(a => {
    const r = a.getBoundingClientRect();
    return { href: a.getAttribute('href'), text: (a.textContent||'').trim(),
             decoration: cs(a).textDecorationLine,
             h: Math.round(r.height), fontSize: parseFloat(cs(a).fontSize) };
  });

  const imgs = Array.from(host.querySelectorAll('img')).map(im => {
    const r = im.getBoundingClientRect(); const cell = im.closest('td');
    const cr = cell ? cell.getBoundingClientRect() : null;
    return { src: im.getAttribute('src'), alt: im.getAttribute('alt'),
             wAttr: im.getAttribute('width'), hAttr: im.getAttribute('height'),
             natural: [im.naturalWidth, im.naturalHeight],
             box: [Math.round(r.width), Math.round(r.height)],
             cellW: cr ? Math.round(cr.width) : null,
             complete: im.complete && im.naturalWidth > 0 };
  });

  // Only cells that sit beside an icon. Some styles put the social links in
  // a brand bar of their own, and comparing those against the icon rows
  // reports a misalignment that is the layout, not a defect.
  const contactLefts = Array.from(host.querySelectorAll('a'))
    .filter(a => /^(mailto:|tel:|https:)/.test(a.getAttribute('href')||''))
    .map(a => a.closest('td'))
    .filter(td => {
      if (!td) return false;
      const prev = td.previousElementSibling;
      return prev && prev.querySelector('img[src*="icon-"]');
    })
    .map(td => Math.round(td.getBoundingClientRect().left));

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
  host.querySelectorAll('div,span,a,td').forEach(el => {
    const own = Array.from(el.childNodes)
      .filter(n => n.nodeType === 3 && n.textContent.trim().length > 1)
      .map(n => n.textContent.trim()).join(' ');
    if (!own) return;
    const st = cs(el);
    if (parseFloat(st.fontSize) < 2) return;
    texts.push({ text: own.slice(0,48), color: st.color, bg: effBg(el),
                 fontSize: parseFloat(st.fontSize), fontWeight: st.fontWeight });
  });

  const rules = Array.from(host.querySelectorAll('td'))
    .filter(td => cs(td).backgroundColor === 'rgb(244, 186, 23)')
    .map(td => { const r = td.getBoundingClientRect();
      return { w: Math.round(r.width), h: Math.round(r.height),
               bgcolorAttr: td.getAttribute('bgcolor') }; });

  const colspans = Array.from(host.querySelectorAll('[colspan]')).map(td => ({
    value: parseInt(td.getAttribute('colspan'), 10),
    tableCols: Math.max(...Array.from(td.closest('table').rows)
      .map(r => Array.from(r.cells).reduce((n,c)=>n+(c.colSpan||1),0)))
  }));

  return { tableW: rect ? Math.round(rect.width) : 0,
           tableH: rect ? Math.round(rect.height) : 0,
           docScrollW: document.documentElement.scrollWidth,
           links, imgs, texts, rules, colspans, contactLefts,
           bodyText: host.innerText.trim(),
           forbidden: {
             styleTags: host.querySelectorAll('style').length,
             classAttrs: host.querySelectorAll('[class]').length,
             radius: Array.from(host.querySelectorAll('*'))
                       .filter(e => cs(e).borderTopLeftRadius !== '0px').length } };
}
"""


def run():
    company = load_company()
    people = load_people(company)
    if not people:
        raise SystemExit("No employee records in src/people/")

    port = free_port()
    serve(DOCS, port)                      # docs/ is the web root, as on Pages
    base = f"http://127.0.0.1:{port}/"

    tmp = tempfile.mkdtemp(prefix="sigcheck-")
    subprocess.run([sys.executable, os.path.join(ROOT, "build", "generate.py"),
                    "--base", base, "--out-root", tmp],
                   check=True, capture_output=True)

    findings, runs = [], []
    def add(sev, scope, vid, msg):
        findings.append({"severity": sev, "scope": scope, "check": vid,
                         "message": msg})

    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])

        # Every style, for every person. Reading only signature.html would
        # leave nine of the ten shipping unlooked-at - the same shape of bug
        # as a gate that skips silently.
        jobs = []
        for rec in people:
            for sid, _l, _n, _f in STYLES:
                fp = os.path.join(tmp, rec["id"], f"sig-{sid}.html")
                if not os.path.isfile(fp):
                    raise SystemExit(f"{fp} missing - generate.py runs first")
                jobs.append((rec, sid, fp))
        if len(jobs) != len(people) * len(STYLES):
            raise SystemExit("style coverage is incomplete")

        for rec, style_id, fp in jobs:
            pid = f"{rec['id']}--{style_id}"
            with open(fp, encoding="utf-8") as fh:
                sig = fh.read()

            if len(sig) >= 10000:
                add("HIGH", pid, "V11",
                    f"{len(sig)} chars over Gmail's 10,000 limit")

            layout = {}
            for wname, wpx in WIDTHS.items():
                for state in ("loaded", "blocked"):
                    page = browser.new_page(viewport={"width": wpx, "height": 900},
                                            device_scale_factor=2)
                    page.set_content(HARNESS.format(
                        base=base, page_bg="#FFFFFF", page_fg="#000000",
                        pad=HOST_PAD, host_w=wpx, extra="", img_extra="",
                        sig=sig))
                    page.wait_for_load_state("networkidle")
                    binfo = None
                    if state == "blocked":
                        binfo = page.evaluate(BLOCK_JS)
                        page.wait_for_timeout(250)
                    d = page.evaluate(PROBE_JS)
                    tag = f"{pid}-{wname}-{state}"
                    page.locator("#host").screenshot(
                        path=os.path.join(SHOTS, f"{tag}.png"))
                    d.update(person=pid, width=wname, viewport=wpx,
                             images=state, screenshot=f"{tag}.png")
                    runs.append(d); layout[f"{wname}-{state}"] = d
                    page.close()
                    s = tag

                    if d["docScrollW"] > wpx + 1:
                        add("HIGH", s, "V1",
                            f"scrollWidth {d['docScrollW']} > {wpx}")
                    if wname == "narrow" and d["tableW"] > wpx - 2*HOST_PAD + 1:
                        add("HIGH", s, "V1",
                            f"table {d['tableW']}px exceeds "
                            f"{wpx-2*HOST_PAD}px content box")

                    for im in d["imgs"]:
                        if im["alt"] not in ("", None):
                            add("MED", s, "V5",
                                f"{os.path.basename(im['src'])} has alt "
                                f"'{im['alt']}' - all images here are decorative")
                        if not im["wAttr"] or not im["hAttr"]:
                            add("MED", s, "V7", f"{im['src']} missing width/height")
                        if state == "loaded":
                            if not im["complete"]:
                                add("HIGH", s, "V7", f"{im['src']} failed to load")
                            elif im["natural"][0] != int(im["wAttr"]) * 2:
                                add("MED", s, "V7",
                                    f"{os.path.basename(im['src'])} natural "
                                    f"{im['natural'][0]} is not 2x {im['wAttr']}")
                        if im["cellW"] is not None and "icon-" in (im["src"] or ""):
                            if im["cellW"] < 18:
                                add("MED", s, "V6",
                                    f"icon cell collapsed to {im['cellW']}px")

                    if state == "blocked" and binfo and \
                            binfo["errored"] != binfo["count"]:
                        add("MED", s, "V5",
                            f"only {binfo['errored']}/{binfo['count']} images "
                            f"actually failed")

                    lefts = d["contactLefts"]
                    if lefts and (max(lefts) - min(lefts)) > 1:
                        add("HIGH", s, "V4",
                            f"contact cells not aligned: {lefts}")

                    for a in d["links"]:
                        if not a["href"] or not re.match(
                                r"^(https://|mailto:|tel:)", a["href"]):
                            add("HIGH", s, "V8", f"bad href {a['href']}")
                        if "underline" not in a["decoration"]:
                            add("MED", s, "V8",
                                f"link '{a['text']}' has no underline - with "
                                f"inherit colour that leaves no affordance")

                    f = d["forbidden"]
                    for k, label in (("styleTags", "<style> tag"),
                                     ("classAttrs", "class attribute"),
                                     ("radius", "border-radius")):
                        if f[k]:
                            add("HIGH", s, "V9", f"{f[k]} x {label}")

                    for c in d["colspans"]:
                        if c["value"] > c["tableCols"]:
                            add("HIGH", s, "V10",
                                f"colspan={c['value']} exceeds "
                                f"{c['tableCols']} columns")

                    # Brand presence, not one particular shape of it. The
                    # original check assumed the single design's vertical
                    # ochre rule; ten styles use horizontal rules, umber
                    # bands and colour columns, all of which are the brand
                    # doing its job.
                    brand_block = ('bgcolor="' + UMBER + '"') in sig or \
                                  ('bgcolor="' + OCHRE + '"') in sig
                    if not d["rules"] and not brand_block:
                        add("MED", s, "V12",
                            "no brand colour found - no rule and no pinned "
                            "umber or ochre block")
                    for r in d["rules"]:
                        long_side = max(r["w"], r["h"])
                        short_side = min(r["w"], r["h"])
                        if short_side < 2 or long_side < 40:
                            add("MED", s, "V12",
                                f"brand rule {r['w']}x{r['h']} is too small to "
                                f"read as a rule (want >=2 x >=40, either way up)")
                        if not r["bgcolorAttr"]:
                            add("LOW", s, "V12", "rule has no bgcolor attribute")

            # V4 cross-state. alt="" does NOT stop a renderer drawing a
            # broken-image placeholder, so what must be guaranteed is that
            # nothing MOVES and no text is lost when the placeholders appear.
            for wname in WIDTHS:
                lo, bl = layout[f"{wname}-loaded"], layout[f"{wname}-blocked"]
                if lo["contactLefts"] and bl["contactLefts"] and any(
                        abs(x - y) > 1 for x, y in
                        zip(lo["contactLefts"], bl["contactLefts"])):
                    add("HIGH", f"{pid}-{wname}", "V4",
                        "contact alignment shifts when images blocked")
                if abs(lo["tableW"] - bl["tableW"]) > 1:
                    add("HIGH", f"{pid}-{wname}", "V4",
                        f"width shifts when blocked: {lo['tableW']} vs {bl['tableW']}")
                if abs(lo["tableH"] - bl["tableH"]) > 2:
                    add("HIGH", f"{pid}-{wname}", "V4",
                        f"height shifts when blocked: {lo['tableH']} vs {bl['tableH']}")
                if lo["bodyText"] != bl["bodyText"]:
                    add("HIGH", f"{pid}-{wname}", "V4",
                        "rendered text differs loaded vs blocked")

            for state, (bg, fg, extra) in DARK_STATES.items():
                img_extra = ("filter:invert(1) hue-rotate(180deg);"
                             if state == "forceddark" else "")
                page = browser.new_page(viewport={"width": 640, "height": 700},
                                        device_scale_factor=2)
                page.set_content(HARNESS.format(
                    base=base, page_bg=bg, page_fg=fg, pad=HOST_PAD,
                    host_w=600, extra=extra, img_extra=img_extra, sig=sig))
                page.wait_for_load_state("networkidle")
                d = page.evaluate(PROBE_JS)
                page.locator("#host").screenshot(
                    path=os.path.join(SHOTS, f"{pid}-dark-{state}.png"))
                if state in ("light", "gmaildark"):
                    surface = (255, 255, 255) if state == "light" else (31, 31, 31)
                    for t in d["texts"]:
                        if DECORATIVE.match(t["text"]):
                            continue
                        c = parse_rgb(t["color"])
                        if not c:
                            continue
                        ratio = contrast(c, parse_rgb(t["bg"]) or surface)
                        size, weight = t["fontSize"], int(t["fontWeight"])
                        large = size >= 24 or (size >= 18.66 and weight >= 700)
                        need = 3.0 if large else 4.5
                        if ratio < need:
                            add("HIGH", f"{pid}-{state}", "V2",
                                f"contrast {ratio}:1 < {need}:1 for "
                                f"{size:g}px/{weight} '{t['text'][:32]}'")
                runs.append({"person": pid, "state": state, "mode": "dark",
                             "screenshot": f"{pid}-dark-{state}.png"})
                page.close()

        browser.close()

    counts = {s: sum(1 for f in findings if f["severity"] == s)
              for s in ("HIGH", "MED", "LOW")}
    report = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"),
              "people": [p["id"] for p in people],
              "runs": runs, "findings": findings, "counts": counts}
    with open(os.path.join(HERE, "report.json"), "w") as fh:
        json.dump(report, fh, indent=2)

    print(f"people: {len(people)}   runs: {len(runs)}   "
          f"screenshots: {len([f for f in os.listdir(SHOTS) if f.endswith('.png')])}")
    print(f"findings: HIGH={counts['HIGH']} MED={counts['MED']} LOW={counts['LOW']}")
    seen = set()
    for f in findings:
        k = (f["check"], f["message"])
        if k in seen:
            continue
        seen.add(k)
        print(f"  [{f['severity']:4}] {f['check']:4} {f['scope']:28} {f['message']}")
    return report


if __name__ == "__main__":
    r = run()
    sys.exit(1 if any(r["counts"].values()) else 0)
