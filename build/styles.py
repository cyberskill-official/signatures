#!/usr/bin/env python3
"""Ten signature styles. Same content, same rules, different arrangement.

Everyone gets the same record; nobody gets a different set of facts. What
varies is where the colour sits, whether the photo leads, and how tall the
block ends up. A style is chosen per person, so a designer and an accountant
can both have something they will actually paste.

Every style in here MUST satisfy all four, and the tests enforce it:

  1. CyberSkill colour is visible - umber or ochre doing real work, not just
     baked inside the logo PNG.
  2. Contact rows carry icons.
  3. The social list is a wrapping text line, so a seventh network costs one
     more comma and nothing above it moves. Text, not brand icons: simple-icons
     carries Facebook, GitHub, Instagram, Telegram, TikTok, X, YouTube and
     Zalo but NOT LinkedIn, which is removed at LinkedIn's request - and text
     survives blocked images, which icons do not.
  4. Text on an unpinned background inherits its colour. No value clears
     4.5:1 against both white and a dark surface, so brand colour is only
     safe inside a cell that pins its OWN background and therefore owns both
     sides of the contrast. That is why umber appears as a block and never as
     a word on white.

Adding a style: write the function, add it to STYLES, run the suite. The
tests check the four rules above; validation checks it renders.
"""
import html
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import (ACCENT, AVATAR, AVATAR_SIZES, ICON, ICON_SIZES, LOGO,
                   LOGO_SIZES, MSO, OCHRE, SANS, TABLE_W, UMBER,
                   asset_url, person_asset, shared_asset)

CREAM = "#E8D9CD"        # readable on umber; already the site header's colour
T = ('<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
     'style="border-collapse:collapse;')


def esc(v):
    """Escape for a text node or a double-quoted attribute. Records arrive by
    pull request, so everything that reaches markup goes through here."""
    return html.escape("" if v is None else str(v), quote=True)


def link(text, href, size=14, colour=None):
    """color:inherit is load-bearing. Omitting a colour does NOT inherit - the
    UA stylesheet still paints link-blue, which is 1.75:1 on a dark surface.
    An explicit colour is passed only on a pinned background."""
    c = f"color:{colour};" if colour else "color:inherit;"
    return (f'<a href="{esc(href)}" style="{c}text-decoration:underline;'
            f'font-family:{SANS};font-size:{size}px;">'
            f'<span style="white-space:nowrap;">{esc(text)}</span></a>')


def img(src, w, h, extra=""):
    """Every image is decorative. All information is already real text, so alt
    text would only duplicate it for a screen reader."""
    return (f'<img src="{esc(src)}" width="{w}" height="{h}" alt="" '
            f'style="display:block;width:{w}px;height:{h}px;border:0;'
            f'outline:none;-ms-interpolation-mode:bicubic;{extra}"/>')


def lh(size, heading=False):
    """CDS line-height floors: 1.5 body, 1.35 headings.

    The doctrine calls these "part of the token system, not optional
    overrides", and the reason is in the same Part: the canary ỚẾỰỎÃỸ must
    not clip. Vietnamese stacked diacritics need the leading, and every
    record here can carry a name_vi. Computed rather than written by hand so
    a new style cannot quietly sit below the floor.
    """
    return math.ceil(size * (1.35 if heading else 1.5))


def div(s, size=14, lh_=None, bold=False, colour=None, pad=0, heading=False):
    c = f"color:{colour};" if colour else ""
    w = "font-weight:bold;" if bold else ""
    n = lh_ if lh_ is not None else lh(size, heading)
    return (f'<div style="font-family:{SANS};font-size:{size}px;'
            f'line-height:{n}px;{w}{c}'
            f'padding-top:{pad}px;{MSO}">{s}</div>')


def sp(px):
    return (f'<td width="{px}" style="width:{px}px;font-size:0;'
            f'line-height:0;">&nbsp;</td>')


def rule(colour=OCHRE, h=2, w=None):
    """A rule is a table cell, never a styled div.

    Outlook renders through Word, which honours the bgcolor ATTRIBUTE and
    ignores background-color on a div - so a div rule simply is not there in
    Outlook. Both are set, always, and they must agree.
    """
    cell = f' width="{w}" style="width:{w}px;' if w else ' style="'
    table = T + '"' + ('' if w else ' width="100%"')
    return (f'{table}><tr>'
            f'<td{cell}height="{h}" bgcolor="{colour}" '
            f'style="height:{h}px;background-color:{colour};font-size:0;'
            f'line-height:0;">&nbsp;</td></tr></table>')


