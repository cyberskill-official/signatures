# The Outlook check

Everything this repository asserts about Outlook on Windows is reasoned, not
observed. `crossclient.py` runs each signature through fourteen client
sanitisers in three browser engines — and not one of those engines is Word,
which is what Outlook on Windows draws mail with. The emulation cannot test
the one renderer the emulation exists to protect against.

This is the manual test that closes it. It takes about ten minutes and only
needs doing again when something in `build/styles.py` changes.

## Doing it

1. Open your page, pick a style, press **Verify & copy**.
2. Paste into a new mail in **Outlook on Windows** — the desktop app, not
   outlook.com and not the Mac build. Only the Windows desktop app uses the
   Word engine.
3. Send it to yourself and open the received copy. Compose and read are not
   the same rendering path.
4. Narrow the reading pane to roughly a third of the window.
5. Work down the table below.

Repeat for `classic`, `plate` and `sidebar`. Those three between them use every
construction the others do: a plain rule, a reversed-out block, and columns.
(`split` was the columns case until it was retired; `sidebar` covers it now
with its 88px umber column.)

## What each row is actually testing

| Check | Passes | Fails, and what it means |
|---|---|---|
| The ochre rule is visible | A solid 3px line | Missing entirely — Word ignored `background-color` and the `bgcolor` attribute did not carry it either. Every style with a rule is affected. |
| `plate`: the name is white on umber | White text on a brown block | White on white. The block is gone and the text is now invisible rather than merely unstyled — the worst failure in the set. |
| Text is Arial, not Times New Roman | Plain sans-serif | Serif. `font-family` is not surviving into nested tables, and repeating it per element did not help. |
| Line spacing looks like the browser preview | Matches | Looser. `mso-line-height-rule:exactly` is not taking effect and every block is taller than designed. |
| Nothing is cut off in a narrow pane | Fits | Horizontal scroll or clipped text. The `width="100%"` mso wrapper is not doing its job. |
| The email address wraps rather than overflowing | Wraps to two lines | Runs off the edge. **This is the one I most expect to fail** — `word-break:break-all` is the newest property here and Word's support for it is uncertain. |
| Icons appear at 18px | Sharp, aligned with the text | Wrong size, or a red X. Wrong size means the `width`/`height` attributes were ignored. |
| The photo is a circle | Circle | Square. Should not happen — the shape is baked into the PNG, not CSS — but if it does, the wrong asset is being served. |

## If something fails

Note which style and which row, and say so rather than fixing it blind. Most
of these have a known Word-safe alternative, but they cost bytes or
flexibility, and it is worth knowing which one actually broke before paying
for a fix to something that did not.

The email wrap is the exception, because there is a decision behind it. If
`break-all` is ignored, the fallback is a shorter address — and that means
every future employee's address has to stay under about 21 characters, which
is the constraint this repo deliberately avoided. Worth confirming before
accepting it.

## Recording the result

Add a row here when you run it, so the next person knows how stale this is.

| Date | Outlook version | Styles checked | Result |
|---|---|---|---|
| | | | |
