# CyberSkill email signatures

One Gmail signature per employee, generated from a YAML record and a photo,
published as a site that staff use to install their own.

**https://signatures.cyberskill.world**

## If you work here

Everything you need is on the site. Nothing to install, no build to run, no
need to clone this repo.

| I want to | Go to |
|---|---|
| Install my signature | [find your name](https://signatures.cyberskill.world/), open your page, press **Verify & copy**, paste into Gmail |
| Get one - I am not listed | [signatures.cyberskill.world/help](https://signatures.cyberskill.world/help/) |
| Change my details or photo | [signatures.cyberskill.world/help](https://signatures.cyberskill.world/help/) |

Raising the change yourself instead? [CONTRIBUTING.md](CONTRIBUTING.md) has
the browser-only route and the local one.

## If you maintain this

The rest of this README is the design and the build. Start with
[the colour architecture](#the-colour-architecture---the-decision-that-matters-most),
which is the decision everything else follows from.

---

## Adding someone by hand

```bash
# 1. photo -> src/avatars/<id>.png   (any square-ish source; 512px+ is plenty)
# 2. record -> src/people/<id>.yml   (copy stephen-cheng.yml and edit)
python3 build/make_assets.py --sheet   # check the crop on docs/assets/_avatar-sheet.png
./install.sh
python3 validation/check.py
git add -A && git commit -m "Add <name>" && git push
./install.sh --verify-remote           # after the Pages deploy finishes
```

The filename is the person's id and becomes their URL, so use lowercase
kebab-case: `src/people/mai-tran.yml` → `.../people/mai-tran/`.

### Record schema

```yaml
name: Stephen Cheng          # required
role: Founder                # required
email: info@cyberskill.world # required

name_vi: Trịnh Thái Anh      # optional second line, rendered with lang="vi"
phone: "(+84) 906 878 091"   # optional
phone_href: "+84906878091"   #   required if phone is set - digits only
website: cyberskill.world    # optional; defaults from company.yml
website_href: https://cyberskill.world
socials:                     # optional; defaults from company.yml
  - {label: LinkedIn, href: https://linkedin.com/company/cyberskill}
avatar: stephen-cheng.png    # optional; file in src/avatars/
crop: [108, 20, 250]         # optional [x, y, size] in source px
order: 0                     # optional sort key on the directory page
```

Every optional field degrades cleanly. No phone drops that row; no avatar
drops the whole portrait column and the directory falls back to initials.
Unknown fields, a missing required field, a bad id, or a `phone` without a
`phone_href` all fail the build loudly rather than shipping something wrong.

`crop` is a subject-aware square around the face. Omit it and the build
centres a square on the upper third, which is fine for a normal portrait -
check `--sheet` and add an explicit crop if the framing is off.

Company-wide values (name, tagline, base URL, shared website and socials) live
in `src/company.yml`. Changing one there changes every signature.

---

## Repository layout

```
signatures/
├── docs/                 <- GitHub Pages root. 100% generated, never hand-edited.
│   ├── index.html            signature directory
│   ├── .nojekyll             stops Jekyll dropping files
│   ├── people/<id>/
│   │   ├── index.html        install page for that person
│   │   └── signature.html    the raw payload
│   └── assets/
│       ├── shared/           logo + 4 icons - one copy for everyone
│       └── people/<id>/      that person's baked avatar
├── src/                  <- authored input
│   ├── company.yml
│   ├── logo.png
│   ├── people/_template.yml  copied by contributors; underscore = ignored
│   ├── people/<id>.yml
│   └── avatars/<id>.png
├── build/                model, asset baker, generator, site builder
├── validation/
│   ├── check.py              layout, contrast, blocked images
│   └── crossclient.py        client sanitisers x 3 engines
├── .github/
│   ├── ISSUE_TEMPLATE/       intake forms for staff with no GitHub knowledge
│   └── workflows/            validate on PR, rebuild docs/ on merge
├── CONTRIBUTING.md
└── install.sh            rebuild + verify
```

Generated output stays completely separate from source. Nothing in `docs/` is
edited by hand; the whole tree is reproducible from `src/` plus `build/`.

### Repository settings this depends on

| Setting | Value | Why |
|---|---|---|
| Settings -> Pages -> Source | **GitHub Actions** | see below |
| Settings -> Actions -> General -> Workflow permissions | either option works | the workflows request what they need explicitly |
| Branch protection on `main` | none, or allow `github-actions[bot]` | `publish.yml` commits the rebuilt `docs/` |

**Pages must deploy from Actions, not from the branch.** A push made with
`GITHUB_TOKEN` does not trigger any workflow, and that includes GitHub's own
`pages-build-deployment`. Under "deploy from a branch", `publish.yml` would
commit `docs/` and the live site would never update - the Actions log would
still be green. Uploading the built tree and calling `deploy-pages` makes the
deploy part of the same run, so it either happens or the run fails.

The custom domain is stored in repository settings, not in `docs/CNAME`, so
this source change keeps `signatures.cyberskill.world` and its certificate.
`docs/CNAME` is still generated and committed; Pages ignores it under this
source, and it keeps the branch-deploy fallback intact.

Workflow-level `permissions:` blocks grant what each job needs, so the repo's
default token setting does not have to be loosened.

---

## The design

```
[avatar]  │  Stephen Cheng                    22px bold
          │  Trịnh Thái Anh                   15px, lang="vi"
          │  Founder - CyberSkill             14px
          │
          │  [✉]  info@cyberskill.world
          │  [☎]  (+84) 906 878 091
          │  [🌐]  cyberskill.world
          │  [👥]  LinkedIn | Facebook
─────────────────────────────────────────
[logo]  Turn Your Will Into Real
```

520px on desktop, 288px at a 320px viewport, **248px tall in both** - the
layout does not reflow between widths, so the phone rendering is the desktop
rendering, just narrower.

### The colour architecture - the decision that matters most

**All text inherits the client's colour. The accent appears only in icons.
Ochre appears only in the rule.**

An earlier build used the accent for the name, six labels and five links, and
carried 31 accepted contrast findings as a result: no single colour clears
4.5:1 against both `#FFFFFF` and a dark surface - the simultaneous ceiling is
4.06:1, at `#7E7E7E`.

Moving the accent out of text removes the constraint entirely.

| Element | Treatment | Light | Dark |
|---|---|---|---|
| All text | inherits the client's colour | ~21:1 | client's own, high |
| Links | `color:inherit` + underline | ~21:1 | client's own, high |
| Icon glyphs | accent `#9E5E3E` | 5.09:1 | 3.24:1 |
| Ochre rule | `#F4BA17` | decorative | decorative |

Icons only have to clear WCAG's **3:1 non-text** threshold as graphical
objects, which the accent does on both surfaces. Text clears 4.5:1 everywhere
because it never fights a fixed colour. Hierarchy comes from size and weight
alone - do not reintroduce colour as a hierarchy device.

`color:inherit` on links is load-bearing. Omitting a colour does **not** make
an `<a>` inherit; the UA stylesheet still paints it link-blue, which measured
1.75:1 on dark. `install.sh` fails the build if it goes missing.

### Icons

Four glyphs from **Lucide (ISC)**, recoloured to accent and rasterised to 36px
PNG (18px display) through Chromium.

**No brand marks are used anywhere.** Lucide ships none, and Simple Icons no
longer ships LinkedIn - LinkedIn asked to be removed on trademark grounds.
Tracing a replacement would defeat that request, and a real Facebook mark
beside a synthetic LinkedIn one would look inconsistent regardless. So
LinkedIn and Facebook share one neutral "people" glyph on a single row, each
named in its own link text. That also cut the block from five rows to four,
which is what lets 320px render without reflowing.

PNG rather than SVG because Gmail strips inline SVG and is unreliable with SVG
in `img src`. Icon fonts are not an option either - Gmail strips `@font-face`.

### Alt text

**Every image carries `alt=""`.** An image conveying nothing beyond adjacent
text is decorative under WCAG, and the name, company and every channel already
appear as real text - alt text would make a screen reader announce each thing
twice. The readable fallback is the visible link text, which is always there.

### Blocked images

`alt=""` does **not** stop a renderer drawing a broken-image placeholder. With
images blocked you get placeholder boxes. That is unavoidable for hosted
images and is what Gmail and Outlook do anyway.

What is guaranteed instead, and measured on every run:

| Property | Result |
|---|---|
| Table width, loaded vs blocked | identical |
| Table height, loaded vs blocked | identical |
| Contact rows share one left edge | yes, unchanged when blocked |
| Rendered text, loaded vs blocked | byte-identical |

Nothing moves and no meaning is lost - every value is self-describing, so an
email address needs no label to be understood.

### Cache busting

Every asset URL carries `?v=<content-hash>`. Gmail proxies images through
`googleusercontent.com` and caches them at paste time, so replacing a file at
the same URL may never reach mail already sent. Hashing the content means any
change produces a new URL automatically - more reliable than remembering to
bump a version directory by hand.

### Gmail constraints

| Constraint | Consequence |
|---|---|
| `<style>` blocks stripped | every style inline |
| class selectors stripped | no `class` anywhere |
| media queries impossible | narrow-safety by table reflow, not breakpoints |
| `border-radius` stripped | avatar and logo shapes baked into the PNGs |
| CSS borders unreliable | the rule is a `<td>` with `bgcolor` + `background-color` |
| local and `data:` images dropped | assets must be publicly hosted |
| 10,000 character limit | ~5,400 chars per signature, 54% of budget |

The real table is `width="100%"` capped by `max-width:520px` - a hard
`width="520"` pinned it at 520px on a 320px phone and forced horizontal
scroll.

Outlook's Word engine gets an `<!--[if mso]>` wrapper, but that wrapper is
**also `width="100%"`, not a fixed 520**. Word ignores `max-width`, so a fixed
wrapper pinned the table at 520px inside Outlook's reading pane and overflowed
it by 36px at 500px and 136px at 400px - a three-pane Outlook window on a
laptop. The cap bought nothing to pay for that: every element is left-aligned
and the widest line of ink is about 285px, so removing it changes only how
much empty space trails the content. Measured identical at 400px and 1400px,
248px tall at both.

Every spacer is a table row with `mso-line-height-rule:exactly`, not a `div`;
Outlook renders a spacer div's `&nbsp;` as a full text line regardless of
font-size.

---

## Validation

```bash
pip install playwright --break-system-packages
python3 -m playwright install chromium
python3 validation/check.py        # exits non-zero on any finding
```

Per person: `{900px, 320px} x {loaded, blocked}` plus `{light, dark, forced
inversion}` = 7 runs and 7 screenshots. Images are blocked by rewriting each
`src` to a URL that genuinely 404s and waiting for the error event, so the
fallback is exercised by the renderer rather than simulated with CSS.

Signatures are regenerated against the local server's own base URL into a temp
directory, so a localhost URL can never reach the published tree - and
`install.sh` fails the build if one ever does.

| ID | Gate |
|---|---|
| V1 | no horizontal overflow at either width |
| V2 | every text node ≥ 4.5:1 (≥3:1 if large), light and dark, no exceptions |
| V4 | width, height, alignment and text identical loaded vs blocked |
| V5 | every image decorative (`alt=""`) |
| V6 | icon cell keeps 18px when images fail |
| V7 | every image is 2x its display size |
| V8 | every link has a safe scheme and an underline |
| V9 | zero `<style>`, `class`, `border-radius` |
| V10 | no `colspan` exceeds its table's real column count |
| V11 | under 10,000 characters |
| V12 | Ochre rule renders ≥3x100px with a `bgcolor` attribute |

**Gate: HIGH 0, MED 0, LOW 0.** No allowlist. If a contrast assertion fails,
coloured text has been reintroduced - find it rather than widening the
threshold.

**The automated checks are not sufficient on their own.** V5 once passed while
the blocked state was visibly wrong, because asserting `alt=""` says nothing
about placeholder rendering. Open the screenshots and look at them.

### Cross-client audit

```bash
python3 -m playwright install chromium firefox webkit
python3 validation/crossclient.py
```

Rendering the raw signature in one browser proves almost nothing about email.
Every client rewrites the markup before drawing it, and they do not share an
engine. So each run applies that client's sanitiser as a **transform** and
renders the result in the engine that client really uses.

| Transform | What it does |
|---|---|
| `webmail` | strips `<style>`, `class`, `id`, `<script>` - a no-op on this markup, which is the point |
| `word` | uncomments the mso branch, then deletes every property Word does not implement, drops `padding` off non-cells, and repaints links Outlook blue |
| `none` | passthrough, for clients that sanitise nothing meaningful here |

| Engine | Clients it genuinely covers |
|---|---|
| Blink | Chrome, Edge, Android WebViews, Gmail web, Outlook.com, Yahoo, Proton |
| WebKit | Apple Mail on macOS and iOS, every iOS mail app, Gmail web in Safari |
| Gecko | Thunderbird |

14 clients x realistic widths x the colour schemes each one actually offers,
plus two robustness probes. Checks per run: overflow, contrast (with the
inversion filter applied first, since `getComputedStyle` reports pre-filter
colours), missing glyphs by canvas measurement, link survival, image
dimension attributes, and text loss against an untransformed baseline.

**A missing engine is reported as UNCOVERED, never skipped silently.** CI runs
with `--require-engines chromium,firefox,webkit` so a broken install fails the
run instead of quietly shrinking the matrix.

---

## Caveats

### Unavoidable, by platform

**Outlook for Windows repaints links in its own blue.** The Word engine does
not implement `color:inherit`, so links come out around `#0563C1` rather than
inheriting. That is 5.6:1 on white, comfortably readable - it degrades rather
than breaks, and there is no markup that prevents it.

**Outlook for Windows drops `padding` on anything that is not a table cell.**
Two `padding-top:2px` divs lose 4px, so the block measures 244px tall in
Outlook against 248px everywhere else. Cosmetic; nothing moves horizontally.

**Blocked images draw placeholder boxes.** `alt=""` does not prevent that.
It is what Gmail and Outlook do for any hosted image, and it is why the checks
assert that width, height, alignment and text are byte-identical loaded versus
blocked, rather than pretending the placeholders are not there.

**A client that darkens the background without setting a text colour would
render the text unreadably dark.** The probe run
`probe-bgonly-*--dark-bgonly.png` shows exactly that. No client we know of
behaves this way - Gmail recolours, Apple Mail and Outlook invert, Thunderbird
recolours - and critically, **no colour choice fixes it**: the highest
simultaneous contrast against both white and a dark surface is 4.06:1 at
`#7E7E7E`, which fails AA on both. Inheriting is the best available answer,
not a compromise.

**Word's engine cannot be installed, only modelled.** Outlook for Windows
renders through Microsoft Word. The `word` transform deletes what Word drops
and renders the remainder, which reliably catches layout that *depends* on a
dropped property. It will not catch a Word-specific rendering bug in a
property Word does implement.

### Still open

**No real paste into Gmail or Outlook has been done.** Every check here is a
model. Paste it, send it, and read it on a phone and a desktop in light and
dark. That is the only test that proves Gmail's sanitiser left the markup
intact.

**WebKit is covered in CI, not locally.** Its renderer needs an EGL display
the development sandbox has no GPU for (`Could not create WPE EGL display`).
GitHub Actions runners have it, and `--require-engines` makes its absence a
CI failure. Locally the run reports those five clients as UNCOVERED.

**Nothing renders in Gmail until `docs/` is pushed and Pages has deployed.**
Run `./install.sh --verify-remote` afterwards to confirm.

**Screenshots use Liberation Sans**, the metric-compatible Linux stand-in for
Arial. Widths are accurate; glyph shapes differ slightly from macOS.

## Licences

- Icons: [Lucide](https://lucide.dev) (ISC), recoloured and rasterised.
- Photography, logo and brand colours: CyberSkill.
