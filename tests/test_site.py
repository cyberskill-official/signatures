"""Locale, theme and link tests for the generated site.

Pages are generated in-process rather than read from docs/, so these run
before the build and do not silently pass against stale committed output.

Two of these exist because the bug happened during the work that added the
feature: a translated index kept the person links relative, so every name on
the Vietnamese page pointed at /vi/people/<id>/ - a directory that is never
built. It rendered perfectly and every link was dead.
"""
import importlib.util
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "build"))

import make_site as M           # noqa: E402
from model import load_company, load_people   # noqa: E402


@pytest.fixture(scope="module")
def loc():
    return M.load_locales()


@pytest.fixture(scope="module")
def data():
    c = load_company()
    return c, load_people(c)


def tr(loc, code):
    return M.T(code, loc[code])


# --- locale integrity ------------------------------------------------------

def test_english_is_present(loc):
    assert M.DEFAULT_LOCALE in loc


def test_every_locale_defines_the_same_keys(loc):
    ref = set(loc[M.DEFAULT_LOCALE])
    for code, strings in loc.items():
        assert set(strings) == ref, f"{code}.yml has drifted from en.yml"


def test_no_locale_string_is_empty(loc):
    for code, strings in loc.items():
        blank = sorted(k for k, v in strings.items() if not v.strip())
        assert not blank, f"{code}.yml has empty values: {blank}"


def test_placeholders_match_across_locales(loc):
    """{company} missing from a translation throws KeyError at build time;
    an extra one throws too. Catch it here rather than in a release."""
    def slots(v):
        return set(re.findall(r"\{(\w+)\}", v))
    ref = loc[M.DEFAULT_LOCALE]
    for code, strings in loc.items():
        if code == M.DEFAULT_LOCALE:
            continue
        for k, v in strings.items():
            assert slots(v) == slots(ref[k]), (
                f"{code}.yml '{k}' uses {slots(v)}, en.yml uses {slots(ref[k])}")


def test_a_missing_key_is_fatal_not_silently_english(loc):
    """The whole point of the loader. A fallback would ship a page that looks
    finished and reads half-translated to the only people who would notice."""
    t = M.T("vi", {k: v for k, v in loc["vi"].items() if k != "index.h1"})
    with pytest.raises(SystemExit):
        t("index.h1")


def test_vietnamese_is_actually_vietnamese(loc):
    """Guards against a copy-paste of en.yml wearing a vi filename."""
    en, vi = loc["en"], loc["vi"]
    prose = [k for k in en if not k.startswith("meta.")]
    same = [k for k in prose if en[k] == vi[k]]
    assert len(same) < len(prose) * 0.25, (
        f"{len(same)} of {len(prose)} vi strings are identical to en")
    joined = " ".join(vi[k] for k in prose)
    assert re.search(r"[ăâđêôơưàáảãạằắẳẵặìíỉĩị]", joined, re.I), \
        "no Vietnamese diacritics anywhere in vi.yml"


# --- the link that broke ---------------------------------------------------

def test_translated_index_points_at_the_real_person_pages(loc, data):
    """Person pages are built once, in English, at /people/. An index one
    directory deeper must reach up to them."""
    company, people = data
    if not people:
        pytest.skip("no people to link to")
    html = M.build_index(company, people, "https://x/vi/", tr(loc, "vi"),
                         None, "../people/")
    for r in people:
        assert f'href="../people/{r["id"]}/"' in html


def test_default_index_does_not_reach_up(loc, data):
    company, people = data
    if not people:
        pytest.skip("no people to link to")
    html = M.build_index(company, people, "https://x/", tr(loc, "en"))
    assert 'href="../people/' not in html


@pytest.mark.parametrize("code", ["en", "vi"])
def test_page_declares_its_own_language(loc, data, code):
    company, people = data
    html = M.build_index(company, people, "https://x/", tr(loc, code))
    assert f'<html lang="{loc[code]["meta.html_lang"]}"' in html


def test_language_link_is_tagged_with_the_language_it_leads_to(loc, data):
    company, people = data
    alt = ("../", loc["vi"]["meta.name"], "vi")
    html = M.build_index(company, people, "https://x/", tr(loc, "en"), alt)
    assert 'hreflang="vi"' in html and 'lang="vi"' in html


# --- theme -----------------------------------------------------------------

@pytest.mark.parametrize("code", ["en", "vi"])
def test_theme_toggle_is_on_the_page(loc, data, code):
    company, people = data
    html = M.build_index(company, people, "https://x/", tr(loc, code))
    assert 'id="themebtn"' in html
    assert "localStorage.getItem('theme')" in html


def test_theme_is_applied_before_first_paint(loc, data):
    """If the attribute is set after the stylesheet, every load flashes the
    wrong theme at anyone who chose one."""
    company, people = data
    html = M.build_index(company, people, "https://x/", tr(loc, "en"))
    assert html.index("localStorage.getItem('theme')") < html.index("<style>")


def test_toggle_labels_come_from_the_locale(loc, data):
    company, people = data
    html = M.build_index(company, people, "https://x/", tr(loc, "vi"))
    assert loc["vi"]["chrome.theme_dark"] in html
    assert "Switch to the dark theme" not in html


@pytest.mark.parametrize("code", ["en", "vi"])
def test_preview_surfaces_never_follow_the_page_theme(loc, data, code):
    """A "light mail client" preview that goes dark with the page shows the
    reader their own browser instead of their recipient's inbox."""
    company, people = data
    if not people:
        pytest.skip("no person page to render")
    html = M.build_person(company, people[0], "https://x/", "<i>sig</i>",
                          tr(loc, code))
    for m in re.finditer(r"\.surface(?:\.\w+)?\{[^}]*\}", html, re.S):
        rule = m.group(0)
        assert "var(" not in rule, f"surface inherits a themed variable: {rule}"


def test_dark_values_are_defined_once(loc):
    """Two copies of the palette drift. The media query and the explicit
    attribute must be filled from the same string."""
    assert M.CSS.count(M.DARK) == 2