def vgap(px):
    return f'<div style="height:{px}px;font-size:0;line-height:0;">&nbsp;</div>'


def avatar(rec, base, px=AVATAR):
    """Display size must be one that was baked, so the source is exactly 2x.
    Anything else either blurs or ships pixels nobody sees - validation's V7
    catches both, which is how the first draft of these styles was found
    asking for six sizes against one 160px file."""
    if not rec.get("avatar_path"):
        return None
    if px not in AVATAR_SIZES:
        raise SystemExit(
            f"avatar size {px} is not baked - use one of {AVATAR_SIZES} "
            f"or add it to AVATAR_SIZES in model.py")
    name = f"avatar-{px}-2x.png"
    return img(asset_url(base, f"assets/people/{rec['id']}/{name}",
                         person_asset(rec["id"], name)), px, px)


def logo(base, px=LOGO):
    """Same rule as avatar(): display only at a size that was baked."""
    if px not in LOGO_SIZES:
        raise SystemExit(
            f"logo size {px} is not baked - use one of {LOGO_SIZES} or add "
            f"it to LOGO_SIZES in model.py")
    name = f"logo-{px}-2x.png"
    return img(asset_url(base, f"assets/shared/{name}",
                         shared_asset(name)), px, px)


def socials(rec, size=13, colour=None):
    """One wrapping line. Growth is absorbed here and nowhere else."""
    if not rec.get("socials"):
        return None
    # The separator inherits unless the caller is on a pinned background.
    # It was #9A9A9A, which is 2.8:1 on white - the tests caught it. A dot
    # nobody can see is not a separator, and grey is not worth a contrast
    # failure on the one surface most people read mail on.
    c = f"color:{colour};" if colour else ""
    sep = f'<span style="font-size:{size}px;{c}"> &middot; </span>'
    return sep.join(link(s["label"], s["href"], size, colour)
                    for s in rec["socials"])


def fields(rec, size=13):
    """(icon, markup) for each contact row a record actually has. A missing
    field drops its row; nothing shifts to fill the space."""
    out = [("mail", link(rec["email"], f'mailto:{rec["email"]}', size))]
    if rec.get("phone"):
        out.append(("phone", link(rec["phone"], f'tel:{rec["phone_href"]}', size)))
    if rec.get("website"):
        out.append(("globe", link(rec["website"], rec["website_href"], size)))
    s = socials(rec, size)
    if s:
        out.append(("users", s))
    return out


def icon_rows(rec, base, size=13, gap=5, px=ICON):
    """Icon column is a fixed width, so a blocked image leaves the text where
    it was instead of shunting it left."""
    if px not in ICON_SIZES:
        raise SystemExit(
            f"icon size {px} is not baked - use one of {ICON_SIZES}")
    rows = []
    items = fields(rec, size)
    for i, (name, body) in enumerate(items):
        url = asset_url(base, f"assets/shared/icon-{name}-2x.png",
                        shared_asset(f"icon-{name}-2x.png"))
        rows.append(
            f'<tr><td width="{px}" valign="top" style="width:{px}px;'
            f'padding:3px 0 0 0;line-height:0;font-size:0;">{img(url, px, px)}</td>'
            f'<td valign="top" style="padding:0 0 0 9px;font-family:{SANS};'
            f'font-size:{size}px;'
            f'line-height:{lh(size)}px;{MSO}">{body}</td></tr>')
        if i < len(items) - 1:
            rows.append(f'<tr><td colspan="2" height="{gap}" style="height:{gap}px;'
                        f'font-size:0;line-height:0;{MSO}">&nbsp;</td></tr>')
    return f'{T}">{"".join(rows)}</table>'


def ident(rec, size=19, colour=None, sub=None):
    """Name, then one line of everything else about who they are. Three
    separate lines was the single biggest contributor to the old height."""
    bits = [x for x in (rec.get("name_vi"), rec["role"], rec.get("company"))
            if x]
    return (div(esc(rec["name"]), size, bold=True, colour=colour,
                heading=True)
            + div(" &middot; ".join(esc(b) for b in bits), 13,
                  colour=sub, pad=2))


