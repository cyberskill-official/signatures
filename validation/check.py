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
from styles import STYLES, render                  # noqa: E402
from fixtures import worst_case                    # noqa: E402
from model import OCHRE, UMBER                     # noqa: E402

SHOTS = os.path.join(HERE, "screenshots")
os.makedirs(SHOTS, exist_ok=True)

# V3 is retired. It predates the current suite and no trace of what it
# checked survives in the source or the docs - so the number stays unused
# rather than being recycled, because a report from before the change and one
# from after would otherwise disagree about what V3 meant.
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

  // Environment key for the geometry baseline: the rendered width of a fixed
  // string in the signature's own font stack. Two machines that resolve the
  // same face agree here; one that falls back to a different face does not,
  // and the baseline says so rather than reporting a phantom regression.
  const fp = document.createElement('span');
  fp.style.cssText = 'position:absolute;visibility:hidden;white-space:pre;'
    + "font:13px Arial, Helvetica, sans-serif";
  fp.textContent = 'CyberSkill 0123456789 ỚẾỰỎÃỸ';
  document.body.appendChild(fp);
  const fontProbe = Math.round(fp.getBoundingClientRect().width * 100) / 100;
  fp.remove();
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

  return { fontProbe, tableW: rect ? Math.round(rect.width) : 0,
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
            for sid, _fn in STYLES:
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

            # V13 - Vietnamese stacked diacritics must fit the line box.
            #
            # CDS names ỚẾỰỎÃỸ as the canary and fails any component that
            # clips it. Clipping is not the only failure: with overflow
            # visible the glyph is not cut, it collides with the line above,
            # or it pushes the block taller than it was designed to be.
            #
            # So the measurement is a comparison, not an absolute. Render the
            # same style twice, once with the canary in name_vi and once with
            # plain Latin capitals of the same length, and see whether the
            # table grows. If it does, the leading is too tight for Vietnamese
            # and the layout moves the day someone with a name like that is
            # added - which, at a Vietnamese company, is every day.
            heights = {}
            for label, probe in (("latin", "AEUODY"), ("canary", "ỚẾỰỎÃỸ")):
                page = browser.new_page(viewport={"width": 640, "height": 700},
                                        device_scale_factor=2)
                page.set_content(HARNESS.format(
                    base=base, page_bg="#FFFFFF", page_fg="#000000",
                    pad=HOST_PAD, host_w=600, extra="", img_extra="",
                    sig=render(style_id, dict(rec, name_vi=probe),
                               company, base)))
                page.wait_for_load_state("networkidle")
                heights[label] = page.evaluate(
                    "() => {const t = document.querySelector('#host table');"
                    " return t ? Math.round(t.getBoundingClientRect().height)"
                    " : 0;}")
                if label == "canary":
                    page.locator("#host").screenshot(
                        path=os.path.join(SHOTS, f"{pid}-canary.png"))
                page.close()
            grew = heights["canary"] - heights["latin"]
            if grew > 1:
                add("HIGH", f"{pid}-canary", "V13",
                    f"Vietnamese diacritics add {grew}px - the line box does "
                    f"not contain them (latin {heights['latin']}px, canary "
                    f"{heights['canary']}px). Raise the leading on the "
                    f"identity line.")
            elif not heights["canary"]:
                add("MED", f"{pid}-canary", "V13",
                    "canary render produced no table - check did not run")

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

    # V14 - the record nobody has yet.
    #
    # Every check above runs against real people, so the suite only ever sees
    # the name lengths currently employed. CI failed on 2026-08-03 because an
    # email grew by ten characters and pushed two styles past the box; nothing
    # caught it, because the content moved and the code did not.
    #
    # This renders every style with each field at the schema's limit, six
    # socials, and a name_vi of stacked diacritics, at phone width - where
    # the box is tightest and this class of defect shows first.
    wc = worst_case(company, people[0] if people else None)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
        for sid, _fn in STYLES:
            page = browser.new_page(viewport={"width": WIDTHS["narrow"],
                                              "height": 900},
                                    device_scale_factor=2)
            page.set_content(HARNESS.format(
                base=base, page_bg="#FFFFFF", page_fg="#000000", pad=HOST_PAD,
                host_w=WIDTHS["narrow"], extra="", img_extra="",
                sig=render(sid, wc, company, base)))
            page.wait_for_load_state("networkidle")
            d = page.evaluate(PROBE_JS)
            tag = f"_worstcase--{sid}-narrow"
            page.locator("#host").screenshot(
                path=os.path.join(SHOTS, f"{tag}.png"))
            page.close()
            box = WIDTHS["narrow"] - HOST_PAD * 2
            if d["tableW"] - box > 1:
                add("HIGH", tag, "V14",
                    f"worst-case record overflows by {d['tableW'] - box}px "
                    f"({d['tableW']} vs {box}) - a longer name or address "
                    f"than anyone currently has would break this style")
            if d["docScrollW"] > WIDTHS["narrow"] + 1:
                add("HIGH", tag, "V14",
                    f"worst-case record scrolls horizontally: "
                    f"scrollWidth {d['docScrollW']} > {WIDTHS['narrow']}")
            runs.append(dict(d, person="_worstcase", style=sid,
                             width="narrow", screenshot=f"{tag}.png"))
        browser.close()

    # --- geometry baseline ---------------------------------------------
    #
    # 87 screenshots a run, compared to nothing. The rule() bug discarded
    # height:2px and font-size:0 for months without a single check noticing,
    # because every check asked "is this within tolerance" and none asked
    # "is this the same as last time".
    #
    # Geometry rather than pixels: a pixel hash would also catch it, but it
    # would fire on every machine whose browser resolves a different font,
    # and a baseline that cries wolf gets deleted. The env key below is the
    # rendered width of a fixed string, so a font difference is reported as
    # a different environment instead of a regression.
    fingerprint = {}
    for d in runs:
        key = f"{d.get('person')}-{d.get('width')}-{d.get('images', '-')}"
        if d.get("tableW"):
            fingerprint[key] = [d["tableW"], d["tableH"]]

    env_key = None
    for d in runs:
        if d.get("fontProbe"):
            env_key = d["fontProbe"]
            break

    bpath = os.path.join(HERE, "baseline.json")
    if not os.path.isfile(bpath):
        with open(bpath, "w") as fh:
            json.dump({"env": env_key, "geometry": fingerprint}, fh,
                      indent=1, sort_keys=True)
        print(f"  baseline written ({len(fingerprint)} measurements) - "
              f"commit it, and future runs compare against it")
    else:
        with open(bpath) as fh:
            base_doc = json.load(fh)
        if base_doc.get("env") != env_key:
            add("LOW", "baseline", "V15",
                f"baseline was recorded in a different environment "
                f"(font probe {base_doc.get('env')} vs {env_key}) - geometry "
                f"not compared. Re-record it on the machine CI uses.")
        else:
            old = base_doc.get("geometry", {})
            for k, v in sorted(fingerprint.items()):
                if k not in old:
                    add("LOW", k, "V15", "new measurement, not in the baseline")
                elif abs(old[k][0] - v[0]) > 1 or abs(old[k][1] - v[1]) > 1:
                    add("HIGH", k, "V15",
                        f"geometry changed since the baseline: "
                        f"{old[k][0]}x{old[k][1]} -> {v[0]}x{v[1]}. If this is "
                        f"intended, delete validation/baseline.json and re-run "
                        f"to re-record.")
            for k in sorted(set(old) - set(fingerprint)):
                add("LOW", k, "V15", "in the baseline but no longer measured")

    # Counted here, after every check has run. This sat above V14 and V15,
    # so their findings were printed but never counted - and the exit code
    # reads counts, which means a run with a HIGH finding exited 0 and CI
    # went green. The findings list is shared by reference, so the report
    # looked right while the gate did not.
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
