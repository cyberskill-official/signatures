# Improvement plan

A review of the signatures site and repository as of `71a3749`, and what to do
next. Written to be handed to someone else for execution: every item says why
it matters, what to change, and how to know it worked.

## How this was reviewed

Findings below are from inspecting the built artifacts and running the code,
not from reading it. Where a claim is that something is broken, it was
reproduced. Where something was not testable in this environment, that is
stated rather than assumed.

Not verified, and still worth doing by hand: a real paste into Gmail, a real
open in Outlook for Windows, and any WebKit rendering (Apple Mail, iOS).

---

# P0 - fix before more people use this

## 1. Employee records can inject HTML into the published site

**Severity: high. This is the one item that should block wider rollout.**

Reproduced on the current build. Adding this to any record in `src/people/`:

```yaml
socials:
  - {label: X, href: 'javascript:alert(1)'}
  - {label: "Y\" onmouseover=\"alert(2)", href: "https://x.test"}
```

produces, in `docs/people/<id>/index.html`:

- 6 `javascript:` hrefs
- 5 injected `onmouseover="alert(2)"` handlers, plus arbitrary markup that
  escaped the attribute and broke out of the surrounding table

`./install.sh` reported `ok`. The person page renders the signature inline for
the previews, so injected script executes for anyone visiting the site.

Why it matters: the whole point of the contribution workflow is that employees
send YAML through pull requests. That is now an untrusted input path into a
public page. A careless paste is as likely as a malicious one, and the
reviewer sees YAML, not the HTML it becomes.

What exists today, and why it is not enough:

| Control | Covers | Gap |
|---|---|---|
| `check.py` V8 link-scheme gate | `javascript:` in the signature payload | only runs on the PR path |
| `install.sh` grep checks | `<style>`, `class`, `border-radius` | passed the hostile record |
| `publish.yml` | nothing | **does not run `check.py` at all** |

Do all four:

1. **Escape every interpolated value at generation time.** `generate.py` and
   `make_site.py` build HTML with f-strings and escape almost nothing. Route
   every record-derived value through `html.escape(..., quote=True)`. Names,
   roles, labels, taglines, ids.
2. **Validate URL schemes in `model.py`, at load.** Allow `https:`, `mailto:`,
   `tel:` only, for `website_href`, `socials[].href`, and `phone_href`. Reject
   at load so a bad record fails the build rather than the render.
3. **Constrain the shape of free-text fields.** Length caps and a character
   allowlist on `name`, `name_vi`, `role`, `label`. A job title does not need
   `<` or `"`.
4. **Run `check.py` in `publish.yml`.** The merge path is currently unguarded.
   A direct push to `main`, or a merge that bypassed CI, deploys unvalidated.

**Verify:** re-run the injection above. `model.py` must raise, `install.sh`
must exit non-zero, and no `javascript:` or `on*=` may appear anywhere in
`docs/`. Add this as a permanent regression test (see item 9).

**Effort: half a day.**

## 2. Nothing removes a leaver

There is no offboarding path. No mention of one in the README, CONTRIBUTING,
or any script. When someone leaves, their photo, name, job title and email
stay published at a public URL indefinitely.

Why it matters: this is a privacy obligation, not a tidiness one. It is also
the single most likely way this repo embarrasses you in a year.

Add an `archive` or `active: false` field, or an explicit removal procedure:
delete the record and the avatar, rebuild, confirm the URL 404s, and note that
already-pasted signatures keep working until the assets are removed too.
Decide deliberately whether removing the assets is correct - it breaks mail
already sent, which may be what you want or may not.

Document the decision either way. A written answer beats a correct answer
nobody can find.

**Effort: 2 hours including the docs.**

## 3. No visible keyboard focus anywhere on the site

Zero `:focus` or `:focus-visible` rules across all three page types. The
custom `.cta`, `.tab`, `.btn` and `.person` styles override the browser
default without replacing it.

Why it matters: WCAG 2.4.7 failure, and practically, anyone tabbing to the
Verify and copy button cannot see where they are. That includes the
screen-reader users most likely to rely on the text-first design already built
into the signature.

Add `:focus-visible` outlines with a contrast-passing colour on every
interactive element. Do not use `outline: none` anywhere.

**Effort: 1 hour.**

## 4. Dependencies are unpinned and actions float on tags

`pip install pyyaml pillow playwright` with no versions, in both workflows. No
`requirements.txt`, no lockfile, no Dependabot. Actions are pinned to `@v4`
and `@v7`, which are mutable tags.

Why it matters: two distinct problems.

Reproducibility - this already bit us. Different Pillow versions produced
different PNG bytes for identical pixels, which churned the `?v=` cache-buster
on every machine. That was worked around in `make_assets.py` rather than
fixed at the root.

Supply chain - a mutable tag on a third-party action is a remote-code-execution
path into a workflow that holds `contents: write` and `pages: write`.

Add `requirements.txt` with pinned versions, pin actions to full commit SHAs
with the version in a trailing comment, and add `.github/dependabot.yml` for
both `pip` and `github-actions`.