def wrap(inner, width=True):
    """Outlook renders through Word, which ignores max-width - so the mso
    wrapper is width="100%". A fixed wrapper pinned the table at 520px inside
    a 400px reading pane and overflowed it by 136px."""
    cap = f"max-width:{TABLE_W}px;" if width else ""
    # Reset what a host container can push in. A signature sits inside the
    # client's own compose or read div, and whatever that div sets inherits
    # unless something in here stops it. A host with line-height:3 grew the
    # block by 42px in WebKit until this line existed - X7 caught it.
    #
    # color is deliberately absent: it MUST keep inheriting, because the
    # client's own foreground is the only value guaranteed to be readable
    # against the client's own background.
    reset = (f"font-size:14px;line-height:{lh(14)}px;letter-spacing:normal;"
             "text-align:left;font-weight:normal;font-style:normal;"
             "text-transform:none;text-indent:0;word-spacing:normal;")
    return (f'<!--[if mso]><table role="presentation" width="100%" '
            f'cellpadding="0" cellspacing="0" border="0"><tr><td><![endif]-->\n'
            f'{T}{cap}font-family:{SANS};{reset}" width="100%">{inner}</table>\n'
            f'<!--[if mso]></td></tr></table><![endif]-->')


# ===========================================================================
# The styles
# ===========================================================================

def s_classic(rec, company, base):
    """Ochre rule, photo left. The original, with the identity lines merged."""
    av = avatar(rec, base, 80)
    left = (f'<td width="80" valign="top" style="width:80px;line-height:0;'
            f'font-size:0;">{av}</td>{sp(15)}' if av else "")
    return wrap(f'''<tr>
{left}<td width="3" bgcolor="{OCHRE}" style="width:3px;background-color:{OCHRE};font-size:0;line-height:0;">&nbsp;</td>{sp(15)}
<td valign="top">{ident(rec)}{vgap(10)}{icon_rows(rec, base)}{vgap(11)}
{rule(OCHRE, 2)}
{div(esc(company["tagline"]), 12, pad=7)}</td></tr>''')


def s_plate(rec, company, base):
    """Umber block holds the photo, the name and the logo together, so the two
    marks stop competing across the block."""
    av = avatar(rec, base, 56)
    cell = (f'<td width="56" valign="middle" style="width:56px;line-height:0;'
            f'font-size:0;">{av}</td>{sp(14)}' if av else "")
    return wrap(f'''
<tr><td bgcolor="{UMBER}" style="background-color:{UMBER};padding:15px 18px;">
{T}" width="100%"><tr>{cell}
<td valign="middle">{ident(rec, 18, "#FFFFFF", CREAM)}</td>
<td align="right" valign="middle" style="text-align:right;">{logo(base, 36)}</td>
</tr></table></td></tr>
<tr><td height="3" bgcolor="{OCHRE}" style="height:3px;background-color:{OCHRE};font-size:0;line-height:0;">&nbsp;</td></tr>
<tr><td style="padding:13px 18px 0 18px;">{icon_rows(rec, base)}</td></tr>
<tr><td style="padding:9px 18px 0 18px;font-family:{SANS};font-size:12px;line-height:{lh(12)}px;{MSO}">{esc(company["tagline"])}</td></tr>''')


def s_cap(rec, company, base):
    """Company first, person second. The smallest area of colour that still
    reads as brand."""
    av = avatar(rec, base, 56)
    cell = (f'<td width="56" valign="top" style="width:56px;line-height:0;'
            f'font-size:0;">{av}</td>{sp(15)}' if av else "")
    return wrap(f'''
<tr><td bgcolor="{UMBER}" style="background-color:{UMBER};padding:8px 16px;font-family:{SANS};font-size:12px;line-height:{lh(12)}px;color:#FFFFFF;{MSO}">
<strong>{esc(company["name"])}</strong><span style="color:{OCHRE};"> &middot; </span><span style="color:{CREAM};">{esc(company["tagline"])}</span></td></tr>
<tr><td style="padding:14px 0 0 0;">{T}" width="100%"><tr>{cell}
<td valign="top">{ident(rec)}{vgap(10)}{icon_rows(rec, base)}</td></tr></table></td></tr>''')


