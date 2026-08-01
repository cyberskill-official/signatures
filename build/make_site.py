#!/usr/bin/env python3
"""
Build the GitHub Pages site: a signature directory and a per-person install
page.

The site is the product for everyone except whoever adds a new employee. Staff
never clone the repo or run Python - they open their page, press one button,
and paste into Gmail.

Asset URLs on these pages are the SAME absolute URLs the signature payload
uses. That is deliberate: if the preview renders, the published URLs are live,
so looking at the page is itself the proof. The Verify button then re-checks
each one explicitly before allowing a copy.
"""
import argparse
import html as H
import json
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import (AVATAR, DOCS, DOCS_PEOPLE, LOGO, OCHRE, SRC, TABLE_W,
                   UMBER, asset_url, load_company, load_people, person_asset,
                   shared_asset)
from styles import DEFAULT_STYLE, STYLES

LOCALES = os.path.join(SRC, "locales")
# English is the reference. Every other locale must define exactly the same
# keys - see load_locales for why a missing one is fatal.
DEFAULT_LOCALE = "en"


def load_locales():
    """Read src/locales/*.yml as {code: {section.key: text}}.

    A missing key is a build failure rather than an English fallback. The
    fallback is the tempting option and it is the wrong one: it produces a
    page that looks finished, reads half-translated to the only people who
    would notice, and never appears in any log.
    """
    out = {}
    for fn in sorted(os.listdir(LOCALES)):
        if not fn.endswith(".yml"):
            continue
        code = os.path.splitext(fn)[0]
        with open(os.path.join(LOCALES, fn), encoding="utf-8") as fh:
            doc = yaml.safe_load(fh) or {}
        flat = {}
        for section, items in doc.items():
            if not isinstance(items, dict):
                raise SystemExit(f"{fn}: '{section}' must be a map of strings")
            for k, v in items.items():
                flat[f"{section}.{k}"] = "" if v is None else str(v)
        out[code] = flat

    if DEFAULT_LOCALE not in out:
        raise SystemExit(f"src/locales/{DEFAULT_LOCALE}.yml is missing")

    ref = set(out[DEFAULT_LOCALE])
    for code, flat in out.items():
        if code == DEFAULT_LOCALE:
            continue
        missing, extra = sorted(ref - set(flat)), sorted(set(flat) - ref)
        if missing or extra:
            lines = [f"src/locales/{code}.yml does not match "
                     f"{DEFAULT_LOCALE}.yml:"]
            lines += [f"  missing: {k}" for k in missing]
            lines += [f"  unknown: {k}" for k in extra]
            raise SystemExit("\n".join(lines))
    return out


class T:
    """Lookup for one locale. Values are formatted, then escaped only where
    the caller asks - several strings intentionally carry <code> and <strong>.
    """

    def __init__(self, code, strings):
        self.code = code
        self.s = strings

    def __call__(self, key, **kw):
        try:
            v = self.s[key]
        except KeyError:
            raise SystemExit(f"locale {self.code}: no string named '{key}'")
        return v.format(**kw) if kw else v

    def esc(self, key, **kw):
        return H.escape(self(key, **kw))

# Every colour that differs between light and dark is a variable, so a theme
# is one block of values rather than a restatement of every rule. Two things
# are deliberately NOT variables:
#
#   - the header, which is umber in both themes by design
#   - the preview surfaces, which pin literal colours further down, because a
#     "light mail client" preview that follows the page theme demonstrates
#     nothing and light text on a white surface disappears entirely
DARK = ("--ink:#EDE8E3;--muted:#A5A19D;--line:#3A342E;--bg:#17140F;"
        "--card:#211C16;--link:#F0C463;--cta-bg:#F4BA17;--cta-fg:#3A1B0B;"
        "--cta-bg-h:#FFD166;--ghost-fg:#F0C463;--ghost-line:#4A423A;"
        "--ghost-bg-h:#2B241C;--code-bg:#2B241C;--code-fg:#EDE8E3;"
        "--field-bg:#211C16;--ok:#6FD68E;--err:#FF9B92;--ph-bg:#2B241C;")

