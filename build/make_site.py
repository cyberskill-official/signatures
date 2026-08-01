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
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import (AVATAR, DOCS, DOCS_PEOPLE, LOGO, OCHRE, UMBER, asset_url,
                   load_company, load_people, person_asset, shared_asset)

CSS = """
  :root{--umber:#45210E;--ochre:#F4BA17;--accent:#9E5E3E;--ink:#22201E;
        --muted:#6B6B6B;--line:#E6E0D8;--bg:#FBF9F7;--card:#FFFFFF;}
  *{box-sizing:border-box;}
  body{margin:0;background:var(--bg);color:var(--ink);
       font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
       -webkit-font-smoothing:antialiased;}
  a{color:var(--umber);}
  .wrap{max-width:1080px;margin:0 auto;padding:0 24px;}
  header.site{background:var(--umber);color:#fff;padding:34px 0 30px;}
  header.site a{color:#fff;text-decoration:none;}
  .brandrow{display:flex;align-items:center;gap:14px;}
  .brandrow img{width:40px;height:40px;display:block;border-radius:8px;}
  .brandname{font-size:15px;font-weight:700;letter-spacing:.14em;
             text-transform:uppercase;}
  header.site h1{margin:18px 0 6px;font-size:30px;letter-spacing:-.4px;}
  header.site p{margin:0;color:#E8D9CD;max-width:62ch;}
  .ochre{height:4px;background:var(--ochre);}
  main{padding:38px 0 80px;}
  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;}
  .steps{padding:20px 24px;margin:0 0 34px;}
  .steps h2{margin:0 0 10px;font-size:12px;letter-spacing:.09em;
            text-transform:uppercase;color:var(--muted);}
  .steps ol{margin:0;padding-left:20px;} .steps li{margin:5px 0;}
  code{background:#F1ECE6;padding:1px 6px;border-radius:4px;font-size:.9em;}
  .toolbar{display:flex;gap:12px;align-items:center;margin:0 0 18px;
           flex-wrap:wrap;}
  .search{flex:1 1 260px;padding:11px 14px;border:1px solid var(--line);
          border-radius:9px;font-size:14px;background:#fff;}
  .count{font-size:13px;color:var(--muted);}
  .people{display:grid;gap:16px;
          grid-template-columns:repeat(auto-fill,minmax(280px,1fr));}
  .person{display:flex;gap:14px;align-items:center;padding:16px;
          text-decoration:none;color:inherit;transition:.15s;}
  .person:hover{border-color:var(--accent);
                box-shadow:0 2px 14px rgba(69,33,14,.09);transform:translateY(-1px);}
  .person img{width:56px;height:56px;display:block;flex:0 0 56px;}
  .ph{width:56px;height:56px;flex:0 0 56px;border-radius:50%;
      background:var(--umber);color:var(--ochre);display:flex;
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
  h1.person-name{margin:0 0 2px;font-size:27px;letter-spacing:-.3px;}
  .person-role{margin:0 0 22px;color:var(--muted);}
  .bar{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin:0 0 20px;}
  .btn{background:var(--umber);color:#fff;border:0;border-radius:8px;
       padding:12px 22px;font-size:14px;font-weight:600;cursor:pointer;}
  .btn:hover{background:#5C2D14;} .btn[disabled]{opacity:.5;cursor:progress;}
  .status{font-size:13px;color:var(--muted);}
  .status.ok{color:#1B7F3B;font-weight:600;}
  .status.err{color:#B3261E;font-weight:600;}
  .grid{display:flex;gap:20px;align-items:flex-start;flex-wrap:wrap;}
  .col{min-width:0;} .col.narrow{flex:0 0 auto;} .col.desk{flex:0 1 556px;}
  .colhead{font-size:11px;letter-spacing:.09em;text-transform:uppercase;
           color:var(--muted);margin:0 0 7px;}
  .dim{text-transform:none;letter-spacing:0;font-weight:700;}
  .dim.good{color:#1B7F3B;} .dim.bad{color:#B3261E;}
  .surface{border:1px solid var(--line);border-radius:9px;padding:18px;
           overflow-x:auto;background:#fff;}
  /* The signature is fluid (width:100% capped at 520px), so a shrink-to-fit
     flex column collapses it to min-content and the "desktop" preview stops
     being a desktop preview. Pin the desktop surface wide enough for the
     table to reach its full 520px. */
  .surface.desk{width:556px;max-width:100%;}
  .surface.w320{width:320px;flex:0 0 320px;}
  .surface.dark{background:#1F1F1F;border-color:#3A3A3A;color:#E8E8E8;}
  .surface.inv{background:#fff;filter:invert(1) hue-rotate(180deg);}
  .surface.inv img{filter:invert(1) hue-rotate(180deg);}
  .sub{font-size:12px;color:var(--muted);margin:0 0 7px;}
  .dark3 .col{flex:1 1 320px;min-width:300px;}
  details{margin-top:20px;} summary{cursor:pointer;font-size:13px;color:var(--muted);}
  textarea{width:100%;height:150px;margin-top:10px;padding:12px;
           font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;
           border:1px solid var(--line);border-radius:8px;background:#FAF8F6;}
  .sec{margin:34px 0 12px;font-size:12px;letter-spacing:.09em;
       text-transform:uppercase;color:var(--muted);}
"""