def s_footer(rec, company, base):
    """Brand and socials travel together in a bar at the bottom - which is
    also where a growing social list belongs."""
    av = avatar(rec, base, 56)
    cell = (f'<td width="56" valign="top" style="width:56px;line-height:0;'
            f'font-size:0;">{av}</td>{sp(15)}' if av else "")
    soc = socials(rec, 12, "#FFFFFF")
    rows = [(n, b) for n, b in fields(rec) if n != "users"]
    inner = []
    for i, (name, body) in enumerate(rows):
        url = asset_url(base, f"assets/shared/icon-{name}-2x.png",
                        shared_asset(f"icon-{name}-2x.png"))
        inner.append(f'<tr><td width="{ICON}" valign="top" style="width:{ICON}px;'
                     f'padding:3px 0 0 0;line-height:0;font-size:0;">'
                     f'{img(url, ICON, ICON)}</td>'
                     f'<td valign="top" style="padding:0 0 0 9px;font-family:{SANS};'
                     f'font-size:13px;'
                     f'line-height:{lh(13)}px;{MSO}">{body}</td></tr>')
        if i < len(rows) - 1:
            inner.append('<tr><td colspan="2" height="5" style="height:5px;'
                         f'font-size:0;line-height:0;{MSO}">&nbsp;</td></tr>')
    return wrap(f'''
<tr><td style="padding:0 0 14px 0;">{T}" width="100%"><tr>{cell}
<td width="3" bgcolor="{OCHRE}" style="width:3px;background-color:{OCHRE};font-size:0;line-height:0;">&nbsp;</td>{sp(15)}
<td valign="top">{ident(rec)}{vgap(9)}{T}">{"".join(inner)}</table></td></tr></table></td></tr>
<tr><td bgcolor="{UMBER}" style="background-color:{UMBER};padding:11px 15px;">
{T}" width="100%"><tr>
<td width="28" valign="middle" style="width:28px;line-height:0;font-size:0;">{logo(base, 28)}</td>{sp(10)}
<td valign="middle" style="font-family:{SANS};font-size:12px;line-height:{lh(12)}px;color:{CREAM};{MSO}">{esc(company["tagline"])}{f"<br/>{soc}" if soc else ""}</td>
</tr></table></td></tr>''')


def s_sidebar(rec, company, base):
    """A vertical block of colour with the photo and the logo stacked in it."""
    av = avatar(rec, base, 56)
    stack = (f'{T}" align="center"><tr><td align="center">{av}</td></tr>'
             f'<tr><td height="12" style="height:12px;font-size:0;'
             f'line-height:0;">&nbsp;</td></tr>'
             f'<tr><td align="center">{logo(base, 28)}</td></tr></table>'
             if av else
             f'{T}" align="center"><tr><td align="center">{logo(base, 36)}</td>'
             f'</tr></table>')
    return wrap(f'''<tr>
<td width="88" bgcolor="{UMBER}" valign="top" align="center" style="width:88px;background-color:{UMBER};padding:14px 0;text-align:center;">
<div style="font-size:0;line-height:0;">{stack}</div></td>{sp(16)}
<td valign="top" style="padding-top:2px;">{ident(rec)}{vgap(10)}{icon_rows(rec, base)}
{div(esc(company["tagline"]), 12, pad=10)}</td></tr>''')


def s_compact(rec, company, base):
    """The smallest block that still carries everything. For anyone who
    replies forty times a day."""
    av = avatar(rec, base, 56)
    cell = (f'<td width="56" valign="top" style="width:56px;line-height:0;'
            f'font-size:0;">{av}</td>{sp(12)}' if av else "")
    return wrap(f'''<tr>{cell}
<td width="3" bgcolor="{OCHRE}" style="width:3px;background-color:{OCHRE};font-size:0;line-height:0;">&nbsp;</td>{sp(12)}
<td valign="top">{ident(rec, 16)}{vgap(8)}{icon_rows(rec, base, 12, 3)}</td>
<td align="right" valign="top" style="text-align:right;">{logo(base, 28)}</td></tr>''')


def s_stacked(rec, company, base):
    """No photo column at all. Logo leads, everything else sits under it."""
    return wrap(f'''
<tr><td>{T}"><tr>
<td width="36" valign="middle" style="width:36px;line-height:0;font-size:0;">{logo(base, 36)}</td>{sp(11)}
<td valign="middle" style="font-family:{SANS};font-size:12px;line-height:{lh(12)}px;{MSO}">
<strong>{esc(company["name"])}</strong></td></tr></table></td></tr>
<tr><td height="12" style="height:12px;font-size:0;line-height:0;">&nbsp;</td></tr>
<tr><td>{rule(OCHRE, 2, 52)}</td></tr>
<tr><td height="12" style="height:12px;font-size:0;line-height:0;">&nbsp;</td></tr>
<tr><td>{ident(rec)}{vgap(10)}{icon_rows(rec, base)}
{div(esc(company["tagline"]), 12, pad=10)}</td></tr>''')


