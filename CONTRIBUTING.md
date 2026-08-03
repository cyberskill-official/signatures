# Contributing

Every CyberSkill employee owns their own signature record. This page explains
how to get one, and how to change it later.

**If you just want a signature, you do not need this page.** Go to
[signatures.cyberskill.world/help](https://signatures.cyberskill.world/help/),
fill in the form, and someone will do it for you. This page is for raising the
change yourself.

Pick the route that matches how comfortable you are with GitHub. All three end
in the same place: a pull request that a maintainer reviews and merges.

| Route | Who it is for | What you need |
|---|---|---|
| [Open a request](#route-1-open-a-request-no-github-knowledge) | Most people | A GitHub account |
| [Edit in the browser](#route-2-edit-in-the-browser) | You have used GitHub a little | A GitHub account |
| [Work locally](#route-3-work-locally) | Maintainers | Git, Python 3, a terminal |

You never need to install anything to get a signature. You never need to run a
build. Automation does that when your change is merged.

---

## Route 1: open a request (no GitHub knowledge)

1. Go to [Issues -> New issue](https://github.com/cyberskill-official/signatures/issues/new/choose).
2. Choose **Request a new signature** or **Update my signature**.
3. Fill in the form and submit. Attach your photo by dragging it into the
   photo field.

Automation turns your request into a pull request within a couple of minutes,
runs the full check suite against it, and comments on your issue with a link.
A maintainer reviews the things a test cannot judge - spelling, accents,
whether the photo is really you - and merges.

That is the whole process. Stop here unless you want to raise the change
yourself.

---

## Route 2: edit in the browser

Nothing here needs a terminal. GitHub does the branching and the pull request
for you.

### Adding yourself

**Step 1 - copy the template.**

Open [`src/people/_template.yml`](src/people/_template.yml), press the pencil
icon, and copy everything in the file.

**Step 2 - create your record.**

Go to [`src/people/`](src/people), press **Add file -> Create new file**, and
name it after yourself in lowercase with hyphens:

```
mai-tran.yml
```

That filename becomes your web address, so `mai-tran.yml` publishes to
`https://signatures.cyberskill.world/people/mai-tran/`. Use only lowercase
letters, numbers and hyphens - the build rejects anything else rather than
publishing a broken URL.

Paste the template in and fill it out:

```yaml
name: Mai Tran
role: Software Engineer
email: mai@cyberskill.world

phone: "(+84) 912 345 678"
phone_href: "+84912345678"
```

`phone_href` is the same number with every space, bracket and plus-sign
removed except the leading `+`. It is what your phone dials when someone taps
the number, so it has to be digits only.

Leave out any line you do not want. No phone means no phone row, and nothing
else moves.

**Step 3 - add your photo.**

Go to [`src/avatars/`](src/avatars), press **Add file -> Upload files**, and
drop in a square-ish photo named to match your record exactly:

```
mai-tran.png
```

Anything from about 512px upwards is plenty. The build crops a circle from the
upper third of the frame, which suits a normal head-and-shoulders portrait. If
your photo is framed unusually, say so in the pull request and a maintainer
will set the crop for you - you do not need to work out coordinates.

No photo is fine too. Leave the `avatar` line out and your signature renders
without a portrait, with your initials on the directory page.

**Step 4 - open the pull request.**

On each file, choose **Create a new branch for this commit and start a pull
request**, then press **Propose new file**.

Put both changes on the same branch so they arrive as one pull request.

### Changing something later

Open your own file under [`src/people/`](src/people), press the pencil icon,
edit, and propose the change. Same as above, minus the photo.

To change your photo, upload a new one over the old filename.

---

## Route 3: work locally

For maintainers and anyone adding several people at once.

```bash
git clone https://github.com/cyberskill-official/signatures.git
cd signatures
pip install -r requirements.txt --break-system-packages

git checkout -b add-mai-tran
cp src/people/_template.yml src/people/mai-tran.yml
# edit it, and put the photo at src/avatars/mai-tran.png

python3 build/make_assets.py --sheet   # check the crop in docs/assets/_avatar-sheet.png
./install.sh --skip-icons              # rebuild and run the local checks
```

Committing `docs/` is optional. If you do commit it, it has to match a clean
build exactly - CI compares them and fails on any hand-edit. If you leave it
alone, CI rebuilds and commits it after merge.

---

## Testing locally

Three levels. Run the first after every change; the third before you push
anything that touches layout.

### 1. Build and unit tests - a second, no browser

```bash
./install.sh --skip-icons      # rebuild docs/ from src/
python3 -m pytest tests/ -q    # records, safety, workflows, locales, styles
```

`--skip-icons` reuses the existing icon PNGs. Drop it if you changed the icon
set. `install.sh` fails on its own if a record is malformed, a signature
exceeds Gmail's limit, or a localhost URL leaked into the output.

### 2. Open the site

```bash
cd docs && python3 -m http.server 8000
```

Then <http://localhost:8000/>. Worth opening, in this order:

| Page | What it should do |
|---|---|
| `/` and `/vi/` | every name links to a page that exists |
| `/people/<id>/` | ten styles, previews change when you press one |
| `/vi/people/<id>/` | the same page in Vietnamese |
| Language link, top right | lands on the same person, not the front page |
| Theme buttons | light / dark / system, and the choice survives a reload |
| **Verify & copy** | status goes green, then paste into Gmail |

Images are absolute URLs pointing at the published site, so they load from
production rather than from your build. That is deliberate - it is what a
recipient's mail client does. To preview a build whose images are local too:

```bash
python3 build/generate.py --base http://localhost:8000/
python3 build/make_site.py --base http://localhost:8000/
```

Rebuild with plain `./install.sh` before committing. `docs/` would otherwise
carry localhost URLs into everyone's signature; `install.sh` refuses to pass
if it finds one, so this fails loudly rather than shipping.

### 3. The render suites - minutes, needs browsers

```bash
python3 -m playwright install chromium firefox webkit
python3 validation/check.py                    # layout, contrast, blocked images
python3 validation/crossclient.py              # 14 clients x 3 engines
```

`check.py` renders every style at desktop and phone width and checks overflow,
contrast and image reachability. `crossclient.py` puts each one through the
sanitiser of 14 real mail clients in three engines, light and dark, plus a
hostile host that tries to push its own styles in.

Both print `HIGH / MED / LOW` counts and write a report - `validation/report.json`
and `validation/crossclient/report.json` - alongside a screenshot per run. A
HIGH is a defect; read the screenshot rather than trusting the number.

If a browser is missing, `crossclient.py` records `UNCOVERED` rather than
passing quietly. Chromium alone is a reasonable quick pass:

```bash
python3 validation/crossclient.py --engines chromium
```

CI runs all three on every pull request, so a WebKit-only defect is caught
there even if you never install it.

---

## What happens to your pull request

Every pull request runs the same checks:

| Check | What it catches |
|---|---|
| Unit tests | a bad record, an unsafe link, a workflow definition that would skip silently |
| Record validation | missing fields, a bad filename, a phone without a `phone_href`, a photo that is not there |
| Build | anything that stops your signature generating |
| Gmail compatibility | markup Gmail would strip, or a signature over the 10,000 character limit |
| Rendering | overflow at phone width, contrast failures, links that lost their underline |
| Cross-client | 14 mail clients across three browser engines, light and dark |
| Generated output | a hand-edit to `docs/` |

The run posts a comment on your pull request with your signature's size and a
preview link. If something fails, the comment says which check and why.

After a maintainer merges, automation rebuilds the site and GitHub Pages
publishes it. Your page appears at:

```
https://signatures.cyberskill.world/people/<your-id>/
```

Give it a minute or two, then open it and press **Verify and copy**.

---

## Ground rules

**Only edit your own record.** Changing someone else's details, or anything in
`src/company.yml`, needs their agreement or a maintainer's.

**Never hand-edit `docs/`.** The whole folder is generated from `src/` and
`build/`. An edit there is silently overwritten on the next build, so it looks
like it worked and then quietly stops working. CI fails the pull request to
stop that reaching main.

**Company-wide values live in `src/company.yml`.** The tagline, the shared
website, the social links and `email_domains` are there. Changing one changes
every employee's signature, so those changes go through a maintainer.

**Your photo is published.** It ends up at a public URL so mail clients can
fetch it, which is how hosted email images work everywhere. Use a photo you are
happy to have public.

---

## Record reference

```yaml
name: Mai Tran                 # required
role: Software Engineer        # required
email: mai@cyberskill.world    # required

name_vi: Trần Thị Mai          # optional second line, tagged as Vietnamese
phone: "(+84) 912 345 678"     # optional
phone_href: "+84912345678"     #   required if phone is set - digits only
avatar: mai-tran.png           # optional, file in src/avatars/
crop: [108, 20, 250]           # optional [x, y, size]; a maintainer sets this
order: 10                      # optional sort key on the directory page
style: plate                   # optional, one of the ten; default classic

website: cyberskill.world      # optional override of company.yml
website_href: https://cyberskill.world
socials:                       # optional override of company.yml
  - {label: LinkedIn, href: https://linkedin.com/in/maitran}
```

Anything not listed above is rejected, so a typo in a field name fails the
pull request instead of silently doing nothing.

### What the build will reject, and why

Records go straight into published HTML and into markup people paste into
their mail client, so they are treated as untrusted input even though a
colleague wrote them.

| Rule | Reason |
|---|---|
| Your email must be on a company domain | Listed in `email_domains` in `src/company.yml`. Catches the mistake somebody eventually makes: copying the template and pasting a personal address. Subdomains are not implied - each one you send from has to be listed. |
| Your email must be a usable address | It is printed on every message you ever send and has to work when someone taps it. `a@b` has no suffix, and a `?` or `&` makes it a URL rather than an address - as a `mailto:` that would prefill the subject and body of every reply. |
| Links must start with `https://`, `mailto:` or `tel:` | `javascript:` and `data:` URLs are executable. Plain `http://` is not accepted either. |
| No `<` or `>` in any text field | A job title has no reason to contain markup. |
| No invisible characters | Zero-width spaces and right-to-left overrides let a name hide what it actually says. |
| Length caps - 60 for names, 80 for a role | Long enough for real names, short enough that the layout holds. |
| `phone_href` must be digits, optionally with a leading `+` | It goes straight into a `tel:` link. |
| `active` must be `true` or `false` | A typo here would quietly unpublish someone. |

Accents, apostrophes and non-Latin scripts are all fine. `Trịnh Thái Anh`,
`O'Brien` and `李小龍` are in the test suite specifically so that these rules
can never start rejecting real names.

If your record is rejected, the failure message names the field and says what
is wrong with it.

### Picking a style

There are ten. Open your page, press the one you want, and check the previews
before you copy - they all carry exactly the same details, so nothing is lost
by choosing on looks alone.

The page remembers your last choice in that browser. To make it permanent, so
it is what your page ships with and what anyone else opening it sees, add one
line to your record:

```yaml
style: plate
```

Valid values are the ids in [`build/styles.py`](build/styles.py): `classic`,
`plate`, `cap`, `footer`, `sidebar`, `compact`, `stacked`, `split`, `banner`,
`badge`. A typo fails the build rather than quietly falling back, so you are
never left wondering why your choice did not stick.

Two styles never show a photo - `stacked` and `badge`. If you would rather not
publish one, pick either and leave `avatar` out.

### Design system conformance

This repo implements the [CyberSkill Global Design System](https://github.com/cyberskill-official/design-system)
v1.3.0 as far as email allows, and records the rest as deferrals rather than
leaving them silently unmet.

Enforced by `tests/test_styles.py`, so a new style cannot drift out of them:

| CDS rule | How it is held |
|---|---|
| Umber `#45210E`, Ochre `#F4BA17` (anchor immutables) | asserted against `model.py`; the only place either is written down |
| Wordmark in sentence case - never `CYBERSKILL` | asserted on rendered markup for all ten styles |
| Line-height 1.5 body, 1.35 headings | computed by `styles.lh()`, never written by hand, asserted per style |
| Stacked-diacritic canary `ỚẾỰỎÃỸ` | survives the markup path (unit test); measured for layout growth by `check.py` V13 |
| Slogan, Vietnamese-first | `company.yml` tagline; `src/locales/` with a documented deferral list |

Deferred, with the reason:

| CDS rule | Why it cannot apply here |
|---|---|
| Be Vietnam Pro as the UI face | A webfont needs `@font-face`, which needs a `<style>` block, which Gmail strips - the test suite asserts that. Outlook ignores webfonts regardless. It survives only in the baked logo PNG, where the wordmark is pixels. Body text falls back to Arial. |
| `cs-color-brand-*` tokens instead of hex | Mail has no custom properties and no `:root` to declare them in. The output must carry literal hex; the token discipline lives in `model.py` instead. |
| Liquid Glass surfaces (Part 21) | CDS itself collapses these to solid under `@supports not (backdrop-filter)`. Email is that fallback path by definition, so nothing is owed. |
| APCA `Lc >= 75` | `check.py` uses WCAG 2.x ratios. APCA is polarity-aware, and the colour architecture below rests on a WCAG-derived result, so switching means re-deriving it rather than swapping a constant. Open. |

### Adding a style

Write the function, add it to `STYLES` in `build/styles.py`, then name it in
every file under `src/locales/` — `label` and `note` under `style: <id>:`. The
registry says which styles exist; the locale files say what to call them, so
the picker can be read in whatever language someone chose. A style with no
name fails the build.

Then run `python3 -m pytest tests/ -q`. The tests enforce four rules on every
style, and they are not suggestions:

| Rule | Why |
|---|---|
| Brand colour visible | Otherwise it is a generic signature with our details in it. |
| Icons on the contact rows | They are the only thing making four similar lines scannable. |
| Socials as one wrapping text line | A seventh network must cost one more link and zero extra rows. |
| Colour only on a pinned background | No value clears 4.5:1 on both white and dark, so a colour is only safe where the same markup owns the background. |

Images may only be displayed at a size that was baked - `AVATAR_SIZES`,
`LOGO_SIZES`, `ICON_SIZES` in `build/model.py`. A 160px source shown at 48px
is not sharper, it is four times the bytes for every recipient of every mail,
and validation says so.

Backgrounds go on table cells, never on a `div`. Outlook draws mail through
Word, which honours the `bgcolor` attribute and ignores `background-color` on
anything else - a div rule is simply absent there.

### Changing the wording on the site

Every word of the site outside a person's own details lives in
[`src/locales/`](src/locales) - `en.yml` and `vi.yml`. Nothing is hardcoded in
the build, so fixing an awkward sentence means editing a YAML file, not
Python.

The Vietnamese was drafted alongside the English and has not yet been read by
a native speaker. If a sentence is stiff, wrong, or just not how anyone
actually says it, change it - that is the most useful pull request on this
list.

Both files must define exactly the same keys. A missing one fails the build
rather than falling back to English, because a page that is half-translated
looks finished and only the people it fails will notice. If you add a string,
add it to both.

Every page is translated, person pages included — a Vietnamese index that
leads to an English page has only moved the problem to the one screen with
the button on it. Each language gets its own `/people/<id>/`.

A few strings stay English on purpose, and `vi.yml` says which and why. The
main one is **Verify & copy**: it is the label printed on the button and the
help page tells people to press it by name, so translating one and not the
other sends someone hunting for a control that does not exist.

### When someone leaves

Set `active: false` on their record. Their page comes off the site, the record
and its history stay in git. Their photo is not deleted by that, because old
mail still points at it - see "When someone leaves" in
[README.md](README.md#when-someone-leaves) for when to remove it as well.

Anyone pictured on this site can ask to be removed at any time. That is
recorded in [LICENSE](LICENSE), not left to custom.

---

## If you get stuck

Open an issue and describe what happened. A broken pull request is not a
problem - nothing reaches the live site until a maintainer merges it, and
nothing you can put in `src/` can break anyone else's signature.
