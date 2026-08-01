#!/usr/bin/env bash
#
# Rebuild everything in docs/ from src/ and verify it.
#
#   ./install.sh                  rebuild + local checks
#   ./install.sh --verify-remote  also check the published URLs resolve
#   ./install.sh --skip-icons     reuse existing icon PNGs (faster)
#
# docs/ is the GitHub Pages root and is entirely generated. Never hand-edit it.
# Commit and push docs/ for the site and the signature images to go live.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

VERIFY_REMOTE=0
SKIP_ICONS=""
for a in "$@"; do
  case "$a" in
    --verify-remote) VERIFY_REMOTE=1 ;;
    --skip-icons)    SKIP_ICONS="--skip-icons" ;;
    *) echo "unknown flag: $a"; exit 2 ;;
  esac
done

c_ok=$'\033[32m'; c_bad=$'\033[31m'; c_warn=$'\033[33m'; c_off=$'\033[0m'
ok()   { printf '%s  ok %s %s\n' "$c_ok"   "$c_off" "$1"; }
bad()  { printf '%s fail%s %s\n' "$c_bad"  "$c_off" "$1"; }
warn() { printf '%s warn%s %s\n' "$c_warn" "$c_off" "$1"; }

BASE=$(python3 - <<'PY'
import sys, os
sys.path.insert(0, "build")
from model import load_company
print(load_company()["base_url"])
PY
)
echo "==> base URL: $BASE"

# ------------------------------------------------------------------ 1. build
echo "==> assets"
python3 build/make_assets.py $SKIP_ICONS
echo "==> signatures"
python3 build/generate.py
echo "==> site"
python3 build/make_site.py

# ----------------------------------------------------------------- 2. verify
echo "==> verifying generated signatures"
fail=0
shopt -s nullglob
for f in docs/people/*/signature.html; do
  id=$(basename "$(dirname "$f")")
  chars=$(wc -m < "$f" | tr -d ' ')

  grep -q '<style'        "$f" && { bad "$id: contains <style> (Gmail strips it)"; fail=1; }
  grep -q 'class='        "$f" && { bad "$id: contains class= (Gmail strips it)"; fail=1; }
  grep -q 'border-radius' "$f" && { bad "$id: uses border-radius"; fail=1; }
  grep -q '@media'        "$f" && { bad "$id: uses @media"; fail=1; }
  grep -q 'src="\.\.'     "$f" && { bad "$id: has a relative image src"; fail=1; }
  grep -q 'src="data:'    "$f" && { bad "$id: has a data: image src"; fail=1; }
  grep -q '127.0.0.1'     "$f" && { bad "$id: localhost URL leaked from validation"; fail=1; }
  grep -q 'color:inherit' "$f" || { bad "$id: links are missing color:inherit"; fail=1; }

  if [[ "$chars" -ge 10000 ]]; then
    bad "$id: $chars chars, over Gmail's 10,000 signature limit"; fail=1
  fi

  # Never let a no-match grep fail the pipeline: under `set -o pipefail` a
  # grep that legitimately matches nothing returns 1 and aborts the script.
  imgs=$( { grep -o 'src="[^"]*"'  "$f" || true; } | wc -l | tr -d ' ')
  links=$( { grep -o 'href="[^"]*"' "$f" || true; } | wc -l | tr -d ' ')
  [[ $fail -eq 0 ]] && ok "$id  ${chars} chars  ${imgs} image(s)  ${links} link(s)"
done
[[ $fail -eq 0 ]] || exit 1

for p in docs/index.html docs/.nojekyll; do
  [[ -f "$p" ]] && ok "$p" || { bad "$p missing"; exit 1; }
done

# ------------------------------------------------------- 3. remote (opt-in)
if [[ $VERIFY_REMOTE -eq 1 ]]; then
  echo "==> verifying published URLs"
  unreachable=0

  # Collect every distinct image URL referenced by any signature.
  # An empty list is treated as a FAILURE, not a pass: a verification step
  # that silently checks nothing is worse than no verification at all.
  url_file=$(mktemp)
  for f in docs/people/*/signature.html; do
    grep -o 'src="https://[^"]*"' "$f" | sed 's/^src="//; s/"$//' >> "$url_file" || true
  done
  sort -u -o "$url_file" "$url_file"
  n_urls=$(wc -l < "$url_file" | tr -d ' ')

  if [[ "$n_urls" -eq 0 ]]; then
    bad "no image URLs found to verify - extraction is broken, refusing to pass"
    rm -f "$url_file"; exit 1
  fi
  echo "    $n_urls distinct image URL(s)"

  while IFS= read -r url; do
    [[ -z "$url" ]] && continue
    code=$(curl -s -o /dev/null -w '%{http_code}' -L --max-time 15 "$url" || echo 000)
    ctype=$(curl -s -o /dev/null -w '%{content_type}' -L --max-time 15 "$url" || echo '')
    if [[ "$code" == "200" && "$ctype" == image/* ]]; then
      ok "${url##*/}  ($code $ctype)"
    else
      bad "$url  ($code ${ctype:-no content-type})"; unreachable=1
    fi
  done < "$url_file"
  rm -f "$url_file"

  if [[ $unreachable -ne 0 ]]; then
    echo
    bad "Commit and push docs/ , wait for the Pages deploy, then re-run."
    echo "     Gmail re-hosts images at paste time but only if it can fetch"
    echo "     them once. A 404 here becomes a permanently broken signature."
    exit 1
  fi
else
  warn "skipped remote checks - run with --verify-remote after pushing"
fi

n=$(ls -d docs/people/*/ 2>/dev/null | wc -l | tr -d ' ')
cat <<EOF

==> done. $n signature(s) built.

Next:
  1. git add -A && git commit -m "Rebuild signatures" && git push
  2. Wait for the Pages deploy, then: ./install.sh --verify-remote
  3. Send everyone their page: ${BASE}people/<id>/

Adding someone:
  1. Put their photo at src/avatars/<id>.png
  2. Copy an existing src/people/*.yml to src/people/<id>.yml and edit it
  3. python3 build/make_assets.py --sheet   # check the crop framing
  4. ./install.sh && python3 validation/check.py
EOF