CSS = """
  :root{--umber:#45210E;--ochre:#F4BA17;--accent:#9E5E3E;--ink:#22201E;
        --muted:#6B6B6B;--line:#E6E0D8;--bg:#FBF9F7;--card:#FFFFFF;
        --link:#45210E;--cta-bg:#45210E;--cta-fg:#FFFFFF;--cta-bg-h:#5C2D14;
        --ghost-fg:#45210E;--ghost-line:#E6E0D8;--ghost-bg-h:#F6F1EB;
        --code-bg:#F1ECE6;--code-fg:inherit;--field-bg:#FAF8F6;
        --ok:#1B7F3B;--err:#B3261E;--ph-bg:#45210E;}
  html{color-scheme:light;}
  html[data-theme="dark"]{color-scheme:dark;}
  @media (prefers-color-scheme: dark){html:not([data-theme="light"]){color-scheme:dark;}}
  *{box-sizing:border-box;}
  body{margin:0;background:var(--bg);color:var(--ink);
       font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
       -webkit-font-smoothing:antialiased;}
  a{color:var(--link);}
  .wrap{max-width:1080px;margin:0 auto;padding:0 24px;}
  header.site{background:var(--umber);color:#fff;padding:34px 0 30px;}
  header.site a{color:#fff;text-decoration:none;}
  .brandrow{display:flex;align-items:center;gap:14px;}
  .brandrow img{width:40px;height:40px;display:block;border-radius:8px;}
  .brandname{font-size:15px;font-weight:700;letter-spacing:.14em;
             text-transform:uppercase;}
  header.site h1{margin:18px 0 6px;font-size:30px;letter-spacing:-.4px;}
  header.site p{margin:0;color:#E8D9CD;max-width:62ch;}
  .tabs{display:flex;gap:8px;margin:20px 0 -6px;flex-wrap:wrap;}
  .tab{display:inline-block;padding:8px 15px;border-radius:8px;font-size:14px;
       font-weight:600;background:rgba(255,255,255,.10);color:#F3E7DC;}
  .tab:hover{background:rgba(255,255,255,.18);}
  .tab.on{background:var(--ochre);color:#3A1B0B;}
  .ochre{height:4px;background:var(--ochre);}
  /* help page */
  .lede{font-size:17px;line-height:1.6;max-width:62ch;margin:0 0 26px;}
  .route{padding:22px 24px;margin:0 0 16px;}
  .route h3{margin:0 0 4px;font-size:18px;}
  .route .who{margin:0 0 14px;color:var(--muted);font-size:14px;}
  .route ol,.route ul{margin:0;padding-left:20px;}
  .route li{margin:7px 0;}
  .cta{display:inline-block;background:var(--cta-bg);color:var(--cta-fg);border-radius:8px;
       padding:11px 20px;font-size:14px;font-weight:600;text-decoration:none;
       margin-top:14px;}
  .cta:hover{background:var(--cta-bg-h);color:var(--cta-fg);}
  .cta.ghost{background:transparent;color:var(--ghost-fg);
             box-shadow:inset 0 0 0 1.5px var(--ghost-line);}
  .cta.ghost:hover{background:var(--ghost-bg-h);color:var(--ghost-fg);}
  .note{border-left:3px solid var(--ochre);padding:2px 0 2px 14px;
        margin:18px 0;color:var(--muted);font-size:14px;max-width:62ch;}
  .faq{padding:6px 24px 10px;margin:0 0 16px;}
  .faq details{border-top:1px solid var(--line);padding:14px 0;margin:0;}
  .faq details:first-of-type{border-top:0;}
  .faq summary{font-weight:600;color:var(--ink);font-size:15px;}
  .faq p{margin:10px 0 0;color:var(--muted);max-width:62ch;}
  main{padding:38px 0 80px;}
  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;}
  .steps{padding:20px 24px;margin:0 0 34px;}
  .steps h2{margin:0 0 10px;font-size:12px;letter-spacing:.09em;
            text-transform:uppercase;color:var(--muted);}
  .steps ol{margin:0;padding-left:20px;} .steps li{margin:5px 0;}
  code{background:var(--code-bg);color:var(--code-fg);padding:1px 6px;
       border-radius:4px;font-size:.9em;}
  .toolbar{display:flex;gap:12px;align-items:center;margin:0 0 18px;
           flex-wrap:wrap;}
  .search{flex:1 1 260px;padding:11px 14px;border:1px solid var(--line);
          border-radius:9px;font-size:14px;background:var(--card);
          color:var(--ink);}
  .count{font-size:13px;color:var(--muted);}
  .people{display:grid;gap:16px;
          grid-template-columns:repeat(auto-fill,minmax(280px,1fr));}
  .person{display:flex;gap:14px;align-items:center;padding:16px;
          text-decoration:none;color:inherit;transition:.15s;}
  .person:hover{border-color:var(--accent);
                box-shadow:0 2px 14px rgba(69,33,14,.09);transform:translateY(-1px);}
  .person img{width:56px;height:56px;display:block;flex:0 0 56px;}
  .ph{width:56px;height:56px;flex:0 0 56px;border-radius:50%;
      background:var(--ph-bg);color:var(--ochre);display:flex;
      align-items:center;justify-content:center;font-weight:700;font-size:19px;}
  .person .n{font-weight:700;font-size:16px;}
  .person .r{font-size:13px;color:var(--muted);}
  .person .go{margin-left:auto;color:var(--accent);font-size:19px;}
  .empty{padding:34px;text-align:center;color:var(--muted);}
  footer.site{border-top:1px solid var(--line);padding:26px 0 50px;
              color:var(--muted);font-size:13px;}
  /* person page */
  .crumb{font-size:13px;margin:0 0 18px;}
  .crumb a{color:var(--muted);}
  h2.person-name{margin:0 0 2px;font-size:27px;letter-spacing:-.3px;}
  .person-role{margin:0 0 22px;color:var(--muted);}
  .bar{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin:0 0 20px;}
  .btn{background:var(--cta-bg);color:var(--cta-fg);border:0;border-radius:8px;
       padding:12px 22px;font-size:14px;font-weight:600;cursor:pointer;}
  .btn:hover{background:var(--cta-bg-h);} .btn[disabled]{opacity:.5;cursor:progress;}
  .status{font-size:13px;color:var(--muted);}
  .status.ok{color:var(--ok);font-weight:600;}
  .status.err{color:var(--err);font-weight:600;}
  .grid{display:flex;gap:20px;align-items:flex-start;flex-wrap:wrap;}
  .col{min-width:0;} .col.narrow{flex:0 0 auto;} .col.desk{flex:0 1 556px;}
  .colhead{font-size:11px;letter-spacing:.09em;text-transform:uppercase;
           color:var(--muted);margin:0 0 7px;}
  .dim{text-transform:none;letter-spacing:0;font-weight:700;}
  .dim.good{color:var(--ok);} .dim.bad{color:var(--err);}
  /* Pinned, never inherited, in every theme. These four rules ARE the
     product: each one shows what a mail client renders, so a surface that
     follows the page theme is showing the reader their own browser instead
     of their recipient's inbox. */
  .surface{border:1px solid #D8D2CA;border-radius:9px;padding:18px;
           overflow-x:auto;background:#FFFFFF;color:#22201E;}
  /* The signature is fluid (width:100% capped at 520px), so a shrink-to-fit
     flex column collapses it to min-content and the "desktop" preview stops
     being a desktop preview. Pin the desktop surface wide enough for the
     table to reach its full 520px. */
  .surface.desk{width:556px;max-width:100%;}
  .surface.w320{width:320px;flex:0 0 320px;}
  .surface.dark{background:#1F1F1F;border-color:#3A3A3A;color:#E8E8E8;}
  .surface.inv{background:#FFFFFF;color:#22201E;
               filter:invert(1) hue-rotate(180deg);}
  .surface.inv img{filter:invert(1) hue-rotate(180deg);}
  .sub{font-size:12px;color:var(--muted);margin:0 0 7px;}
  .dark3 .col{flex:1 1 320px;min-width:300px;}
  details{margin-top:20px;} summary{cursor:pointer;font-size:13px;color:var(--muted);}
  textarea{width:100%;height:150px;margin-top:10px;padding:12px;
           font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;
           border:1px solid var(--line);border-radius:8px;
           background:var(--field-bg);color:var(--ink);}
  /* Keyboard focus. Every interactive element here has custom styling that
     overrode the browser default without replacing it, so tabbing to the
     copy button showed nothing at all. */
  .skip{position:absolute;left:-9999px;top:0;background:var(--ochre);
        color:#3A1B0B;padding:12px 18px;border-radius:0 0 8px 0;
        font-weight:700;z-index:100;text-decoration:none;}
  .skip:focus{left:0;}
  a:focus-visible,button:focus-visible,input:focus-visible,
  summary:focus-visible{outline:3px solid var(--ochre);outline-offset:3px;
                        border-radius:4px;}
  header.site a:focus-visible{outline-color:#FFFFFF;}
  .vh{position:absolute;width:1px;height:1px;margin:-1px;padding:0;
      overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0;}
  @media (prefers-reduced-motion: reduce){
    *{transition:none !important;animation:none !important;}
  }
  .styles{display:grid;gap:9px;margin:0 0 8px;
          grid-template-columns:repeat(auto-fill,minmax(196px,1fr));}
  .stylebtn{display:block;text-align:left;padding:11px 13px;cursor:pointer;
            background:var(--card);color:inherit;font:inherit;
            border:1px solid var(--line);border-radius:9px;}
  .stylebtn:hover{border-color:var(--accent);}
  .stylebtn[aria-pressed="true"]{border-color:var(--ochre);
            box-shadow:inset 0 0 0 1.5px var(--ochre);}
  .stylebtn .sname{display:block;font-weight:700;font-size:14px;}
  .stylebtn .snote{display:block;font-size:12.5px;line-height:17px;
                   color:var(--muted);padding-top:2px;}
  .sec{margin:34px 0 12px;font-size:12px;letter-spacing:.09em;
       text-transform:uppercase;color:var(--muted);}
  /* Theme control. Hidden until the inline script in <head> marks the page
     as scripted, because a button that cannot do anything is worse than no
     button - without JS the OS preference below still applies. */
  .themebtn{display:none;}
  html.js .themebtn{display:inline-flex;align-items:center;gap:7px;
        padding:8px 13px;border:0;border-radius:8px;
        background:rgba(255,255,255,.10);color:#F3E7DC;font:inherit;
        font-size:14px;font-weight:600;cursor:pointer;}
  html.js .themebtn:hover{background:rgba(255,255,255,.18);}
  .themebtn svg{width:16px;height:16px;display:block;}
  /* The icon names the destination, not the current state - a sun while
     already light reads as "you are here", which is not what a button means.
     CSS does the swap so it is right on first paint; the script only has to
     keep the label in step. */
  .themebtn .sun{display:none;} .themebtn .moon{display:block;}
  html[data-theme="dark"] .themebtn .sun{display:block;}
  html[data-theme="dark"] .themebtn .moon{display:none;}
  @media (prefers-color-scheme: dark){
    html:not([data-theme="light"]) .themebtn .sun{display:block;}
    html:not([data-theme="light"]) .themebtn .moon{display:none;}
  }
  .navrow{display:flex;align-items:flex-end;gap:12px;}
  .navrow .tabs{flex:1 1 auto;}
  .navtools{display:flex;align-items:center;gap:8px;margin-left:auto;
            margin-bottom:-6px;}
  /* Outlined rather than filled, so it does not read as a third page in the
     tab group beside it. */
  .langlink{display:inline-flex;align-items:center;gap:7px;background:none;
            box-shadow:inset 0 0 0 1.5px rgba(255,255,255,.28);}
  .langlink:hover{background:rgba(255,255,255,.12);}
  .langlink svg{width:15px;height:15px;display:block;opacity:.85;}
"""

