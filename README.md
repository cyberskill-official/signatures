# CyberSkill email signatures

One Gmail signature per employee, generated from a YAML record and a photo,
published as a GitHub Pages site that staff use to install their own.

**Site:** https://cyberskill-official.github.io/signatures/

Staff never clone this repo. They open their page, press one button, and paste
into Gmail. This README is for whoever adds people and maintains the design.

---

## Adding someone

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
│   ├── people/<id>.yml
│   └── avatars/<id>.png
├── build/                model, asset baker, generator, site builder
├── validation/           check.py + screenshots
└── install.sh            rebuild + verify
```

Pages is configured as **deploy from branch `main`, folder `/docs`**, which
keeps generated output completely separate from source. Nothing in `docs/` is
edited by hand; the whole tree is reproducible from `src/` plus `build/`.

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

Outlook's Word engine gets an `<!--[if mso]>` fixed-width wrapper because it
ignores `max-width`. The real table is `width="100%"` capped by
`max-width:520px` - a hard `width="520"` pinned it at 520px on a 320px phone
and forced horizontal scroll. Every spacer is a table row with
`mso-line-height-rule:exactly`, not a `div`; Outlook renders a spacer div's
`&nbsp;` as a full text line regardless of font-size.

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

---

## Caveats

1. **Nothing renders in Gmail until `docs/` is pushed and Pages has
   deployed.** Run `./install.sh --verify-remote` afterwards to confirm.
2. **Not yet tested in real Gmail or real Outlook.** Headless checks cannot
   prove Gmail's sanitiser leaves the markup intact, and Outlook's Word engine
   is out of scope for Chromium. Paste it, send it, read it on both.
3. **Outlook ignores `color:inherit`** and uses its own link colour. Blue on
   white is still legible, so this degrades rather than breaks.
4. **Screenshots use Liberation Sans**, the metric-compatible Linux stand-in
   for Arial. Widths are accurate; glyph shapes differ slightly from macOS.
5. **Blocked images show placeholder boxes.** Unavoidable; layout and text are
   unaffected.

## Licences

- Icons: [Lucide](https://lucide.dev) (ISC), recoloured and rasterised.
- Photography, logo and brand colours: CyberSkill.
