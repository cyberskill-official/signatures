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
from model import (AVATAR, DOCS, DOCS_PEOPLE, LOGO, OCHRE, TABLE_W, UMBER,
                   asset_url, load_company, load_people, person_asset,
                   shared_asset)

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
  .cta{display:inline-block;background:var(--umber);color:#fff;border-radius:8px;
       padding:11px 20px;font-size:14px;font-weight:600;text-decoration:none;
       margin-top:14px;}
  .cta:hover{background:#5C2D14;color:#fff;}
  .cta.ghost{background:transparent;color:var(--umber);
             box-shadow:inset 0 0 0 1.5px var(--line);}
  .cta.ghost:hover{background:#F6F1EB;color:var(--umber);}
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
  h2.person-name{margin:0 0 2px;font-size:27px;letter-spacing:-.3px;}
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
  /* Dark mode for the site chrome only.
     The preview surfaces must NOT follow it - a "Light" preview that goes
     dark stops demonstrating anything, and text inheriting a light colour
     onto a white surface disappears entirely. Both surfaces pin their own
     colour rather than inheriting. */
  @media (prefers-color-scheme: dark){
    :root{--ink:#EDE8E3;--muted:#A5A19D;--line:#3A342E;--bg:#17140F;
          --card:#211C16;}
    a{color:#F0C463;}
    .cta,.btn{background:var(--ochre);color:#3A1B0B;}
    .cta:hover,.btn:hover{background:#FFD166;color:#3A1B0B;}
    .cta.ghost{background:transparent;color:#F0C463;
               box-shadow:inset 0 0 0 1.5px #4A423A;}
    .cta.ghost:hover{background:#2B241C;color:#F0C463;}
    code{background:#2B241C;color:#EDE8E3;}
    .search,textarea{background:#211C16;color:var(--ink);
                     border-color:var(--line);}
    .status.ok,.dim.good{color:#6FD68E;}
    .status.err,.dim.bad{color:#FF9B92;}
    .ph{background:#2B241C;}
    .surface{background:#FFFFFF;color:#22201E;border-color:#D8D2CA;}
    .surface.dark{background:#1F1F1F;color:#E8E8E8;border-color:#3A3A3A;}
    .surface.inv{background:#FFFFFF;color:#22201E;}
  }
  .sec{margin:34px 0 12px;font-size:12px;letter-spacing:.09em;
       text-transform:uppercase;color:var(--muted);}
"""


def head(title, desc, base, canonical, company, lang="en", css_extra=""):
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
    t, d = H.escape(title), H.escape(desc)
    return f"""<!doctype html>
<html lang="{lang}">
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
<meta property="og:title" content="{t}"/>
<meta property="og:description" content="{d}"/>
<meta property="og:url" content="{canonical}"/>
<meta property="og:image" content="{og}"/>
<meta property="og:image:width" content="1200"/>
<meta property="og:image:height" content="630"/>
<meta name="twitter:card" content="summary_large_image"/>
<title>{t}</title>
<style>{CSS}{css_extra}</style>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>"""


def site_header(company, logo_url, root, subtitle, h1, here=""):
    def tab(label, href, key):
        cur = ' aria-current="page"' if key == here else ""
        return f'<a class="tab{" on" if key == here else ""}" href="{href}"{cur}>{label}</a>'
    return f"""
<header class="site">
  <div class="wrap">
    <a class="brandrow" href="{root}">
      <img src="{logo_url}" alt=""/>
      <span class="brandname">{H.escape(company['name'])}</span>
    </a>
    <h1>{H.escape(h1)}</h1>
    <p>{subtitle}</p>
    <nav class="tabs">
      {tab("All signatures", root, "index")}
      {tab("Get one or change yours", root + "help/", "help")}
    </nav>
  </div>
</header>
<div class="ochre"></div>
<main id="main"><div class="wrap">"""


def footer(root):
    """The site is read by staff, not by whoever maintains the build.

    An earlier version explained the YAML layout here, which is useful to
    nobody who arrived to copy their signature.
    """
    return f"""</div></main>
<footer class="site"><div class="wrap">
  <p>Something wrong, missing, or out of date?
     <a href="{root}help/">Ask for it to be changed</a> - it usually takes a
     day. Nothing here is edited by hand; every signature is generated, so a
     fix for one person can be a fix for everyone.</p>
</div></footer>
</body></html>"""


def initials(name):
    parts = [p for p in name.split() if p]
    return (parts[0][:1] + (parts[-1][:1] if len(parts) > 1 else "")).upper()


def build_404(company, base):
    """Served by Pages for any missing path.

    Links are absolute, not relative: this one file answers /nope/ and
    /people/nobody/ alike, and a relative href would resolve differently for
    each. The likeliest visitor is someone whose id changed or who was
    offboarded, so it leads with the directory rather than an apology.
    """
    logo = asset_url(base, f"assets/shared/logo-{LOGO}-2x.png",
                     shared_asset(f"logo-{LOGO}-2x.png"))
    return (head(f"Page not found - {company['name']}",
                 "That signature page does not exist.", base, base, company)
            + site_header(company, logo, base,
                          "That page does not exist. It may have moved, or "
                          "the person may no longer be listed.",
                          "Page not found")
            + f"""
  <div class="card route">
    <h3>Try one of these</h3>
    <ul>
      <li><a href="{base}">All signatures</a> - find your name in the list.</li>
      <li><a href="{base}help/">Get a signature</a> - if you are not listed
          yet, or your details changed.</li>
    </ul>
  </div>"""
            + footer(base))


def build_help(company, base):
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
      <a class="cta" href="{new_url}">Request a signature</a>
      <a class="cta ghost" href="{upd_url}">Update my details</a>""" if repo else """
      <p class="note">No repository is configured in <code>src/company.yml</code>,
         so the request links are missing. Ask whoever maintains this site.</p>"""

    body = f"""
  <p class="lede">Everyone at {H.escape(company['name'])} can have a signature
     on this site. If yours is not here yet, or something on it has changed,
     here is how to sort it out.</p>

  <div class="card route">
    <h3>Just ask</h3>
    <p class="who">The normal way. You need a GitHub account and nothing else.</p>
    <ol>
      <li>Open one of the forms below.</li>
      <li>Fill in your name, job title and email. Add a phone number if you
          want one on there.</li>
      <li>Drag your photo into the photo box. Anything square-ish works.</li>
      <li>Submit.</li>
    </ol>
    {ask}
  </div>

  <div class="card route">
    <h3>Or do it yourself</h3>
    <p class="who">If you have used GitHub before. All of it happens in the
       browser - nothing to install, nothing to run.</p>
    <ol>
      <li>Copy <code>src/people/_template.yml</code> to
          <code>src/people/your-name.yml</code> and fill it in. That filename
          becomes your web address, so use lowercase letters and hyphens.</li>
      <li>Upload your photo to <code>src/avatars/</code> with a matching
          filename.</li>
      <li>Open a pull request with both changes on one branch.</li>
    </ol>
    {f'<a class="cta ghost" href="{contrib}">Full instructions</a>' if repo else ''}
  </div>

  <div class="card route">
    <h3>What happens next</h3>
    <p class="who">Usually within a day.</p>
    <ul>
      <li>Someone turns your request into a change and checks it.</li>
      <li>Automatic checks confirm it renders correctly on a phone and a
          laptop, in light and dark mode, and that it survives what Gmail
          does to pasted markup.</li>
      <li>Once it is merged the site rebuilds itself and your page appears
          under <strong>All signatures</strong>.</li>
      <li>Open your page, press <strong>Verify &amp; copy</strong>, and paste
          into Gmail.</li>
    </ul>
    <p class="note">Nothing you send can break anyone else's signature, and
       nothing reaches the live site until a person has looked at it.</p>
  </div>

  <div class="card faq">
    <details>
      <summary>What ends up public?</summary>
      <p>Your name, job title, work email, your photo, and the phone number if
         you give one. Your photo is served from a public web address, which
         is how images in email signatures work everywhere - a mail app has to
         be able to fetch it. Use a photo you are happy to have public, and
         leave it out if you would rather not.</p>
    </details>
    <details>
      <summary>I do not want my phone number on it.</summary>
      <p>Leave it out and the row disappears. Nothing else shifts. The same is
         true of the photo, the Vietnamese name line, and the social links.</p>
    </details>
    <details>
      <summary>What sort of photo?</summary>
      <p>A normal head-and-shoulders portrait, square-ish, 512 pixels or
         larger. It gets cropped to a circle automatically. If your photo is
         framed unusually - very wide, or you are off to one side - say so in
         your request and it will be adjusted by hand.</p>
    </details>
    <details>
      <summary>My name has accents. Will they show correctly?</summary>
      <p>Yes. Vietnamese diacritics are checked on every build, in every
         browser engine, and a missing character fails the build rather than
         shipping a blank box.</p>
    </details>
    <details>
      <summary>The images are not showing in my email.</summary>
      <p>Most mail apps block images until you allow them, and some people
         keep them blocked permanently. That is expected. Every line of your
         signature is real text, so nothing is lost and nothing moves - the
         layout is identical either way.</p>
    </details>
    <details>
      <summary>It looks slightly different in Outlook.</summary>
      <p>Outlook for Windows draws email through Microsoft Word, which ignores
         some styling. Links come out in Outlook's own blue instead of
         inheriting the surrounding colour, and the block is about four pixels
         shorter. Both are expected and neither can be prevented from the
         markup.</p>
    </details>
    <details>
      <summary>I pasted it and then my details changed.</summary>
      <p>Request the change, then paste again once your page updates. Gmail
         keeps its own copy of whatever you pasted, so an old signature stays
         old until you replace it.</p>
    </details>
  </div>"""

    return (head(f"Get a signature - {company['name']}",
                 f"How to get an email signature at {company['name']}, or "
                 f"change the details on the one you have. Takes about a day.",
                 base, base + "help/", company)
            + site_header(company, logo, "../",
                          "Do not have one yet, or something changed? "
                          "Start here.",
                          "Get a signature", here="help")
            + body + footer("../"))


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
    <label class="vh" for="q">Search by name, role or email</label>
    <input class="search" id="q" type="search"
           placeholder="Search by name, role or email" autocomplete="off"/>
    <span class="count" id="count">{n} {'person' if n == 1 else 'people'}</span>
  </div>

  <div class="people" id="people">{''.join(cards)}</div>
  <div class="empty card" id="empty" style="display:none;">
    No match. <a href="help/">Not listed yet?</a>
  </div>
  <p class="note" style="margin-top:22px;">Not on this list, or something here
     is out of date? <a href="help/">Ask for it to be added or changed</a>.</p>

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

    return (head(f"Email signatures - {company['name']}",
                 f"Find your name, press one button, paste into Gmail. "
                 f"Official {company['name']} email signatures.",
                 base, base, company)
            + site_header(company, logo, "./",
                          "Pick your name, verify, copy, paste into Gmail. "
                          "One button, about a minute.", "Email signatures",
                          here="index")
            + body + footer("./"))


def build_person(company, rec, base, sig):
    logo = asset_url(base, f"assets/shared/logo-{LOGO}-2x.png",
                     shared_asset(f"logo-{LOGO}-2x.png"))
    esc = H.escape(sig)
    return (head(f"{rec['name']} - email signature",
                 f"Install {rec['name']}'s {company['name']} email signature: "
                 f"verify the images, copy, paste into Gmail.",
                 base, f"{base}people/{rec['id']}/", company)
            + site_header(company, logo, "../../",
                          "Verify the images, copy, then paste into Gmail.",
                          "Your email signature", here="index")
            + f"""
  <p class="crumb"><a href="../../">&larr; All signatures</a>
     &nbsp;&middot;&nbsp; <a href="../../help/">Something here is wrong</a></p>
  <h2 class="person-name">{H.escape(rec['name'])}</h2>
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
  var RAW = document.getElementById('raw').value;
  var URLS = [].map.call(
    new DOMParser().parseFromString(RAW, 'text/html').querySelectorAll('img'),
    function (n) {{ return n.getAttribute('src'); }});

  // Verification runs on load, NOT on click.
  //
  // clipboard.write() is only permitted while the click's user activation is
  // still live. Awaiting up to eight seconds of image checks first outlives
  // that window, and WebKit enforces it strictly - the copy would fail in
  // Safari and every iOS browser while appearing fine in Chrome. Checking
  // early means the click almost always has its answer already and can write
  // synchronously, which every engine accepts.
  var state = 'pending', reason = null;
  var checked = Promise.all(URLS.map(checkImage)).then(function (r) {{
    var bad = r.filter(function (x) {{ return !x.ok; }});
    if (bad.length) {{
      console.warn('Unreachable:', bad.map(function (b) {{ return b.url; }}));
      throw new Error(bad.length + ' of ' + r.length +
        ' images unreachable - not copied. Tell whoever manages the repo.');
    }}
    return true;
  }});
  checked.then(function () {{ state = 'ok'; }},
               function (e) {{ state = 'bad'; reason = e; }});

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
}})();
</script>""" + footer("../../"))


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

    helpdir = os.path.join(DOCS, "help")
    os.makedirs(helpdir, exist_ok=True)
    with open(os.path.join(helpdir, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(build_help(company, base))
    print("  docs/help/index.html")

    with open(os.path.join(DOCS, "404.html"), "w", encoding="utf-8") as fh:
        fh.write(build_404(company, base))

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
        urls = [base, base + "help/"] + [
            f"{base}people/{r['id']}/" for r in people]
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
        with open(os.path.join(d, "signature.html"), encoding="utf-8") as fh:
            sig = fh.read()
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
            fh.write(build_person(company, rec, base, sig))
        print(f"  docs/people/{rec['id']}/index.html")

    print(f"site -> docs/index.html + {len(people)} person page(s)")


if __name__ == "__main__":
    main()