# Dark applies two ways: automatically from the OS, and explicitly from the
# toggle. The :not() is what lets an explicit "light" win over a dark OS -
# without it the media query would keep overriding the user's own choice.
CSS += ("""
  @media (prefers-color-scheme: dark){
    html:not([data-theme="light"]){%s}
  }
  html[data-theme="dark"]{%s}
""" % (DARK, DARK))


def head(title, desc, base, canonical, company, t, css_extra=""):
    """Document head, including what a link preview needs.

    This URL gets pasted into Slack, Zalo and email. Without og: tags it
    renders as a bare link with no card, which is a poor first impression for
    a page asking people to trust it with a photograph.

    Indexing defaults to OFF. Every employee's name, job title, work email and
    photo are on this site; making that harvestable by default is a decision
    nobody made. Set `index_site: true` in company.yml to allow crawlers.
    Note that robots.txt alone would not be enough - it asks crawlers not to
    fetch, not to omit from results - so the meta tag is what does the work.
    """
    og = asset_url(base, "assets/shared/og-card.png",
                   shared_asset("og-card.png"))
    icon = asset_url(base, "assets/shared/favicon-32.png",
                     shared_asset("favicon-32.png"))
    touch = asset_url(base, "assets/shared/apple-touch-icon.png",
                      shared_asset("apple-touch-icon.png"))
    robots = ("index,follow" if company.get("index_site")
              else "noindex,nofollow")
    ti, d = H.escape(title), H.escape(desc)
    return f"""<!doctype html>
<html lang="{t('meta.html_lang')}">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta name="color-scheme" content="light dark"/>
<meta name="theme-color" content="{UMBER}"/>
<meta name="robots" content="{robots}"/>
<meta name="description" content="{d}"/>
<link rel="canonical" href="{canonical}"/>
<link rel="icon" type="image/png" sizes="32x32" href="{icon}"/>
<link rel="apple-touch-icon" href="{touch}"/>
<meta property="og:type" content="website"/>
<meta property="og:site_name" content="{H.escape(company['name'])}"/>
<meta property="og:title" content="{ti}"/>
<meta property="og:description" content="{d}"/>
<meta property="og:url" content="{canonical}"/>
<meta property="og:image" content="{og}"/>
<meta property="og:image:width" content="1200"/>
<meta property="og:image:height" content="630"/>
<meta name="twitter:card" content="summary_large_image"/>
<title>{ti}</title>
<script>/* Before first paint, or the page flashes the wrong theme on every
  load for anyone who chose one. Also marks the document as scripted, which
  is what reveals the toggle - without JS the OS preference still applies and
  a dead button would be worse than none. */
(function(){{var r=document.documentElement;r.className+=' js';
try{{var t=localStorage.getItem('theme');
if(t==='dark'||t==='light')r.setAttribute('data-theme',t);}}catch(e){{}}}})();</script>
<style>{CSS}{css_extra}</style>
</head>
<body>
<a class="skip" href="#main">{H.escape(t("chrome.skip"))}</a>"""


