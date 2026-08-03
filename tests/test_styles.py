"""Every style must satisfy the same four rules.

These are written against the markup rather than against a promise, because
the whole point of a registry is that someone will add an eleventh style
later and will not have read styles.py first.
"""
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "build"))

from model import OCHRE, UMBER, load_company, load_people  # noqa: E402
import styles as S  # noqa: E402

BASE = "https://example.test/"
IDS = [s[0] for s in S.STYLES]


@pytest.fixture(scope="module")
def rec():
    c = load_company()
    people = load_people(c)
    if not people:
        pytest.skip("no records to render")
    return people[0], c


def markup(sid, rec):
    return S.render(sid, rec[0], rec[1], BASE)


def test_there_are_ten(rec):
    assert len(S.STYLES) == 9, (
        f"{len(S.STYLES)} styles registered. If that is deliberate, change "
        f"this number - the picker and the docs both say nine.")


def test_ids_are_unique_and_url_safe():
    assert len(set(IDS)) == len(IDS)
    for sid in IDS:
        assert re.fullmatch(r"[a-z][a-z0-9-]*", sid), \
            f"'{sid}' becomes a filename and a localStorage key"


def test_default_is_registered():
    assert S.DEFAULT_STYLE in S.BY_ID


def test_unknown_style_is_fatal(rec):
    with pytest.raises(SystemExit):
        S.render("no-such-style", rec[0], rec[1], BASE)


# --- rule 1: brand colour visible ------------------------------------------

@pytest.mark.parametrize("sid", IDS)
def test_brand_colour_is_present(sid, rec):
    """Umber or ochre doing real work, not just baked inside the logo PNG."""
    m = markup(sid, rec)
    assert UMBER.lower() in m.lower() or OCHRE.lower() in m.lower(), (
        f"style '{sid}' has no CyberSkill colour in its markup")


@pytest.mark.parametrize("sid", IDS)
def test_pinned_backgrounds_carry_both_attribute_and_style(sid, rec):
    """Outlook's Word renderer honours the bgcolor attribute; everything else
    reads the inline style. A cell with only one of them loses its background
    in half the clients - and a reversed-out white name on a lost background
    is white on white."""
    m = markup(sid, rec)
    for tag in re.findall(r"<(?:div|span|p|table|tr)[^>]*>", m):
        if "background-color:" in tag:
            pytest.fail(
                f"style '{sid}' paints a background on a non-cell element. "
                f"Word honours the bgcolor attribute and ignores this "
                f"entirely, so the block is simply absent in Outlook: {tag}")
    for cell in re.findall(r"<td[^>]*>", m):
        has_attr = re.search(r'\sbgcolor="([^"]+)"', cell)
        has_css = re.search(r"background-color:\s*([^;\"]+)", cell)
        if has_attr or has_css:
            assert has_attr and has_css, (
                f"style '{sid}': cell pins a background with only one of "
                f"bgcolor/background-color -> {cell}")
            assert has_attr.group(1).lower() == has_css.group(1).strip().lower()