def head(title, css_extra=""):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta name="color-scheme" content="light"/>
<title>{H.escape(title)}</title>
<style>{CSS}{css_extra}</style>
</head>
<body>"""


def site_header(company, logo_url, root, subtitle, h1):
    return f"""
<header class="site">
  <div class="wrap">
    <a class="brandrow" href="{root}">
      <img src="{logo_url}" alt=""/>
      <span class="brandname">{H.escape(company['name'])}</span>
    </a>
    <h1>{H.escape(h1)}</h1>
    <p>{subtitle}</p>
  </div>
</header>
<div class="ochre"></div>
<main><div class="wrap">"""


FOOTER = """</div></main>
<footer class="site"><div class="wrap">
  <p>Generated from <code>src/people/</code>. To add someone, drop a YAML
     record and a photo in <code>src/</code> and run <code>./install.sh</code>.
     Nothing in <code>docs/</code> is edited by hand.</p>
</div></footer>
</body></html>"""


def initials(name):
    parts = [p for p in name.split() if p]
    return (parts[0][:1] + (parts[-1][:1] if len(parts) > 1 else "")).upper()


def build_index(company, people, base):
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
            f'<a class="card person" href="people/{r["id"]}/" '
            f'data-search="{H.escape((r["name"] + " " + r["role"] + " " + r["email"]).lower())}">'
            f'{thumb}<div><div class="n">{H.escape(r["name"])}</div>'
            f'<div class="r">{H.escape(r["role"])}</div></div>'
            f'<div class="go">&rarr;</div></a>')

    n = len(people)
    body = f"""
  <div class="card steps">
    <h2>How to install yours</h2>
    <ol>
      <li>Find yourself below and open your page.</li>
      <li>Press <strong>Verify &amp; copy</strong>. It checks every image URL
          first and refuses to copy if any is unreachable.</li>
      <li>In Gmail: <strong>Settings &rarr; See all settings &rarr; General
          &rarr; Signature</strong>.</li>
      <li>Paste with <strong>Cmd/Ctrl+V</strong>, then
          <strong>Save changes</strong> at the very bottom of the page.</li>
      <li>Send yourself a test and read it on your phone as well as your laptop.</li>
    </ol>
  </div>

  <div class="toolbar">
    <input class="search" id="q" type="search"
           placeholder="Search by name, role or email" autocomplete="off"/>
    <span class="count" id="count">{n} {'person' if n == 1 else 'people'}</span>
  </div>

  <div class="people" id="people">{''.join(cards)}</div>
  <div class="empty card" id="empty" style="display:none;">No match.</div>