def site_header(company, logo_url, root, subtitle, h1, t, alt=None, here=""):
    """`alt` is (href, label, lang) for the other language, or None on a page
    that has no translation."""
    def tab(label, href, key):
        cur = ' aria-current="page"' if key == here else ""
        return f'<a class="tab{" on" if key == here else ""}" href="{href}"{cur}>{H.escape(label)}</a>'

    dark_j, light_j = json.dumps(t("chrome.theme_dark")), json.dumps(t("chrome.theme_light"))
    to_dark_j, to_light_j = (json.dumps(t("chrome.theme_to_dark")),
                             json.dumps(t("chrome.theme_to_light")))
    langlink = ""
    if alt:
        href, label, code = alt
        # hreflang and lang both matter: hreflang tells a crawler what is on
        # the other end, lang tells a screen reader how to pronounce the label
        # it is about to read, which is the whole point of writing it in the
        # other language.
        globe = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"'
                 ' stroke-width="2" aria-hidden="true"><circle cx="12" cy="12"'
                 ' r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18'
                 'M12 3a15 15 0 0 0 0 18"/></svg>')
        langlink = (f'<a class="tab langlink" href="{H.escape(href)}" '
                    f'hreflang="{code}" lang="{code}">{globe}'
                    f'{H.escape(label)}</a>')
    return f"""
<header class="site">
  <div class="wrap">
    <a class="brandrow" href="{root}">
      <img src="{logo_url}" alt=""/>
      <span class="brandname">{H.escape(company['name'])}</span>
    </a>
    <h1>{H.escape(h1)}</h1>
    <p>{subtitle}</p>
    <div class="navrow">
      <nav class="tabs">
        {tab(t("chrome.nav_all"), root, "index")}
        {tab(t("chrome.nav_help"), root + "help/", "help")}
      </nav>
      <div class="navtools">{langlink}
      <button class="themebtn" id="themebtn" type="button">
        <svg class="sun" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round" aria-hidden="true">
          <circle cx="12" cy="12" r="4.2"/><path d="M12 2v2.6M12 19.4V22
          M2 12h2.6M19.4 12H22M4.9 4.9l1.9 1.9M17.2 17.2l1.9 1.9
          M19.1 4.9l-1.9 1.9M6.8 17.2l-1.9 1.9"/>
        </svg>
        <svg class="moon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linejoin="round" aria-hidden="true">
          <path d="M20 14.2A8.2 8.2 0 0 1 9.8 4a8.4 8.4 0 1 0 10.2 10.2z"/>
        </svg>
        <span class="themebtn-t">{H.escape(t("chrome.theme_dark"))}</span>
      </button></div>
    </div>
<script>/* The button's icon is swapped by CSS so it is correct before this
  runs; this only keeps the word and the accessible name in step, and follows
  the OS for anyone who has never chosen. */
(function(){{
  var b=document.getElementById('themebtn'),r=document.documentElement,
      mq=window.matchMedia('(prefers-color-scheme: dark)');
  function isDark(){{var a=r.getAttribute('data-theme');
    return a?a==='dark':mq.matches;}}
  var W={{d:{dark_j},l:{light_j},ad:{to_dark_j},al:{to_light_j}}};
  function sync(){{var d=isDark();
    b.querySelector('.themebtn-t').textContent=d?W.l:W.d;
    b.setAttribute('aria-label',d?W.al:W.ad);}}
  sync();
  b.addEventListener('click',function(){{
    var next=isDark()?'light':'dark';
    r.setAttribute('data-theme',next);
    try{{localStorage.setItem('theme',next);}}catch(e){{}}
    sync();}});
  try{{if(!localStorage.getItem('theme'))mq.addEventListener('change',sync);}}
  catch(e){{}}
}})();</script>
  </div>
</header>
<div class="ochre"></div>
<main id="main"><div class="wrap">"""


def footer(root, t):
    """The site is read by staff, not by whoever maintains the build.

    An earlier version explained the YAML layout here, which is useful to
    nobody who arrived to copy their signature.
    """
    return f"""</div></main>
<footer class="site"><div class="wrap">
  <p>{H.escape(t("chrome.footer_q"))}
     <a href="{root}help/">{H.escape(t("chrome.footer_link"))}</a>
     {H.escape(t("chrome.footer_rest"))}</p>
</div></footer>
</body></html>"""


def initials(name):
    parts = [p for p in name.split() if p]
    return (parts[0][:1] + (parts[-1][:1] if len(parts) > 1 else "")).upper()


def build_404(company, base, t):
    """Served by Pages for any missing path.

    Links are absolute, not relative: this one file answers /nope/ and
    /people/nobody/ alike, and a relative href would resolve differently for
    each. The likeliest visitor is someone whose id changed or who was
    offboarded, so it leads with the directory rather than an apology.
    """
    logo = asset_url(base, f"assets/shared/logo-{LOGO}-2x.png",
                     shared_asset(f"logo-{LOGO}-2x.png"))
    return (head(t("notfound.title", company=company["name"]),
                 t("notfound.desc"), base, base, company, t)
            + site_header(company, logo, base, t.esc("notfound.subtitle"),
                          t("notfound.h1"), t)
            + f"""
  <div class="card route">
    <h3>{t.esc("notfound.try_h")}</h3>
    <ul>
      <li><a href="{base}">{t.esc("notfound.try_all")}</a>
          {t.esc("notfound.try_all_rest")}</li>
      <li><a href="{base}help/">{t.esc("notfound.try_help")}</a>
          {t.esc("notfound.try_help_rest")}</li>
    </ul>
  </div>"""
            + footer(base, t))