**Effort: 2 hours.**

---

# P1 - high impact, do next

## 5. The site is English-only  -  DONE

CyberSkill is a Vietnamese company. The signature carefully tags Vietnamese
names with `lang="vi"` and validates diacritic rendering across engines - and
then the interface around it is entirely in English, including the help page
written for staff with no GitHub knowledge.

Why it matters: the help page exists specifically to serve the least technical
reader. Serving that reader in their second language undercuts the reason it
was built.

Add a `locales` map in `company.yml` and generate `vi/` variants of the index
and help pages, with a language toggle in the header nav and `lang` set
correctly per page. Keep the person pages as they are - they are mostly
proper nouns and one button.

**Effort: 1 day, most of it translation review rather than code.**

Done, with one caveat. Strings moved to `src/locales/{en,vi}.yml`; `vi/`
variants of the index and help pages are generated, with a language link in
the header and `lang`/`hreflang` set per page. A missing key fails the build
rather than falling back to English.

**The Vietnamese is a draft and has not been read by a native speaker.**
Person pages stay English, as recommended.

## 6. Turning a request into a pull request is entirely manual

The issue forms collect structured data. A maintainer then reads the issue and
hand-writes the YAML. That is the bottleneck the forms were supposed to
remove, just moved.

Add a workflow on `issues: [opened, edited]` that parses the issue-form body,
writes `src/people/<id>.yml`, commits the attached photo to `src/avatars/`,
opens a pull request, and links it back to the issue. The existing PR
validation then does the checking.

Two cautions for whoever builds it:

- The photo arrives as a GitHub user-content URL, not a file. Download,
  verify it is really an image by decoding it rather than by extension,
  re-encode it, and cap the dimensions. An issue attachment is untrusted input
  and this workflow will have write access.
- Derive the id from the name with the same kebab-case rule the loader
  enforces, and fail loudly on a collision rather than silently overwriting an
  existing person.

**Effort: 1 day. Highest leverage item on this list once P0 is done.**

## 7. Reviewers cannot see what a pull request looks like  -  DONE

CI uploads screenshots as an artifact. Reviewing a signature change means
downloading a zip and opening PNGs.

Add a per-PR preview deploy, or at minimum inline the rendered signature into
the existing PR comment as a base64 image. The comment infrastructure is
already there.

Why it matters: review quality collapses when review is inconvenient. Most of
the defects found in this project were found by looking at a picture, not by
reading an assertion.

**Effort: half a day for the inline image, 1 day for a real preview deploy.**

Done, but not the way this suggested. The inline base64 image cannot work:
GitHub's markdown sanitiser drops `data:` URIs on `<img>`, and one encoded
screenshot is ~130,000 characters against a 65,536-character comment limit -
twice the whole budget for a single image. Both are asserted in
`tests/test_previews.py` so the idea does not come back.

Instead the screenshots are pushed to an orphan `previews` branch under
`pr-<n>/<sha>/` and linked from the comment. The SHA is in the path because
GitHub proxies images through camo, which caches by URL - without it a
re-pushed branch keeps showing the first screenshot taken.

## 8. Link previews are blank, and the site has no icon

No `description`, no Open Graph or Twitter tags, no favicon, no `404.html`, no
`robots.txt`, no `sitemap.xml`.

Why it matters: this URL gets pasted into Slack, Zalo and email when you tell
staff about it. Right now that renders as a bare link with no title card. It
is also the first impression of a page whose entire job is to look
professional enough that people trust it with their photo.

Add per-page `description`, `og:title` / `og:description` / `og:image`, a
favicon generated from the existing logo, and a `404.html` that links back to
the directory.

`robots.txt` needs a decision, not a default - see item 12.

**Effort: half a day.**

---

# P2 - robustness and maintainability

## 9. There are no unit tests

`validation/` renders and measures, which is the right primary test. But
`model.py` contains the record loader, the schema, the id rules and the
cache-buster, and none of it is tested directly. Every check runs through a
full build and a browser.

Add `pytest` covering: required and unknown fields, id format, `phone` without
`phone_href`, missing avatar, underscore-prefixed files being skipped, crop
validation, `custom_domain` mismatch, digest stability, and - once item 1 is
done - every injection payload as a regression test.

Why it matters: the render suite takes minutes and needs three browsers. A
loader test suite runs in under a second, which means it actually gets run.

**Effort: half a day.**

## 10. `publish.yml` deploys without validating

Covered under item 1, repeated here because it is a process gap as much as a
security one. `validate.yml` runs the full suite on pull requests.
`publish.yml` runs `install.sh` and deploys. Anything reaching `main` by any
route other than a validated PR goes straight to production.

Either run the full suite in `publish.yml`, or enable branch protection so
`main` is unreachable except through a passing PR. Prefer both. Note that
branch protection needs `github-actions[bot]` allowed to push, or the rebuild
commit is rejected.

**Effort: 1 hour, plus a settings change.**

## 11. WebKit is untested and the gap is invisible day to day

The harness reports five clients as UNCOVERED locally, and CI enforces
`--require-engines`. That is the right design. But nobody reads CI logs on a
green run, so in practice the WebKit result is unobserved.