<script>
(function () {{
  var q = document.getElementById('q'), list = document.getElementById('people'),
      empty = document.getElementById('empty'), count = document.getElementById('count'),
      cards = Array.prototype.slice.call(list.querySelectorAll('.person'));
  function apply() {{
    var t = q.value.trim().toLowerCase(), shown = 0;
    cards.forEach(function (c) {{
      var hit = !t || c.getAttribute('data-search').indexOf(t) > -1;
      c.style.display = hit ? '' : 'none'; if (hit) shown++;
    }});
    count.textContent = shown + (shown === 1 ? ' person' : ' people');
    empty.style.display = shown ? 'none' : '';
  }}
  q.addEventListener('input', apply);
}})();
</script>"""

    return (head(f"Email signatures - {company['name']}")
            + site_header(company, logo, "./",
                          "Pick your name, verify, copy, paste into Gmail. "
                          "One button, about a minute.", "Email signatures")
            + body + FOOTER)


def build_person(company, rec, base, sig):
    logo = asset_url(base, f"assets/shared/logo-{LOGO}-2x.png",
                     shared_asset(f"logo-{LOGO}-2x.png"))
    esc = H.escape(sig)
    return (head(f"{rec['name']} - email signature")
            + site_header(company, logo, "../../",
                          "Verify the images, copy, then paste into Gmail.",
                          "Your email signature")
            + f"""
  <p class="crumb"><a href="../../">&larr; All signatures</a></p>
  <h1 class="person-name">{H.escape(rec['name'])}</h1>
  <p class="person-role">{H.escape(rec['role'])} - {H.escape(company['name'])}</p>

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
      <div class="surface">{sig}</div></div>
    <div class="col"><div class="sub">Dark</div>
      <div class="surface dark">{sig}</div></div>
    <div class="col"><div class="sub">Forced inversion</div>
      <div class="surface inv">{sig}</div></div>
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
    <summary>Raw HTML ({len(sig)} chars) - if the button is blocked by your browser</summary>
    <textarea readonly spellcheck="false" id="raw">{esc}</textarea>
  </details>

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
  async function run() {{
    var btn = document.getElementById('copy'), st = document.getElementById('status'),
        raw = document.getElementById('raw').value;
    btn.disabled = true; st.className = 'status'; st.textContent = 'Checking images...';
    var doc = new DOMParser().parseFromString(raw, 'text/html');
    var urls = [].map.call(doc.querySelectorAll('img'),
                           function (n) {{ return n.getAttribute('src'); }});
    var bad = (await Promise.all(urls.map(checkImage))).filter(function (r) {{ return !r.ok; }});
    if (bad.length) {{
      st.className = 'status err';
      st.textContent = bad.length + ' of ' + urls.length +
        ' images unreachable - not copied. Tell whoever manages the repo.';
      console.warn('Unreachable:', bad.map(function (b) {{ return b.url; }}));
      btn.disabled = false; return;
    }}
    try {{
      if (navigator.clipboard && window.ClipboardItem) {{
        await navigator.clipboard.write([new ClipboardItem({{
          'text/html': new Blob([raw], {{type: 'text/html'}}),
          'text/plain': new Blob([raw], {{type: 'text/plain'}})
        }})]);
      }} else {{
        var h = document.getElementById('s-desktop');
        var s = window.getSelection(), r = document.createRange();
        r.selectNodeContents(h); s.removeAllRanges(); s.addRange(r);
        document.execCommand('copy'); s.removeAllRanges();
      }}
      st.className = 'status ok';
      st.textContent = 'All ' + urls.length + ' images OK - copied. Paste into Gmail.';
    }} catch (e) {{
      st.className = 'status err';
      st.textContent = 'Your browser blocked the clipboard - copy from the Raw HTML box below.';
      console.error(e);
    }}
    btn.disabled = false;
  }}
  document.getElementById('copy').addEventListener('click', run);

  function measure() {{
    [['s-desktop','d-desktop'], ['s-narrow','d-narrow']].forEach(function (p) {{
      var el = document.getElementById(p[0]), out = document.getElementById(p[1]);
      if (!el || !out) return;
      var t = el.querySelector('table'), r = t ? t.getBoundingClientRect() : null;
      var host = el.parentElement, over = host.scrollWidth - host.clientWidth;
      out.textContent = (r ? Math.ceil(r.width) + ' x ' + Math.ceil(r.height) : '')
                        + (over > 1 ? '  overflow ' + over + 'px' : '');
      out.className = 'dim ' + (over > 1 ? 'bad' : 'good');
    }});
  }}
  window.addEventListener('load', measure);
  window.addEventListener('resize', measure);
}})();
</script>""" + FOOTER)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=None)
    args = ap.parse_args()

    company = load_company()
    base = args.base or company["base_url"]
    if not base.endswith("/"):
        base += "/"
    people = load_people(company)

    os.makedirs(DOCS, exist_ok=True)
    with open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(build_index(company, people, base))

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
        with open(os.path.join(d, "signature.html"), encoding="utf-8") as fh:
            sig = fh.read()
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
            fh.write(build_person(company, rec, base, sig))
        print(f"  docs/people/{rec['id']}/index.html")

    print(f"site -> docs/index.html + {len(people)} person page(s)")


if __name__ == "__main__":
    main()