def build_help(company, base, t, alt=None):
    """The page for someone who has no signature yet, or whose details moved.

    Written for whoever arrives without knowing what a pull request is. The
    engineering route is here too, but second - leading with it turns a
    two-minute request into a tutorial.
    """
    logo = asset_url(base, f"assets/shared/logo-{LOGO}-2x.png",
                     shared_asset(f"logo-{LOGO}-2x.png"))
    # repo is scheme-checked in load_company; escaped here so a query string
    # or an ampersand cannot end an attribute early.
    repo = H.escape((company.get("repo") or "").rstrip("/"), quote=True)
    new_url = f"{repo}/issues/new?template=new-signature.yml" if repo else ""
    upd_url = f"{repo}/issues/new?template=update-signature.yml" if repo else ""
    contrib = f"{repo}/blob/main/CONTRIBUTING.md" if repo else ""

    ask = f"""
      <a class="cta" href="{new_url}">{t.esc("help.ask_cta_new")}</a>
      <a class="cta ghost" href="{upd_url}">{t.esc("help.ask_cta_update")}</a>""" \
        if repo else f"""
      <p class="note">{t("help.ask_no_repo")}</p>"""

    def li(key):
        return f"<li>{t(key)}</li>"

    def faq(q, a):
        return (f"<details><summary>{t.esc(q)}</summary>"
                f"<p>{t(a)}</p></details>")

    body = f"""
  <p class="lede">{t("help.lede", company=H.escape(company["name"]))}</p>

  <div class="card route">
    <h3>{t.esc("help.ask_h")}</h3>
    <p class="who">{t.esc("help.ask_who")}</p>
    <ol>{"".join(li(f"help.ask_{i}") for i in (1, 2, 3, 4))}</ol>
    {ask}
  </div>

  <div class="card route">
    <h3>{t.esc("help.self_h")}</h3>
    <p class="who">{t("help.self_who")}</p>
    <ol>{"".join(li(f"help.self_{i}") for i in (1, 2, 3))}</ol>
    {f'<a class="cta ghost" href="{contrib}">{t.esc("help.self_cta")}</a>' if repo else ""}
  </div>

  <div class="card route">
    <h3>{t.esc("help.next_h")}</h3>
    <p class="who">{t.esc("help.next_who")}</p>
    <ul>{"".join(li(f"help.next_{i}") for i in (1, 2, 3, 4, 5))}</ul>
    <p class="note">{t.esc("help.next_note")}</p>
  </div>

  <div class="card faq">
    {"".join(faq(f"help.faq_{k}_q", f"help.faq_{k}_a") for k in
             ("public", "phone", "photo", "accents", "images", "outlook",
              "stale"))}
  </div>"""

    n = company["name"]
    return (head(t("help.title", company=n), t("help.desc", company=n),
                 base, base + "help/", company, t)
            + site_header(company, logo, "../", t.esc("help.subtitle"),
                          t("help.h1"), t, alt, here="help")
            + body + footer("../", t))


def build_index(company, people, base, t, alt=None, people_root="people/"):
    """`people_root` exists because person pages are built once, in the
    default locale, at /people/. A translated index sits one directory deeper,
    so a bare "people/<id>/" from there points at a directory that does not
    exist. This is the only cross-locale link in the site."""
    logo = asset_url(base, f"assets/shared/logo-{LOGO}-2x.png",
                     shared_asset(f"logo-{LOGO}-2x.png"))
    cards = []
    for r in people:
        if r.get("avatar_path"):
            av = asset_url(base, f"assets/people/{r['id']}/avatar-{AVATAR}-2x.png",
                           person_asset(r["id"], f"avatar-{AVATAR}-2x.png"))
            thumb = f'<img src="{av}" alt=""/>'
        else:
            thumb = f'<div class="ph">{H.escape(initials(r["name"]))}</div>'
        cards.append(
            f'<a class="card person" href="{people_root}{r["id"]}/" '
            f'data-search="{H.escape((r["name"] + " " + r["role"] + " " + r["email"]).lower())}">'
            f'{thumb}<div><div class="n">{H.escape(r["name"])}</div>'
            f'<div class="r">{H.escape(r["role"])}</div></div>'
            f'<div class="go">&rarr;</div></a>')

    n = len(people)
    steps = "".join(f"<li>{t(f'index.step_{i}')}</li>" for i in range(1, 6))
    # The count is rebuilt live by the script below, so both forms cross into
    # JavaScript as JSON. Vietnamese has no plural form and simply repeats the
    # same string - which is exactly why the choice belongs in the locale file
    # and not in an `n == 1` in the template.
    one_j = json.dumps(t("index.count_one", n="\x00"))
    many_j = json.dumps(t("index.count_many", n="\x00"))
    body = f"""
  <div class="card steps">
    <h2>{t.esc("index.steps_h")}</h2>
    <ol>{steps}</ol>
  </div>

  <div class="toolbar">
    <label class="vh" for="q">{t.esc("index.search_label")}</label>
    <input class="search" id="q" type="search"
           placeholder="{t.esc("index.search_placeholder")}" autocomplete="off"/>
    <span class="count" id="count">{
      t.esc("index.count_one" if n == 1 else "index.count_many", n=n)}</span>
  </div>

  <div class="people" id="people">{''.join(cards)}</div>
  <div class="empty card" id="empty" style="display:none;">
    {t.esc("index.empty_pre")} <a href="help/">{t.esc("index.empty_link")}</a>
  </div>
  <p class="note" style="margin-top:22px;">{t.esc("index.note")}
     <a href="help/">{t.esc("index.note_link")}</a>.</p>

<script>
(function () {{
  var ONE = {one_j}, MANY = {many_j};
  var q = document.getElementById('q'), list = document.getElementById('people'),
      empty = document.getElementById('empty'), count = document.getElementById('count'),
      cards = Array.prototype.slice.call(list.querySelectorAll('.person'));
  function apply() {{
    var t = q.value.trim().toLowerCase(), shown = 0;
    cards.forEach(function (c) {{
      var hit = !t || c.getAttribute('data-search').indexOf(t) > -1;
      c.style.display = hit ? '' : 'none'; if (hit) shown++;
    }});
    count.textContent = (shown === 1 ? ONE : MANY).replace('\\x00', shown);
    empty.style.display = shown ? 'none' : '';
  }}
  q.addEventListener('input', apply);
}})();
</script>"""

    nm = company["name"]
    return (head(t("index.title", company=nm), t("index.desc", company=nm),
                 base, base, company, t)
            + site_header(company, logo, "./", t.esc("index.subtitle"),
                          t("index.h1"), t, alt, here="index")
            + body + footer("./", t))