@pytest.mark.parametrize("sid", IDS)
def test_text_colour_only_appears_on_a_pinned_surface(sid, rec):
    """The contrast rule. No value clears 4.5:1 on both white and dark, so a
    colour is only safe where some ancestor pins the background and the same
    markup therefore owns both sides of the contrast.

    This walks the tree rather than matching cells with a regex: these
    layouts nest tables, so a colour set inside a pinned block looks
    unpinned to anything that only looks at one tag at a time.
    """
    from html.parser import HTMLParser

    bad = []

    class Walk(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack = [False]          # is a background pinned above here

        def handle_starttag(self, tag, attrs):
            at = dict(attrs)
            style = at.get("style", "")
            pinned = bool(at.get("bgcolor")) or "background-color:" in style
            here = self.stack[-1] or pinned
            colours = re.findall(r"(?<!background-)color:\s*(#[0-9A-Fa-f]{3,6})",
                                 style)
            if colours and not here:
                bad.append((tag, colours, style[:70]))
            if tag not in ("img", "br", "hr", "meta"):
                self.stack.append(here)

        def handle_endtag(self, tag):
            if len(self.stack) > 1:
                self.stack.pop()

    Walk().feed(markup(sid, rec))
    assert not bad, (
        f"style '{sid}' sets a text colour with no pinned background above "
        f"it - unreadable in one theme or the other: {bad}")


# --- rule 2: icons ---------------------------------------------------------

@pytest.mark.parametrize("sid", IDS)
def test_contact_rows_have_icons(sid, rec):
    m = markup(sid, rec)
    found = set(re.findall(r"icon-(\w+)-2x\.png", m))
    assert "mail" in found, f"style '{sid}' has no icon on the email row"
    assert len(found) >= 3, (
        f"style '{sid}' shows only {sorted(found)} - the record has more "
        f"contact rows than that")


# --- rule 3: extendable socials --------------------------------------------

@pytest.mark.parametrize("sid", IDS)
def test_growing_the_social_list_only_grows_the_social_line(sid, rec):
    """Six networks must cost six more links and nothing else. If a style
    laid them out in fixed columns this is where it would show."""
    r, company = rec
    few = dict(r, socials=[{"label": "LinkedIn", "href": "https://a.test/"},
                           {"label": "Facebook", "href": "https://b.test/"}])
    many = dict(r, socials=few["socials"] + [
        {"label": n, "href": f"https://{n.lower()}.test/"}
        for n in ("GitHub", "YouTube", "Zalo", "TikTok")])
    a = S.render(sid, few, company, BASE)
    b = S.render(sid, many, company, BASE)
    assert "TikTok" in b and "TikTok" not in a
    # Same structure, only more links inside it.
    assert a.count("<tr") == b.count("<tr"), (
        f"style '{sid}' adds table rows when socials grow - it cannot take a "
        f"seventh network without relayout")
    assert b.count("<a ") - a.count("<a ") == 4


@pytest.mark.parametrize("sid", IDS)
def test_no_socials_drops_the_row_without_leaving_a_hole(sid, rec):
    r, company = rec
    m = S.render(sid, dict(r, socials=[]), company, BASE)
    assert "icon-users" not in m
    assert "<td" in m and m.count("<table") == m.count("</table>")


# --- rule 4: the constraints that were paid for in blood -------------------

@pytest.mark.parametrize("sid", IDS)
def test_links_pin_inherit_or_an_explicit_colour(sid, rec):
    """Omitting a colour does NOT inherit - the UA stylesheet paints link-blue,
    which is 1.75:1 on a dark surface."""
    m = markup(sid, rec)
    for tag in re.findall(r"<a\s[^>]*>", m):
        assert "color:" in tag, f"style '{sid}' has a link with no colour: {tag}"


@pytest.mark.parametrize("sid", IDS)
def test_mso_wrapper_is_full_width(sid, rec):
    """Word ignores max-width. A fixed wrapper pinned the table at 520px
    inside a 400px Outlook reading pane and overflowed it by 136px."""
    m = markup(sid, rec)
    assert "<!--[if mso]>" in m
    assert re.search(r'\[if mso\]><table[^>]*width="100%"', m), \
        f"style '{sid}' has an mso wrapper that is not width=100%"


@pytest.mark.parametrize("sid", IDS)
def test_no_markup_gmail_strips(sid, rec):
    m = markup(sid, rec)
    for banned, why in (("<style", "Gmail strips <style> blocks"),
                        ("class=", "Gmail strips class attributes"),
                        ("border-radius", "Gmail strips border-radius"),
                        ("@media", "Gmail strips @media"),
                        ("position:", "not supported in mail"),
                        ("data:", "Gmail drops data: images")):
        assert banned not in m, f"style '{sid}': {why}"


@pytest.mark.parametrize("sid", IDS)
def test_every_image_is_decorative(sid, rec):
    """All information is real text already, so alt would duplicate it."""
    m = markup(sid, rec)
    for tag in re.findall(r"<img[^>]*>", m):
        assert 'alt=""' in tag, f"style '{sid}': {tag}"


@pytest.mark.parametrize("sid", IDS)
def test_fits_gmails_limit_with_room_to_spare(sid, rec):
    m = markup(sid, rec)
    assert len(m) < 8000, (
        f"style '{sid}' is {len(m)} chars; Gmail's limit is 10,000 and a "
        f"longer name or a sixth social has to still fit")


@pytest.mark.parametrize("sid", IDS)
def test_renders_without_a_photo(sid, rec):
    """Two styles never show one, and anyone may decline to publish one."""
    r, company = rec
    m = S.render(sid, dict(r, avatar_path=None, avatar=None), company, BASE)
    assert "avatar-" not in m
    assert m.count("<table") == m.count("</table>")
    assert r["name"] in m


@pytest.mark.parametrize("sid", IDS)
def test_record_values_are_escaped(sid, rec):
    r, company = rec
    hostile = dict(r, role='Founder" onmouseover="alert(1)',
                   name="A <b>bold</b> claim")
    m = S.render(sid, hostile, company, BASE)
    # The escaped text still reads "onmouseover=" - that is fine. What must
    # be gone is the quote that would close the style attribute and let the
    # rest become a real handler.
    assert 'onmouseover="' not in m
    assert "&quot; onmouseover=&quot;" in m or "&quot;onmouseover" in m
    assert "<b>bold</b>" not in m
    assert "&lt;b&gt;bold&lt;/b&gt;" in m

    from html.parser import HTMLParser
    handlers = []

    class Sniff(HTMLParser):
        def handle_starttag(self, tag, attrs):
            handlers.extend(k for k, _ in attrs if k.startswith("on"))

    Sniff().feed(m)
    assert not handlers, f"style '{sid}' produced event handlers: {handlers}"


# --- the names, which live in the locale files -----------------------------

def _locales():
    sys.path.insert(0, os.path.join(ROOT, "build"))
    import make_site as M
    return M.load_locales()


def test_every_style_is_named_in_every_language():
    """The registry says a style exists; the locale files say what to call it.
    A style added to one without the other puts an English label on a
    Vietnamese page, or crashes the build - the second is the good outcome
    and this test is the early version of it."""
    loc = _locales()
    for code, strings in sorted(loc.items()):
        for sid in IDS:
            for part in ("label", "note"):
                assert f"style.{sid}.{part}" in strings, \
                    f"{code}.yml has no style.{sid}.{part}"


def test_no_orphan_style_strings():
    """The other direction: a name left behind after a style was deleted."""
    loc = _locales()
    for code, strings in sorted(loc.items()):
        named = {k.split(".")[1] for k in strings if k.startswith("style.")}
        assert named <= set(IDS), \
            f"{code}.yml names styles that do not exist: {sorted(named - set(IDS))}"


def test_the_issue_form_offers_exactly_the_registered_styles():
    """The dropdown people pick from is static YAML on GitHub - it cannot be
    generated at build time, so it is pinned here instead. Without this it is
    a fourth copy of the names, free to drift the moment a style is renamed."""
    import yaml
    loc = _locales()
    en = loc["en"]
    want = [f"{sid} - {en[f'style.{sid}.label']}: {en[f'style.{sid}.note']}"
            for sid in IDS]
    forms = [os.path.join(ROOT, ".github", "ISSUE_TEMPLATE", f)
             for f in ("new-signature.yml", "update-signature.yml")]
    for path in forms:
        if not os.path.isfile(path):
            pytest.skip(f"{os.path.basename(path)} not present")
        with open(path, encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        drop = [b for b in doc["body"]
                if b.get("type") == "dropdown" and b.get("id") == "style"]
        assert len(drop) == 1, f"{path}: expected one style dropdown"
        got = drop[0]["attributes"]["options"]
        assert got == want, (
            f"{os.path.basename(path)} is out of step with src/locales/en.yml"
            f"\n  form: {got}\n  want: {want}")
        default = drop[0]["attributes"].get("default")
        assert default is not None and IDS[default] == S.DEFAULT_STYLE, (
            f"{os.path.basename(path)} preselects "
            f"'{IDS[default] if default is not None else None}', "
            f"build default is '{S.DEFAULT_STYLE}'")


# --- CyberSkill Design System conformance ----------------------------------
#
# github.com/cyberskill-official/design-system, v1.3.0. Only the parts that
# survive the medium are enforced here - see the deferral table in
# CONTRIBUTING.md for what email cannot carry and why.

def test_the_wordmark_is_never_upper_cased(rec):
    """CDS: "always set in sentence case as a single word: CyberSkill. It is
    not Cyber Skill, CYBERSKILL, cyberskill, or CYBER SKILL." Two styles
    upper-cased it for the look of the brand bar."""
    company = rec[1]
    shouting = company["name"].upper()
    if company["name"] == shouting:         # a name like "IBM" is its own upper
        pytest.skip("company name is case-degenerate")
    for sid in IDS:
        m = markup(sid, rec)
        assert shouting not in m, \
            f"style '{sid}' renders the wordmark as {shouting!r}"
        assert company["name"] in m

    # The lower-case form is deliberately not asserted against. CDS forbids
    # "cyberskill" as a wordmark, but cyberskill.world and
    # thai-anh.trinh@cyberskill.world are domains, which are lower-case by
    # nature and are not the wordmark. A test that cannot tell the two apart
    # would fail on correct markup, so it would be deleted rather than
    # obeyed - and the case it does catch, .upper(), is the one that
    # happened.


@pytest.mark.parametrize("sid", IDS)
def test_line_heights_meet_the_cds_floor(sid, rec):
    """1.5 body, 1.35 headings. CDS calls these "part of the token system,
    not optional overrides" - they are what stops the stacked-diacritic
    canary clipping, and every record here may carry a name_vi.

    Spacers are exempt: font-size:0 with line-height:0 is structure, not
    type, and giving them leading would put gaps in the layout.
    """
    bad = []
    for style in re.findall(r'style="([^"]*)"', markup(sid, rec)):
        fs = re.search(r"font-size:\s*(\d+)px", style)
        lh = re.search(r"line-height:\s*(\d+)px", style)
        if not fs or not lh:
            continue
        size, line = int(fs.group(1)), int(lh.group(1))
        if size == 0:
            continue
        # 1.35 is the loosest floor CDS allows, so anything under it fails
        # whatever the element is. Headings are the only things permitted
        # between 1.35 and 1.5, and bold is how this markup marks one.
        floor = 1.35 if "font-weight:bold" in style else 1.5
        if line < size * floor:
            bad.append(f"{size}px/{line}px = {line / size:.2f} < {floor}")
    assert not bad, f"style '{sid}' is under the CDS line-height floor: {bad}"


@pytest.mark.parametrize("sid", IDS)
def test_no_text_below_twelve_pixels(sid, rec):
    """iOS Mail scales small text up, which breaks a fixed-width layout, and
    12px is the floor anyone should be asked to read in a signature."""
    small = [int(n) for n in re.findall(r"font-size:\s*(\d+)px", markup(sid, rec))
             if 0 < int(n) < 12]
    assert not small, f"style '{sid}' sets text at {sorted(set(small))}px"


def test_the_anchor_colours_are_the_cds_values():
    """Umber and Ochre are anchor immutables. If these ever drift, the
    signature stops being CyberSkill before anyone notices visually."""
    assert UMBER.upper() == "#45210E"
    assert OCHRE.upper() == "#F4BA17"


@pytest.mark.parametrize("sid", IDS)
def test_the_stacked_diacritic_canary_renders(sid, rec):
    """CDS names ỚẾỰỎÃỸ as the canary and fails any component that clips it.
    Clipping is a pixel question that needs a browser - validation/check.py
    owns that. What is checked here is that the canary survives the markup
    path intact: not stripped, not mangled by escaping, not normalised into
    a different sequence.
    """
    r, company = rec
    canary = "ỚẾỰỎÃỸ"
    m = S.render(sid, dict(r, name_vi=canary), company, BASE)
    assert canary in m, (
        f"style '{sid}' lost the canary - it is in the record but not the "
        f"rendered markup")


@pytest.mark.parametrize("sid", IDS)
def test_no_tag_declares_an_attribute_twice(sid, rec):
    """`rule()` emitted <td style="height="2" bgcolor=... style="height:2px;...">
    for months. The parser read the first style's value as "height=", dropped
    the second as a duplicate, and threw away height, font-size and
    line-height. bgcolor still painted, so it looked fine - and the pinned-
    background test passed, because it searched the tag for bgcolor and
    background-color and found both.

    An attribute appearing twice in one tag is always a construction bug.
    """
    bad = []
    for tag in re.findall(r"<\w+[^>]*>", markup(sid, rec)):
        names = re.findall(r'(?:^|\s)([a-zA-Z-]+)=', tag)
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            bad.append((sorted(dupes), tag[:110]))
    assert not bad, f"style '{sid}' has repeated attributes: {bad}"


# --- the tests, tested ------------------------------------------------------
#
# Six checks in this repo have passed while testing nothing: a site audit
# hardcoded to two pages, check.py and crossclient.py each reading one style
# of ten, X7 comparing every style against classic, the install-page audit
# hardcoded to English, and the pinned-background test above passing on a tag
# with two style attributes. Six is a pattern, not six accidents.
#
# A rule test that cannot fail is worse than no test, because it is counted.
# So each rule below is handed markup that breaks it, and must reject it. If
# one of these stops raising, that rule has quietly stopped being enforced.

_WRAP = ('<!--[if mso]><table role="presentation" width="100%" cellpadding="0"'
         ' cellspacing="0" border="0"><tr><td><![endif]-->'
         '<table role="presentation" style="border-collapse:collapse;"'
         ' width="100%"><tr><td>{}</td></tr></table>'
         '<!--[if mso]></td></tr></table><![endif]-->')

MUTANTS = [
    ("line-height floor",
     "test_line_heights_meet_the_cds_floor",
     _WRAP.format('<div style="font-size:13px;line-height:15px;">x</div>')),
    ("wordmark upper-cased",
     "test_the_wordmark_is_never_upper_cased",
     _WRAP.format("<strong>{SHOUT}</strong>")),
    ("attribute declared twice",
     "test_no_tag_declares_an_attribute_twice",
     _WRAP.format('<td style="a" bgcolor="#45210E" style="b">x</td>')),
    ("background painted on a div",
     "test_pinned_backgrounds_carry_both_attribute_and_style",
     _WRAP.format('<div style="background-color:#45210E;">x</div>')),
    ("link with no colour",
     "test_links_pin_inherit_or_an_explicit_colour",
     _WRAP.format('<a href="https://x.test/">x</a>')),
    ("text under 12px",
     "test_no_text_below_twelve_pixels",
     _WRAP.format('<div style="font-size:9px;line-height:20px;">x</div>')),
    ("colour with nothing pinning the background",
     "test_text_colour_only_appears_on_a_pinned_surface",
     _WRAP.format('<div style="color:#9A9A9A;">x</div>')),
    ("mso wrapper not full width",
     "test_mso_wrapper_is_full_width",
     '<!--[if mso]><table width="520"><tr><td><![endif]-->'
     '<table style="border-collapse:collapse;"><tr><td>x</td></tr></table>'),
    ("image with no alt",
     "test_every_image_is_decorative",
     _WRAP.format('<img src="https://x.test/a.png" width="18" height="18"/>')),
    ("markup Gmail strips",
     "test_no_markup_gmail_strips",
     _WRAP.format('<div class="x" style="border-radius:4px;">x</div>')),
]


@pytest.mark.parametrize("label,func_name,broken",
                         [(m[0], m[1], m[2]) for m in MUTANTS],
                         ids=[m[0] for m in MUTANTS])
def test_each_rule_rejects_markup_that_breaks_it(label, func_name, broken,
                                                 rec, monkeypatch):
    r, company = rec
    broken = broken.replace("{SHOUT}", company["name"].upper())
    monkeypatch.setattr(S, "render", lambda *a, **k: broken)
    # Some rules are parametrised per style and take (sid, rec); the
    # wordmark one loops over every style itself and takes (rec).
    import inspect
    func = globals()[func_name]
    args = ("classic", rec) if "sid" in inspect.signature(func).parameters \
        else (rec,)
    try:
        func(*args)
    except pytest.skip.Exception:
        pytest.skip(f"{func_name} skipped rather than judged")
    except (AssertionError, pytest.fail.Exception):
        return                      # rejected it, which is the point
    pytest.fail(
        f"{func_name} accepted markup with: {label}. That rule is not being "
        f"enforced - it passes whatever it is given.")
