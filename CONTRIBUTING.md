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

The record and workflow tests run in a fraction of a second and need no
browser:

```bash
python3 -m pytest tests/ -q
```

The full render suite needs one:

```bash
python3 -m playwright install chromium
python3 validation/check.py
python3 validation/crossclient.py --engines chromium
```

Committing `docs/` is optional. If you do commit it, it has to match a clean
build exactly - CI compares them and fails on any hand-edit. If you leave it
alone, CI rebuilds and commits it after merge.

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
website and the social links are there. Changing one changes every employee's
signature, so those changes go through a maintainer.

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

### Adding a style

Write the function, add it to `STYLES`, run `python3 -m pytest tests/ -q`. The
tests enforce four rules on every style, and they are not suggestions:

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

Person pages are deliberately not translated. They are mostly proper nouns
and one button, and every string on them is tied to live JavaScript state.

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