Surface it: include the engine coverage line in the PR comment, and fail the
run if the UNCOVERED count is greater than zero on CI specifically.

Also worth doing once: borrow a Mac, open the site in Safari, and press
Verify and copy. The clipboard restructuring was done specifically for
WebKit's user-activation rule and has never been executed on WebKit.

**Effort: 2 hours, plus one manual test.**

## 12. Decide whether this site should be indexed

Every employee's name, job title, work email and photo are on a public,
crawlable domain with no `robots.txt`. Email addresses appear in page text and
in a `data-search` attribute.

This is a genuine trade-off and should be a decision, not a default:

- Indexed is fine if these addresses are already public on the website, and it
  makes the site findable by staff who lost the link.
- Noindex reduces automated harvesting, at the cost of staff needing the link.

If you choose noindex, `robots.txt` alone is not enough - add
`<meta name="robots" content="noindex">` too, since `robots.txt` only asks
crawlers not to fetch, not to omit from results.

Note that neither option protects the images, which must stay publicly
fetchable for mail clients to load them. That is inherent to hosted signature
images and cannot be designed away.

**Effort: 1 hour once decided.**

## 13. Second `<h1>` on person pages, unlabelled search input

`docs/people/<id>/index.html` has two `<h1>` elements - one in the site header
and one for the person's name. The directory search input has an `id` and a
placeholder but no associated `<label>`.

Both are small and both are real: heading structure is how screen-reader users
navigate, and a placeholder is not a label because it disappears on focus.

Demote the person name to `<h2>` or make it the only `<h1>`, and add a
visually-hidden `<label>`.

**Effort: 30 minutes.**

## 14. No licence

No `LICENSE`. The README credits Lucide (ISC) for the icons but the repo
itself states no terms, and it contains employee photographs.

Add an explicit licence, or an explicit "all rights reserved, internal use"
statement. Either is fine; silence is not, because it leaves the photograph
rights ambiguous.

**Effort: 15 minutes.**

---

# P3 - polish

## 15. The site has no dark mode

Every page sets `<meta name="color-scheme" content="light">`. Staff on a dark
OS get a bright page.

Mildly ironic given how much work went into the signature's dark-mode
behaviour. The signature previews would need care - the dark preview panels
must stay dark regardless of page theme, or they stop demonstrating anything.

**Effort: half a day.**

## 16. Changing your photo silently leaves old mail stale

The `?v=` content hash means a new photo gets a new URL. Gmail proxies and
caches images at paste time, so a signature pasted before the change keeps the
old photo forever, and nothing tells the employee.

Add a line to the help page FAQ, and consider having the update workflow
comment on the issue telling the person to re-paste once merged.

**Effort: 1 hour.**

## 17. Smaller items worth batching

- No vCard or "add to contacts" link on the person page.
- No bulk import path - onboarding twenty people means twenty YAML files.
- No way to know whether anyone actually installed their signature. Any
  analytics here needs a privacy decision first; a server-side count of
  `signature.html` fetches may be enough and avoids client-side tracking.
- `.commitmsg` is gitignored scratch from a sandbox workaround. Delete it.
- `build/vendor/` holds 86MB of `node_modules` for four icons. It is
  gitignored, but the icon build could fetch Lucide on demand instead.
- `--skip-icons` is passed everywhere in CI, so the icon rasterisation path
  is effectively untested. Either test it or document that changing icons is a
  local-only operation.

---

# Suggested execution order

Sequenced so nothing later invalidates something earlier.

**Week 1 - close the security gaps.** Items 1, 4, 10, then 9 to lock item 1
in with regression tests. Nothing here changes design or copy, so it will not
conflict with anything else. Do not widen the rollout until item 1 is done.

**Week 2 - make the workflow real.** Items 6 and 7 together - automating
request-to-PR is much more valuable when reviewers can see the result. Then
item 2, since offboarding touches the same record schema.

**Week 3 - reach the actual audience.** Items 5, 8, 12, 13, 3. Item 3 is P0 by
severity but sits here comfortably if the other accessibility and markup work
happens in the same pass - only if that pass really happens.

**Week 4 - polish.** Items 11, 14, 15, 16, 17.

## What this plan deliberately does not recommend

- **Rewriting the signature markup.** It measures clean across 24 client and
  engine combinations. The colour architecture and the fluid mso wrapper are
  both load-bearing decisions with reasons recorded in the README. Leave them.
- **Moving off GitHub Pages.** It works, the certificate is valid, and the
  Actions deploy path is now correct.
- **Adding a framework to the site.** Three generated pages with inline CSS
  load fast and have no dependencies. That is a feature.
- **Fixing the Outlook link colour or the 4px height difference.** Both are
  Word engine behaviour with no markup-level fix. They are documented.

## The one thing still not verified

Nobody has pasted this into real Gmail and read the result on a phone. Every
check in this repository is a model of what Gmail does. Do that before item 6
sends more people through the pipeline - if the sanitiser does something
unexpected, you want to find it once, not twenty times.