def build_person(company, rec, base, sigs, t):
    """`sigs` is {style_id: markup} for every style, because the picker lets
    people compare before they commit. Each one is parked in a hidden
    textarea rather than a div: .value returns the exact bytes the generator
    wrote, including the mso conditional comments, where innerHTML would hand
    back whatever the DOM chose to serialise."""
    logo = asset_url(base, f"assets/shared/logo-{LOGO}-2x.png",
                     shared_asset(f"logo-{LOGO}-2x.png"))
    chosen = rec.get("style") or DEFAULT_STYLE
    sig = sigs[chosen]
    esc = H.escape(sig)
    picker = "".join(
        f'<button class="stylebtn" type="button" data-style="{sid}" '
        f'aria-pressed="{"true" if sid == chosen else "false"}">'
        f'<span class="sname">{H.escape(label)}</span>'
        f'<span class="snote">{H.escape(note)}</span></button>'
        for sid, label, note, _ in STYLES if sid in sigs)
    sources = "".join(
        f'<textarea id="src-{sid}" hidden readonly>{H.escape(m)}</textarea>'
        for sid, m in sigs.items())
    return (head(f"{rec['name']} - email signature",
                 f"Install {rec['name']}'s {company['name']} email signature: "
                 f"verify the images, copy, paste into Gmail.",
                 base, f"{base}people/{rec['id']}/", company, t)
            + site_header(company, logo, "../../",
                          "Verify the images, copy, then paste into Gmail.",
                          "Your email signature", t, here="index")
            + f"""
  <p class="crumb"><a href="../../">&larr; All signatures</a>
     &nbsp;&middot;&nbsp; <a href="../../help/">Something here is wrong</a></p>
  <h2 class="person-name">{H.escape(rec['name'])}</h2>
  <p class="person-role">{H.escape(rec['role'])} - {H.escape(company['name'])}</p>

  <div class="sec" style="margin-top:26px;">Pick a style</div>
  <div class="styles" id="styles">{picker}</div>
  <p class="sub" style="margin:0 0 20px;">Every style carries the same
     details. Pick one, check it below, then copy. To make it stick, put
     <code>style: <span id="stylehint">{chosen}</span></code> in your record - otherwise the page opens on
     whichever you chose last time.</p>

  <div class="bar">
    <button class="btn" id="copy">Verify &amp; copy</button>
    <span class="status" id="status">Not verified</span>
  </div>

  <div class="grid">
    <div class="col desk">
      <div class="colhead">Desktop <span class="dim" id="d-desktop"></span></div>
      <div class="surface desk"><div id="s-desktop">{sig}</div></div>
    </div>
    <div class="col narrow">
      <div class="colhead">Phone, 320px <span class="dim" id="d-narrow"></span></div>
      <div class="surface w320"><div id="s-narrow">{sig}</div></div>
    </div>
  </div>

  <div class="sec">Dark mode</div>
  <div class="grid dark3">
    <div class="col"><div class="sub">Light</div>
      <div class="surface"><div id="s-l">{sig}</div></div></div>
    <div class="col"><div class="sub">Dark</div>
      <div class="surface dark"><div id="s-d">{sig}</div></div></div>
    <div class="col"><div class="sub">Forced inversion</div>
      <div class="surface inv"><div id="s-i">{sig}</div></div></div>
  </div>

  <div class="card steps" style="margin-top:34px;">
    <h2>Paste it into Gmail</h2>
    <ol>
      <li>Press <strong>Verify &amp; copy</strong> above.</li>
      <li>Gmail &rarr; <strong>Settings</strong> (gear, top right) &rarr;
          <strong>See all settings</strong> &rarr; <strong>General</strong>.</li>
      <li>Scroll to <strong>Signature</strong>. Create one if you have none.</li>
      <li>Click into the box and paste with <strong>Cmd/Ctrl+V</strong>.</li>
      <li>Set it as your default for new mail and replies if you want it everywhere.</li>
      <li><strong>Save changes</strong> at the very bottom - it is easy to miss.</li>
    </ol>
  </div>

  <details>
    <summary>Raw HTML (<span id="rawn">{len(sig)}</span> chars) - if the
       button is blocked by your browser</summary>
    <textarea readonly spellcheck="false" id="raw">{esc}</textarea>
  </details>
  <div class="vh" aria-hidden="true">{sources}</div>

<script>
(function () {{
  function checkImage(url) {{
    return new Promise(function (res) {{
      var i = new Image(), done = false;
      function fin(ok) {{ if (!done) {{ done = true; res({{url: url, ok: ok}}); }} }}
      i.onload = function () {{ fin(i.naturalWidth > 0); }};
      i.onerror = function () {{ fin(false); }};
      setTimeout(function () {{ fin(false); }}, 8000);
      i.src = url + (url.indexOf('?') > -1 ? '&' : '?') + 'cb=' + Date.now();
    }});
  }}
  var RAW = document.getElementById('raw').value, URLS = [];
  function urlsIn(markup) {{
    return [].map.call(
      new DOMParser().parseFromString(markup, 'text/html').querySelectorAll('img'),
      function (n) {{ return n.getAttribute('src'); }});
  }}

  // Verification runs on load, NOT on click.
  //
  // clipboard.write() is only permitted while the click's user activation is
  // still live. Awaiting up to eight seconds of image checks first outlives
  // that window, and WebKit enforces it strictly - the copy would fail in
  // Safari and every iOS browser while appearing fine in Chrome. Checking
  // early means the click almost always has its answer already and can write
  // synchronously, which every engine accepts.
  var state = 'pending', reason = null, checked = null;

  // Re-run per style, because the styles do not share an image set - two of
  // them carry no photo at all, so a result verified against one is not an
  // answer about another.
  function verify() {{
    URLS = urlsIn(RAW);
    state = 'pending'; reason = null;
    var mine = checked = Promise.all(URLS.map(checkImage)).then(function (r) {{
      var bad = r.filter(function (x) {{ return !x.ok; }});
      if (bad.length) {{
        console.warn('Unreachable:', bad.map(function (b) {{ return b.url; }}));
        throw new Error(bad.length + ' of ' + r.length +
          ' images unreachable - not copied. Tell whoever manages the repo.');
      }}
      return true;
    }});
    mine.then(function () {{ if (mine === checked) state = 'ok'; }},
              function (e) {{ if (mine === checked) {{ state = 'bad'; reason = e; }} }});
  }}
  verify();

  function blob(type) {{ return new Blob([RAW], {{type: type}}); }}

  function selectionCopy() {{
    var h = document.getElementById('s-desktop');
    var s = window.getSelection(), r = document.createRange();
    r.selectNodeContents(h); s.removeAllRanges(); s.addRange(r);
    var ok = document.execCommand('copy'); s.removeAllRanges();
    if (!ok) throw new Error('execCommand refused');
  }}

  function run() {{
    var btn = document.getElementById('copy'), st = document.getElementById('status');
    if (state === 'bad') {{
      st.className = 'status err'; st.textContent = reason.message; return;
    }}
    btn.disabled = true; st.className = 'status'; st.textContent = 'Copying...';

    var write;
    try {{
      if (navigator.clipboard && window.ClipboardItem) {{
        write = navigator.clipboard.write([new ClipboardItem(
          state === 'ok'
            // Settled: hand over real Blobs, synchronously inside the gesture.
            ? {{'text/html': blob('text/html'), 'text/plain': blob('text/plain')}}
            // Still checking: ClipboardItem accepts promises, so write() is
            // still called inside the gesture and the data arrives later.
            : {{'text/html':  checked.then(function () {{ return blob('text/html'); }}),
               'text/plain': checked.then(function () {{ return blob('text/plain'); }})}}
        )]);
      }} else {{
        write = checked.then(selectionCopy);
      }}
    }} catch (e) {{ write = Promise.reject(e); }}

    write.then(function () {{
      st.className = 'status ok';
      st.textContent = 'All ' + URLS.length + ' images OK - copied. Paste into Gmail.';
    }}, function (e) {{
      st.className = 'status err';
      st.textContent = (e && /unreachable/.test(e.message || ''))
        ? e.message
        : 'Your browser blocked the clipboard - copy from the Raw HTML box below.';
      console.error(e);
    }}).then(function () {{ btn.disabled = false; }});
  }}
  document.getElementById('copy').addEventListener('click', run);

  function measure() {{
    [['s-desktop','d-desktop', {TABLE_W}], ['s-narrow','d-narrow', 0]].forEach(function (p) {{
      var el = document.getElementById(p[0]), out = document.getElementById(p[1]);
      if (!el || !out) return;
      var t = el.querySelector('table'), r = t ? t.getBoundingClientRect() : null;
      var host = el.parentElement, over = host.scrollWidth - host.clientWidth;
      // Reading this page on a phone squeezes the desktop preview, so the
      // number stops describing desktop. Saying so beats printing a width
      // that looks like a measurement of the signature.
      var squeezed = p[2] && host.clientWidth < p[2];
      if (squeezed) {{
        out.textContent = 'narrowed by this screen - open on a computer to see it';
        out.className = 'dim';
        return;
      }}
      out.textContent = (r ? Math.ceil(r.width) + ' x ' + Math.ceil(r.height) : '')
                        + (over > 1 ? '  overflow ' + over + 'px' : '');
      out.className = 'dim ' + (over > 1 ? 'bad' : 'good');
    }});
  }}
  window.addEventListener('load', measure);
  window.addEventListener('resize', measure);

  // Switching style rewrites every preview surface, the raw box, and what
  // the copy button will hand over - from one source of truth, so the thing
  // you looked at is the thing you paste.
  var SURFACES = ['s-desktop', 's-narrow', 's-l', 's-d', 's-i'];
  var KEY = 'sig-style:{rec["id"]}';

  function select(sid, remember) {{
    var src = document.getElementById('src-' + sid);
    if (!src) return;
    RAW = src.value;
    SURFACES.forEach(function (id) {{
      var el = document.getElementById(id);
      if (el) el.innerHTML = RAW;
    }});
    var raw = document.getElementById('raw');
    raw.value = RAW;
    document.getElementById('rawn').textContent = RAW.length;
    var hint = document.getElementById('stylehint');
    if (hint) hint.textContent = sid;
    [].forEach.call(document.querySelectorAll('.stylebtn'), function (b) {{
      b.setAttribute('aria-pressed',
        b.getAttribute('data-style') === sid ? 'true' : 'false');
    }});
    var st = document.getElementById('status');
    st.className = 'status'; st.textContent = 'Not verified';
    verify();
    measure();
    if (remember) {{ try {{ localStorage.setItem(KEY, sid); }} catch (e) {{}} }}
  }}

  [].forEach.call(document.querySelectorAll('.stylebtn'), function (b) {{
    b.addEventListener('click', function () {{
      select(b.getAttribute('data-style'), true);
    }});
  }});

  // Reopen on whatever they chose last time. The record's `style:` still
  // decides what the page ships with, and what everyone else sees.
  try {{
    var saved = localStorage.getItem(KEY);
    if (saved && document.getElementById('src-' + saved)) select(saved, false);
  }} catch (e) {{}}
}})();
</script>""" + footer("../../", t))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=None)
    args = ap.parse_args()

    company = load_company()
    base = args.base or company["base_url"]
    if not base.endswith("/"):
        base += "/"
    people = load_people(company)

    locales = load_locales()
    en = T(DEFAULT_LOCALE, locales[DEFAULT_LOCALE])
    others = [c for c in sorted(locales) if c != DEFAULT_LOCALE]

    def site_dir(code):
        return DOCS if code == DEFAULT_LOCALE else os.path.join(DOCS, code)

    def site_url(code):
        return base if code == DEFAULT_LOCALE else f"{base}{code}/"

    # With exactly two languages the switch is unambiguous. A third would
    # need a menu rather than a link, and this is the line that would tell
    # you - it fails loudly instead of silently linking to the wrong one.
    if len(others) > 1:
        raise SystemExit(
            f"{len(locales)} locales found ({', '.join(sorted(locales))}). "
            f"The header switch is a single link and can only offer one "
            f"alternative - it needs to become a menu first.")

    for code in [DEFAULT_LOCALE] + others:
        t = T(code, locales[code])
        d = site_dir(code)
        os.makedirs(d, exist_ok=True)

        # The link points at the same page in the other language, not at that
        # language's home page - being thrown back to the front page is how
        # people give up on a language switch.
        alt = None
        if others:
            oc = others[0] if code == DEFAULT_LOCALE else DEFAULT_LOCALE
            ot = T(oc, locales[oc])
            here = f"{oc}/" if code == DEFAULT_LOCALE else "../"
            alt = (here, ot("meta.name"), ot("meta.html_lang"))

        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
            fh.write(build_index(
                company, people, site_url(code), t, alt,
                "people/" if code == DEFAULT_LOCALE else "../people/"))

        helpdir = os.path.join(d, "help")
        os.makedirs(helpdir, exist_ok=True)
        alt_help = None
        if alt:
            oc = others[0] if code == DEFAULT_LOCALE else DEFAULT_LOCALE
            ot = T(oc, locales[oc])
            href = f"../{oc}/help/" if code == DEFAULT_LOCALE else "../../help/"
            alt_help = (href, ot("meta.name"), ot("meta.html_lang"))
        with open(os.path.join(helpdir, "index.html"), "w",
                  encoding="utf-8") as fh:
            fh.write(build_help(company, site_url(code), t, alt_help))
        rel = os.path.relpath(helpdir, DOCS)
        print(f"  docs/{rel}/index.html ({code})")

    # Pages serves exactly one 404, from the root, whatever path was asked
    # for. There is no way to pick a language for it, so it is English.
    with open(os.path.join(DOCS, "404.html"), "w", encoding="utf-8") as fh:
        fh.write(build_404(company, base, en))

    # robots.txt and the meta robots tag say the same thing, because they do
    # different jobs: robots.txt asks crawlers not to fetch, the meta tag asks
    # them not to list. Neither protects the images, which have to stay
    # publicly fetchable for mail clients to load them.
    indexed = bool(company.get("index_site"))
    with open(os.path.join(DOCS, "robots.txt"), "w", encoding="utf-8") as fh:
        if indexed:
            fh.write(f"User-agent: *\nAllow: /\nSitemap: {base}sitemap.xml\n")
        else:
            fh.write("User-agent: *\nDisallow: /\n")
    print(f"  docs/robots.txt ({'indexed' if indexed else 'noindex'})")

    if indexed:
        urls = ([base, base + "help/"]
                + [f"{base}{c}/" for c in others]
                + [f"{base}{c}/help/" for c in others]
                + [f"{base}people/{r['id']}/" for r in people])
        entries = "".join(f"<url><loc>{H.escape(u)}</loc></url>" for u in urls)
        with open(os.path.join(DOCS, "sitemap.xml"), "w",
                  encoding="utf-8") as fh:
            fh.write('<?xml version="1.0" encoding="UTF-8"?>'
                     '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                     f'{entries}</urlset>\n')
        print(f"  docs/sitemap.xml ({len(urls)} urls)")

    # GitHub Pages runs Jekyll by default, which ignores files and folders
    # beginning with an underscore. .nojekyll turns that off so nothing is
    # silently dropped from the published site.
    open(os.path.join(DOCS, ".nojekyll"), "w").close()

    # Regenerate docs/CNAME so the custom domain survives any rebuild. GitHub
    # writes this file when the domain is first saved in Settings, but relying
    # on that one commit means a clean rebuild, a bad merge, or a force-push
    # can detach the domain without anyone noticing.
    domain = company.get("custom_domain")
    cname = os.path.join(DOCS, "CNAME")
    if domain:
        with open(cname, "w", encoding="utf-8") as fh:
            fh.write(domain + "\n")
        print(f"  docs/CNAME -> {domain}")
    elif os.path.isfile(cname):
        os.remove(cname)
        print("  docs/CNAME removed (no custom_domain set)")

    for rec in people:
        d = os.path.join(DOCS_PEOPLE, rec["id"])
        os.makedirs(d, exist_ok=True)
        # Every style the generator produced, so the page can offer all of
        # them. Missing files are a build ordering bug, not something to
        # paper over - generate.py runs first and writes all ten.
        sigs = {}
        for sid, _l, _n, _f in STYLES:
            fp = os.path.join(d, f"sig-{sid}.html")
            if not os.path.isfile(fp):
                raise SystemExit(
                    f"{fp} is missing - run build/generate.py before "
                    f"build/make_site.py")
            with open(fp, encoding="utf-8") as fh:
                sigs[sid] = fh.read()
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
            fh.write(build_person(company, rec, base, sigs, en))
        print(f"  docs/people/{rec['id']}/index.html")

    print(f"site -> docs/index.html + {len(people)} person page(s)")


if __name__ == "__main__":
    main()