def s_split(rec, company, base):
    """Identity one side, contacts the other. Wide and short - and it stacks
    rather than crushes when the pane narrows."""
    av = avatar(rec, base, 56)
    cell = (f'<td width="56" valign="top" style="width:56px;line-height:0;'
            f'font-size:0;">{av}</td>{sp(14)}' if av else "")
    return wrap(f'''<tr>{cell}
<td valign="top" width="180" style="width:180px;">{ident(rec, 18)}
{vgap(10)}{T}"><tr>
<td width="28" valign="middle" style="width:28px;line-height:0;font-size:0;">{logo(base, 28)}</td>{sp(9)}
<td valign="middle" style="font-family:{SANS};font-size:12px;line-height:{lh(12)}px;{MSO}">{esc(company["tagline"])}</td>
</tr></table></td>{sp(16)}
<td width="3" bgcolor="{UMBER}" style="width:3px;background-color:{UMBER};font-size:0;line-height:0;">&nbsp;</td>{sp(16)}
<td valign="top">{icon_rows(rec, base)}</td></tr>''')


def s_banner(rec, company, base):
    """Ruled top and bottom in ochre. Reads as a printed card."""
    av = avatar(rec, base, 56)
    cell = (f'<td width="56" valign="top" style="width:56px;line-height:0;'
            f'font-size:0;">{av}</td>{sp(15)}' if av else "")
    return wrap(f'''
<tr><td height="3" bgcolor="{OCHRE}" style="height:3px;background-color:{OCHRE};font-size:0;line-height:0;">&nbsp;</td></tr>
<tr><td style="padding:14px 0;">{T}" width="100%"><tr>{cell}
<td valign="top">{ident(rec)}{vgap(10)}{icon_rows(rec, base)}</td>
<td align="right" valign="top" style="text-align:right;">{logo(base, 36)}</td>
</tr></table></td></tr>
<tr><td height="1" bgcolor="{UMBER}" style="height:1px;background-color:{UMBER};font-size:0;line-height:0;">&nbsp;</td></tr>
<tr><td style="padding:8px 0 0 0;font-family:{SANS};font-size:12px;line-height:{lh(12)}px;{MSO}">{esc(company["tagline"])}</td></tr>''')


def s_badge(rec, company, base):
    """An umber square carrying the logo, name beside it. No photo, so it
    suits anyone who would rather not publish one."""
    return wrap(f'''<tr>
<td width="56" bgcolor="{UMBER}" valign="middle" align="center" style="width:56px;background-color:{UMBER};padding:11px 0;text-align:center;">
<div style="font-size:0;line-height:0;">{T}" align="center"><tr><td align="center">{logo(base, 36)}</td></tr></table></div></td>{sp(15)}
<td valign="middle">{ident(rec, 18)}</td></tr>
<tr><td colspan="3" height="13" style="height:13px;font-size:0;line-height:0;">&nbsp;</td></tr>
<tr><td colspan="3">{icon_rows(rec, base)}
{div(esc(company["tagline"]), 12, pad=9)}</td></tr>''')


# Order is the order they appear on the page. First is the default.
#
# Names and one-line descriptions are NOT here - they live in src/locales/,
# because the picker is shown in whatever language the reader chose and a
# label baked into Python can only ever be English. This list answers "which
# styles exist"; the locale files answer "what do we call them".
STYLES = [
    ("classic", s_classic),
    ("plate", s_plate),
    ("cap", s_cap),
    ("footer", s_footer),
    ("sidebar", s_sidebar),
    ("compact", s_compact),
    ("stacked", s_stacked),
    ("split", s_split),
    ("banner", s_banner),
    ("badge", s_badge),
]

BY_ID = dict(STYLES)
DEFAULT_STYLE = STYLES[0][0]


def render(style_id, rec, company, base):
    try:
        fn = BY_ID[style_id]
    except KeyError:
        raise SystemExit(
            f"unknown style '{style_id}' - known: {', '.join(BY_ID)}")
    return fn(rec, company, base)
