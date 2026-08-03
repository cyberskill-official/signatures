"""Record loading, validation and input safety.

The render suite in validation/ is the primary test, but it needs three
browsers and takes minutes, so in practice it runs in CI and not much else.
These run in under a second, which means they actually get run.

Every injection payload here was reproduced against the build before the
escaping and scheme-allowlisting went in. They are regression tests, not
hypotheticals.
"""
import os
import sys

import pytest
import yaml

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build"))

import model                                                # noqa: E402
from model import (RecordError, check_email, check_text,   # noqa: E402
                   check_url)

COMPANY = {"name": "TestCo", "tagline": "Tagline",
           "website": "test.example", "website_href": "https://test.example",
           "socials": [], "email_domains": ["test.example"]}

MINIMAL = {"name": "Mai Tran", "role": "Engineer", "email": "mai@test.example"}


@pytest.fixture
def people_dir(tmp_path, monkeypatch):
    d = tmp_path / "people"
    d.mkdir()
    monkeypatch.setattr(model, "PEOPLE_SRC", str(d))
    monkeypatch.setattr(model, "AVATARS_SRC", str(tmp_path / "avatars"))
    (tmp_path / "avatars").mkdir()

    def write(name, rec):
        (d / name).write_text(yaml.safe_dump(rec, allow_unicode=True),
                              encoding="utf-8")
    return write


def load(write, rec, fn="mai-tran.yml"):
    write(fn, rec)
    return model.load_people(COMPANY)


# ---------------------------------------------------------------- schema ---
def test_minimal_record_loads(people_dir):
    people = load(people_dir, dict(MINIMAL))
    assert len(people) == 1
    assert people[0]["id"] == "mai-tran"
    assert people[0]["company"] == "TestCo"


@pytest.mark.parametrize("missing", ["name", "role", "email"])
def test_required_fields(people_dir, missing):
    rec = dict(MINIMAL)
    del rec[missing]
    with pytest.raises(RecordError, match="missing required"):
        load(people_dir, rec)


def test_unknown_field_is_rejected(people_dir):
    """A typo in a field name must fail loudly, not silently do nothing."""
    with pytest.raises(RecordError, match="unknown field"):
        load(people_dir, dict(MINIMAL, rôle="Engineer"))


def test_filename_must_be_kebab_case(people_dir):
    with pytest.raises(RecordError, match="kebab-case"):
        load(people_dir, dict(MINIMAL), fn="Mai Tran.yml")


def test_underscore_files_are_skipped(people_dir):
    """_template.yml carries placeholders and must never build as a person."""
    people_dir("_template.yml", {"name": "PLACEHOLDER"})
    people_dir("mai-tran.yml", dict(MINIMAL))
    assert [p["id"] for p in model.load_people(COMPANY)] == ["mai-tran"]


def test_email_must_look_like_one(people_dir):
    with pytest.raises(RecordError, match="email"):
        load(people_dir, dict(MINIMAL, email="not-an-address"))


def test_phone_requires_phone_href(people_dir):
    with pytest.raises(RecordError, match="phone_href is missing"):
        load(people_dir, dict(MINIMAL, phone="(+84) 912 345 678"))


@pytest.mark.parametrize("bad", ["+84 912 345 678", "tel:+84912345678",
                                 "912-345-678", "abc"])
def test_phone_href_must_be_dialable(people_dir, bad):
    """It goes straight into a tel: link, so anything but digits breaks it."""
    with pytest.raises(RecordError, match="phone_href"):
        load(people_dir, dict(MINIMAL, phone="x", phone_href=bad))


def test_missing_avatar_file_is_rejected(people_dir):
    with pytest.raises(RecordError, match="not found"):
        load(people_dir, dict(MINIMAL, avatar="nope.png"))


@pytest.mark.parametrize("crop", [[1, 2], "1,2,3", [1, 2, "3"], [1.0, 2, 3]])
def test_crop_must_be_three_integers(people_dir, crop):
    with pytest.raises(RecordError, match="crop"):
        load(people_dir, dict(MINIMAL, crop=crop))


# ------------------------------------------------------------ offboarding ---
def test_inactive_person_is_not_built(people_dir):
    people_dir("mai-tran.yml", dict(MINIMAL, active=False))
    people_dir("still-here.yml", dict(MINIMAL, name="Still Here"))
    assert [p["id"] for p in model.load_people(COMPANY)] == ["still-here"]


def test_active_must_be_boolean(people_dir):
    with pytest.raises(RecordError, match="active"):
        load(people_dir, dict(MINIMAL, active="no"))


