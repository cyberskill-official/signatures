#!/usr/bin/env python3
"""Round 2. Every layout here keeps all three requirements:

  - CyberSkill brand colour, visibly, not just inside a baked logo PNG
  - icons on the contact rows
  - a social list that can grow

Each variant is rendered twice, with 2 socials and with 6, because
"extendable" is a claim that has to be looked at rather than asserted.

Two constraints shape all of this:

1. Text on an unknown background must inherit its colour - no single value
   clears 4.5:1 against both white and a dark surface. So brand colour is only
   safe inside a cell that pins its OWN background, which then owns both
   sides of the contrast. That is why every variant below puts umber in a
   block rather than on a word.

2. Socials stay as text, not brand icons. simple-icons carries Facebook,
   GitHub, Instagram, Telegram, TikTok, X, YouTube and Zalo - but not
   LinkedIn, which is removed at LinkedIn's request. An icon strip missing
   the one network a B2B company needs is not a strip. Text also survives
   blocked images, which icons do not.

Run:  python3 build/layout_lab.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import DOCS, MSO, OCHRE, SANS, UMBER  # noqa: E402

A = "file://" + os.path.join(DOCS, "assets")
AV = f"{A}/people/stephen-cheng/avatar-80-2x.png"
LOGO = f"{A}/shared/logo-36-2x.png"
IC = {k: f"{A}/shared/icon-{k}-2x.png" for k in
      ("mail", "phone", "globe", "users")}

CREAM = "#E8D9CD"      # readable on umber, already used in the site header
R = dict(name="Stephen Cheng", name_vi="Trịnh Thái Anh", role="Founder",
         company="CyberSkill", email="info@cyberskill.world",
         phone="(+84) 906 878 091", phone_href="+84906878091",
         web="cyberskill.world", web_href="https://cyberskill.world",
         tagline="Turn Your Will Into Real")

SOCIALS_2 = ["LinkedIn", "Facebook"]
SOCIALS_6 = ["LinkedIn", "Facebook", "GitHub", "YouTube", "Zalo", "TikTok"]

T = ('<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
     'style="border-collapse:collapse;')


def a(text, href, size=14, colour=None):
    c = f"color:{colour};" if colour else "color:inherit;"
    return (f'<a href="{href}" style="{c}text-decoration:underline;'
            f'font-size:{size}px;{MSO}">{text}</a>')


def img(src, w, h, alt=""):
    return (f'<img src="{src}" width="{w}" height="{h}" alt="{alt}" '
            f'style="display:block;width:{w}px;height:{h}px;border:0;"/>')


def txt(s, size=14, lh=20, bold=False, colour=None, pad=0):
    c = f"color:{colour};" if colour else ""
    w = "font-weight:bold;" if bold else ""
    return (f'<div style="font-size:{size}px;line-height:{lh}px;{w}{c}'
            f'padding-top:{pad}px;{MSO}">{s}</div>')


def sp(px):
    return (f'<td width="{px}" style="width:{px}px;font-size:0;'
            f'line-height:0;">&nbsp;</td>')


def social_text(socials, size=13, colour=None):
    """One wrapping line. A seventh network costs one more comma, and if it
    wraps it wraps onto a line of its own kind - nothing else moves."""
    sep = (f'<span style="font-size:{size}px;'
           f'color:{colour or "#9A9A9A"};"> &middot; </span>')
    return sep.join(a(s, "#", size, colour) for s in socials)


def icon_rows(items, size=13, gap=5):
    """Icon + value, one per row. The icon column is fixed width so a blocked
    image leaves the text where it was rather than shunting it left."""
    out = []
    for i, (k, body) in enumerate(items):
        out.append(
            f'<tr><td width="17" valign="top" style="width:17px;'
            f'padding:3px 0 0 0;line-height:0;font-size:0;">'
            f'{img(IC[k], 17, 17)}</td>'
            f'<td valign="top" style="padding:0 0 0 9px;font-size:{size}px;'
            f'line-height:19px;{MSO}">{body}</td></tr>')
        if i < len(items) - 1:
            out.append(f'<tr><td colspan="2" height="{gap}" '
                       f'style="height:{gap}px;font-size:0;line-height:0;'
                       f'{MSO}">&nbsp;</td></tr>')
    return f'{T}">{"".join(out)}</table>'


def contacts(socials, size=13):
    return [("mail", a(R["email"], f'mailto:{R["email"]}', size)),
            ("phone", a(R["phone"], f'tel:{R["phone_href"]}', size)),
            ("globe", a(R["web"], R["web_href"], size)),
            ("users", social_text(socials, size))]


# ---------------------------------------------------------------------------
# A. Umber plate. Identity reversed out, contacts on white below.
# ---------------------------------------------------------------------------
def vA(socials):
    return f'''{T}max-width:520px;font-family:{SANS};" width="100%">
<tr><td bgcolor="{UMBER}" style="background-color:{UMBER};padding:15px 18px;">
{T}" width="100%"><tr>
<td width="54" valign="middle" style="width:54px;line-height:0;font-size:0;">{img(AV, 54, 54)}</td>{sp(14)}
<td valign="middle">{txt(R["name"], 18, 23, True, "#FFFFFF")}
{txt(R["name_vi"], 13, 18, colour=CREAM, pad=1)}
{txt(R["role"] + " &middot; " + R["company"], 13, 18, colour=CREAM, pad=1)}</td>
<td align="right" valign="middle" style="text-align:right;">{img(LOGO, 34, 34)}</td>
</tr></table></td></tr>
<tr><td height="3" bgcolor="{OCHRE}" style="height:3px;background-color:{OCHRE};font-size:0;line-height:0;">&nbsp;</td></tr>
<tr><td style="padding:13px 18px 0 18px;">{icon_rows(contacts(socials))}</td></tr>
<tr><td style="padding:9px 18px 0 18px;font-size:12px;line-height:17px;{MSO}">{R["tagline"]}</td></tr>
</table>'''


# ---------------------------------------------------------------------------
# B. Umber rule instead of ochre, tighter identity, socials on their own row.
#    Closest to what exists - the smallest change that gets colour in.
# ---------------------------------------------------------------------------
def vB(socials):
    return f'''{T}max-width:520px;font-family:{SANS};" width="100%"><tr>
<td width="64" valign="top" style="width:64px;line-height:0;font-size:0;">{img(AV, 64, 64)}</td>{sp(15)}
<td width="4" bgcolor="{UMBER}" style="width:4px;background-color:{UMBER};font-size:0;line-height:0;">&nbsp;</td>{sp(15)}
<td valign="top">
{txt(R["name"], 19, 24, True)}
{txt(R["name_vi"] + " &middot; " + R["role"] + " &middot; " + R["company"], 13, 18, pad=2)}
<div style="height:10px;font-size:0;line-height:0;">&nbsp;</div>
{icon_rows(contacts(socials))}
<div style="height:11px;font-size:0;line-height:0;">&nbsp;</div>
<div style="height:2px;background-color:{OCHRE};font-size:0;line-height:0;">&nbsp;</div>
{txt(R["tagline"], 12, 17, pad=7)}</td></tr></table>'''


# ---------------------------------------------------------------------------
# C. Umber footer bar. Brand sits under the person, holding logo, tagline and
#    socials together - which is also where a growing social list belongs.
# ---------------------------------------------------------------------------
def vC(socials):
    three = contacts(socials)[:3]
    return f'''{T}max-width:520px;font-family:{SANS};" width="100%">
<tr><td style="padding:0 0 14px 0;">{T}" width="100%"><tr>
<td width="64" valign="top" style="width:64px;line-height:0;font-size:0;">{img(AV, 64, 64)}</td>{sp(15)}
<td width="3" bgcolor="{OCHRE}" style="width:3px;background-color:{OCHRE};font-size:0;line-height:0;">&nbsp;</td>{sp(15)}
<td valign="top">{txt(R["name"], 19, 24, True)}
{txt(R["name_vi"] + " &middot; " + R["role"] + " &middot; " + R["company"], 13, 18, pad=2)}
<div style="height:9px;font-size:0;line-height:0;">&nbsp;</div>
{icon_rows(three)}</td></tr></table></td></tr>
<tr><td bgcolor="{UMBER}" style="background-color:{UMBER};padding:11px 15px;">
{T}" width="100%"><tr>
<td width="28" valign="middle" style="width:28px;line-height:0;font-size:0;">{img(LOGO, 28, 28)}</td>{sp(10)}
<td valign="middle" style="font-size:12px;line-height:17px;color:{CREAM};{MSO}">
{R["tagline"]}<br/>{social_text(socials, 12, "#FFFFFF")}</td>
</tr></table></td></tr></table>'''


# ---------------------------------------------------------------------------
# D. Umber sidebar. A vertical block of colour, avatar and logo stacked in it.
# ---------------------------------------------------------------------------
def vD(socials):
    return f'''{T}max-width:520px;font-family:{SANS};" width="100%"><tr>
<td width="88" bgcolor="{UMBER}" valign="top" style="width:88px;background-color:{UMBER};padding:14px 0;text-align:center;" align="center">
<div style="font-size:0;line-height:0;">{T}" align="center"><tr><td align="center">{img(AV, 56, 56)}</td></tr>
<tr><td height="12" style="height:12px;font-size:0;line-height:0;">&nbsp;</td></tr>
<tr><td align="center">{img(LOGO, 28, 28)}</td></tr></table></div></td>
{sp(16)}
<td valign="top" style="padding-top:2px;">
{txt(R["name"], 19, 24, True)}
{txt(R["name_vi"] + " &middot; " + R["role"] + " &middot; " + R["company"], 13, 18, pad=2)}
<div style="height:10px;font-size:0;line-height:0;">&nbsp;</div>
{icon_rows(contacts(socials))}
{txt(R["tagline"], 12, 17, pad=10)}</td></tr></table>'''


# ---------------------------------------------------------------------------
# E. Thin umber cap. Company first, person second, one strip of colour.
# ---------------------------------------------------------------------------
def vE(socials):
    return f'''{T}max-width:520px;font-family:{SANS};" width="100%">
<tr><td bgcolor="{UMBER}" style="background-color:{UMBER};padding:8px 16px;
    font-size:12px;line-height:17px;color:#FFFFFF;letter-spacing:.10em;{MSO}">
<strong>{R["company"].upper()}</strong><span style="color:{OCHRE};"> &middot; </span><span style="color:{CREAM};letter-spacing:0;">{R["tagline"]}</span></td></tr>
<tr><td style="padding:14px 0 0 0;">{T}" width="100%"><tr>
<td width="60" valign="top" style="width:60px;line-height:0;font-size:0;">{img(AV, 60, 60)}</td>{sp(15)}
<td valign="top">{txt(R["name"], 19, 24, True)}
{txt(R["name_vi"] + " &middot; " + R["role"], 13, 18, pad=2)}
<div style="height:10px;font-size:0;line-height:0;">&nbsp;</div>
{icon_rows(contacts(socials))}</td></tr></table></td></tr></table>'''


VARIANTS = [
    ("A. Umber plate", "identity reversed out, contacts below", vA),
    ("B. Umber rule", "smallest change from what you have", vB),
    ("C. Umber footer bar", "brand and socials travel together", vC),
    ("D. Umber sidebar", "vertical block, avatar and logo stacked", vD),
    ("E. Umber cap", "company first, person second", vE),
]


def sheet(width, socials, heading):
    blocks = [f'<div style="font:700 15px/20px {SANS};color:#22201E;'
              f'margin:0 0 20px;">{heading}</div>']
    for title, note, fn in VARIANTS:
        blocks.append(
            f'<div style="margin:0 0 26px;">'
            f'<div style="font:600 12px/16px {SANS};letter-spacing:.08em;'
            f'text-transform:uppercase;color:#8A8178;margin:0 0 3px;">{title}</div>'
            f'<div style="font:13px/17px {SANS};color:#6B6B6B;margin:0 0 10px;">'
            f'{note}</div>'
            f'<div style="background:#FFFFFF;border:1px solid #E6E0D8;'
            f'padding:16px;width:{width}px;color:#22201E;">{fn(socials)}</div>'
            f'</div>')
    return (f'<!doctype html><meta charset="utf-8">'
            f'<body style="margin:0;padding:24px;background:#FBF9F7;">'
            f'{"".join(blocks)}</body>')


if __name__ == "__main__":
    for tag, w, socs, head in (
            ("desktop-2", 520, SOCIALS_2, "Desktop 520px &middot; 2 socials"),
            ("desktop-6", 520, SOCIALS_6, "Desktop 520px &middot; 6 socials"),
            ("phone-6", 300, SOCIALS_6, "Phone 300px &middot; 6 socials")):
        p = f"/tmp/lab2-{tag}.html"
        open(p, "w", encoding="utf-8").write(sheet(w, socs, head))
        print(f"  {p}")