def test_active_defaults_true(people_dir):
    assert load(people_dir, dict(MINIMAL))[0]["active"] is True


# --------------------------------------------------------- input safety ----
# Every payload below reached the published page before this was fixed.
INJECTION_HREFS = [
    "javascript:alert(1)",
    "JavaScript:alert(1)",
    "  javascript:alert(1)",
    "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
    "vbscript:msgbox(1)",
    "file:///etc/passwd",
    "http://insecure.example",          # http is not in the allowlist
    'https://x.test" onmouseover="alert(1)',
]


@pytest.mark.parametrize("href", INJECTION_HREFS)
def test_social_href_scheme_is_allowlisted(people_dir, href):
    with pytest.raises(RecordError):
        load(people_dir, dict(MINIMAL,
                              socials=[{"label": "X", "href": href}]))


@pytest.mark.parametrize("href", INJECTION_HREFS)
def test_website_href_scheme_is_allowlisted(people_dir, href):
    with pytest.raises(RecordError):
        load(people_dir, dict(MINIMAL, website_href=href))


@pytest.mark.parametrize("field", ["name", "name_vi", "role"])
def test_angle_brackets_rejected_in_text(people_dir, field):
    with pytest.raises(RecordError, match="markup"):
        load(people_dir, dict(MINIMAL, **{field: "<script>alert(1)</script>"}))


@pytest.mark.parametrize("payload", [
    "Mai​Tran",        # zero-width space
    "Mai‮Tran",        # right-to-left override
    "Mai Tran",        # line separator
    "Mai\x00Tran",          # null
    "Mai﻿Tran",        # BOM
])
def test_invisible_characters_rejected(people_dir, payload):
    """Zero-width and bidi characters are how a name hides what it says."""
    with pytest.raises(RecordError, match="control or zero-width"):
        load(people_dir, dict(MINIMAL, name=payload))


def test_overlong_text_rejected(people_dir):
    with pytest.raises(RecordError, match="over the"):
        load(people_dir, dict(MINIMAL, role="x" * 200))


def test_socials_must_be_well_formed(people_dir):
    for bad in ("notalist", [{"label": "X"}], [{"href": "https://x.test"}],
                [{"label": "X", "href": "https://x.test", "extra": 1}]):
        with pytest.raises(RecordError):
            load(people_dir, dict(MINIMAL, socials=bad))


# Legitimate input must keep working. A safety check that rejects real names
# is worse than no check, because it gets removed.
@pytest.mark.parametrize("name", [
    "Trịnh Thái Anh", "Nguyễn Thị Ánh Nguyệt", "O'Brien",
    "Anne-Marie Someone", "Søren Kierkegaard", "李小龍", "Renée",
])
def test_real_names_are_accepted(people_dir, name):
    assert load(people_dir, dict(MINIMAL, name=name))[0]["name"] == name


@pytest.mark.parametrize("href", [
    "https://linkedin.com/in/someone",
    "https://x.test/path?a=1&b=2",
    "mailto:mai@test.example",
    "tel:+84912345678",
])
def test_real_urls_are_accepted(href):
    assert check_url("t", "href", href) == href


# ------------------------------------------------------------- company -----
def test_company_socials_are_validated():
    """company.yml reaches every signature, so it is not trusted either."""
    with pytest.raises(RecordError):
        check_url("company.yml", "socials[0].href", "javascript:alert(1)")


def test_check_text_rejects_non_strings():
    with pytest.raises(RecordError, match="must be text"):
        check_text("t", "name", 42)


# ------------------------------------------------------------- digest ------
def test_digest_is_stable_and_content_addressed(tmp_path):
    a, b, c = (tmp_path / n for n in ("a", "b", "c"))
    a.write_bytes(b"same"); b.write_bytes(b"same"); c.write_bytes(b"other")
    assert model.digest(str(a)) == model.digest(str(b))
    assert model.digest(str(a)) != model.digest(str(c))
    assert len(model.digest(str(a))) == 8


def test_asset_url_appends_cache_buster(tmp_path):
    f = tmp_path / "x.png"
    f.write_bytes(b"data")
    url = model.asset_url("https://s.example/", "x.png", str(f))
    assert url.startswith("https://s.example/x.png?v=")


def test_asset_url_without_local_file_has_no_buster():
    assert model.asset_url("https://s.example/", "x.png", None) == \
        "https://s.example/x.png"


# -------------------------------------------------------------- ordering ---
def test_people_sort_by_order_then_name(people_dir):
    people_dir("zoe.yml", dict(MINIMAL, name="Zoe", order=0))
    people_dir("adam.yml", dict(MINIMAL, name="Adam", order=5))
    people_dir("beth.yml", dict(MINIMAL, name="Beth"))     # default 999
    assert [p["name"] for p in model.load_people(COMPANY)] == \
        ["Zoe", "Adam", "Beth"]


# ----------------------------------------------------------------- email ---
#
# email was the only required field with no rule of its own: it was accepted
# on the strength of containing an "@", while website_href got a scheme
# allowlist and phone_href was forced to digits. A record reading
# stephen@gmail.com published without complaint.

DOMS = ["test.example"]


@pytest.mark.parametrize("addr", [
    "mai@test.example",
    "thai-anh.trinh@test.example",     # hyphens and dots in the local part
    "mai+careers@test.example",        # plus addressing
    "Mai@Test.Example",                # domains are case-insensitive
    "m@test.example",                  # one-character local part
])
def test_real_addresses_are_accepted(addr):
    check_email("t", addr, DOMS)


@pytest.mark.parametrize("addr,why", [
    ("mai@gmail.com", "domain"),       # the mistake that will actually happen
    ("mai@sub.test.example", "domain"),  # subdomains are not implied
    ("a@b", "usable address"),
    ("mai @ test.example", "space"),
    (" mai@test.example", "whitespace"),
    ("mai@test.example ", "whitespace"),
    ("mai@@test.example", "@ signs"),
    ("@test.example", "usable address"),
    ("mai@", "usable address"),
    ("mai@test.example.", "usable address"),
    ("mai@test", "usable address"),    # no suffix
    ("javascript:alert(1)@test.example", "usable address"),
    (12345, "must be text"),
])
def test_bad_addresses_are_rejected(addr, why):
    with pytest.raises(RecordError, match=why):
        check_email("t", addr, DOMS)


@pytest.mark.parametrize("addr", [
    "mai@test.example?subject=hi",
    "mai@test.example&body=owned",
])
def test_a_query_string_is_named_as_such(addr):
    """As a mailto: this prefills the subject and body of every reply. The
    message says so, because "invalid address" would send someone hunting
    for a typo that is not there."""
    with pytest.raises(RecordError, match="query string"):
        check_email("t", addr, DOMS)


def test_the_domain_error_says_where_to_fix_it():
    with pytest.raises(RecordError, match="company.yml"):
        check_email("t", "mai@gmail.com", DOMS)


def test_a_record_with_a_foreign_domain_does_not_load(people_dir):
    with pytest.raises(RecordError, match="gmail.com"):
        load(people_dir, dict(MINIMAL, email="mai@gmail.com"))


# --------------------------------------------------- the allowlist itself ---

def _company(**over):
    c = {"base_url": "https://x.example/", "name": "TestCo",
         "email_domains": ["test.example"]}
    c.update(over)
    return c


def test_missing_allowlist_is_fatal(tmp_path, monkeypatch):
    """Not optional-with-a-default. An absent list would mean the domain
    check quietly does not run - a check that passes because it looked at
    nothing is the failure this repo keeps finding."""
    monkeypatch.setattr(model, "SRC", str(tmp_path))
    for value in ({}, {"email_domains": []}, {"email_domains": "test.example"}):
        (tmp_path / "company.yml").write_text(
            yaml.safe_dump(_company(**value) if value else
                           {k: v for k, v in _company().items()
                            if k != "email_domains"}),
            encoding="utf-8")
        with pytest.raises(RecordError, match="email_domains"):
            model.load_company()


@pytest.mark.parametrize("bad", [
    "@test.example", "https://test.example", "test.example/path",
    "TEST.example", "test", "",
])
def test_allowlist_entries_must_be_bare_lowercase_domains(tmp_path,
                                                          monkeypatch, bad):
    monkeypatch.setattr(model, "SRC", str(tmp_path))
    (tmp_path / "company.yml").write_text(
        yaml.safe_dump(_company(email_domains=[bad])), encoding="utf-8")
    with pytest.raises(RecordError, match="email_domains"):
        model.load_company()


def test_a_duplicate_domain_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(model, "SRC", str(tmp_path))
    (tmp_path / "company.yml").write_text(
        yaml.safe_dump(_company(email_domains=["a.example", "a.example"])),
        encoding="utf-8")
    with pytest.raises(RecordError, match="twice"):
        model.load_company()
