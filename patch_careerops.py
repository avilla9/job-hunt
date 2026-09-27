import subprocess
from pathlib import Path

repo = Path(__file__).parent / "career-ops"
runner = repo / "batch" / "batch-runner.sh"
anchor = '  echo "--- Processing offer #$id: $url (report $report_num, attempt $((retries + 1)))"\n'
fallback = r'''  if [[ "$url" == *gh_jid=* && "$url" == *board=* ]]; then
    local gh_id gh_board
    gh_id=$(printf '%s' "$url" | sed -nE 's/.*[?&]gh_jid=([0-9]+).*/\1/p')
    gh_board=$(printf '%s' "$url" | sed -nE 's/.*[?&]board=([A-Za-z0-9_-]+).*/\1/p')
    if [[ -n "$gh_id" && -n "$gh_board" ]] && curl -s --max-time 30 --proto =https \
      "https://boards-api.greenhouse.io/v1/boards/$gh_board/jobs/$gh_id" > "$jd_file" && [[ $(wc -c < "$jd_file") -gt 1000 ]]; then
      echo "    JD via Greenhouse API (embedded board)"
    fi
  fi
  local jd_cache
  jd_cache="$PROJECT_DIR/data/jd-cache/$(node -e "process.stdout.write(require('crypto').createHash('sha1').update(process.argv[1]).digest('hex'))" "$url").txt"
  if [[ -s "$jd_cache" ]]; then
    cp "$jd_cache" "$jd_file"
    echo "    JD via local cache"
  fi
  if [[ ! -s "$jd_file" ]]; then
    if node "$PROJECT_DIR/fetch-jd.mjs" "$url" > "$jd_file" 2>/dev/null && [[ -s "$jd_file" ]]; then
      echo "    JD via ATS public API"
    elif [[ "$url" == *.icims.com/* ]] && curl -sL --max-time 30 --proto =https "${url%%\?*}?in_iframe=1" > "$jd_file" \
      && [[ $(wc -c < "$jd_file") -gt 5000 ]]; then
      echo "    JD via iCIMS iframe"
    elif node "$PROJECT_DIR/browser-extract.mjs" "$url" --mode jd --max-chars 20000 2>/dev/null \
      | node -e "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{try{const t=JSON.parse(s).text||'';if(t.split(/\s+/).length>=80)process.stdout.write(t);else process.exit(1)}catch{process.exit(1)}})" > "$jd_file"; then
      echo "    JD via headless browser"
    else
      : > "$jd_file"
      echo "    JD not retrievable locally, worker will WebFetch"
    fi
  fi

'''

original = subprocess.run(["git", "-C", str(repo), "show", "HEAD:batch/batch-runner.sh"],
                          capture_output=True, text=True, encoding="utf-8", check=True).stdout
if anchor not in original:
    raise SystemExit("patch failed: anchor not found in batch-runner.sh")
patched = original.replace(anchor, fallback + anchor, 1)
fixes = [
    ('        report_artifacts=("$REPORTS_DIR/$report_num-"*.md)\n        shopt -u nullglob\n',
     '        report_artifacts=("$REPORTS_DIR/$report_num-"*.md)\n        shopt -u nullglob\n'
     '        local -a real_artifacts=()\n'
     '        local artifact_candidate\n'
     '        for artifact_candidate in ${report_artifacts[@]+"${report_artifacts[@]}"}; do\n'
     '          [[ "$artifact_candidate" == *-RESERVED.md ]] || real_artifacts+=("$artifact_candidate")\n'
     '        done\n'
     '        report_artifacts=(${real_artifacts[@]+"${real_artifacts[@]}"})\n'),
    ('        claude "${claude_args[@]}" > "$log_file" 2>&1 || exit_code=$?\n',
     '        $(if command -v timeout >/dev/null 2>&1; then echo "timeout 900"; elif command -v gtimeout >/dev/null 2>&1; then echo "gtimeout 900"; fi) '
     'claude "${claude_args[@]}" > "$log_file" 2>&1 || exit_code=$?\n'),
]
for old, new in fixes:
    if old not in patched:
        raise SystemExit(f"patch failed: batch-runner.sh: {old[:60]!r}")
    patched = patched.replace(old, new, 1)
if runner.read_text(encoding="utf-8") != patched:
    runner.write_text(patched, encoding="utf-8", newline="\n")

gemini = repo / "batch-evaluate-gemini.mjs"
g_original = subprocess.run(["git", "-C", str(repo), "show", "HEAD:batch-evaluate-gemini.mjs"],
                            capture_output=True, text=True, encoding="utf-8", check=True).stdout
g_anchor = "async function scrapeUrl(browser, url) {\n"
g_import = "import { promisify } from 'util';\n"
if g_anchor not in g_original or g_import not in g_original:
    raise SystemExit("patch failed: anchors not found in batch-evaluate-gemini.mjs")
g_patched = g_original.replace(g_import, g_import + "import { createHash } from 'crypto';\n", 1).replace(
    g_anchor, g_anchor + "  const cached = join(DATA_ROOT, 'data', 'jd-cache', createHash('sha1').update(url).digest('hex') + '.txt');\n"
                         "  if (existsSync(cached)) return readFileSync(cached, 'utf-8');\n", 1)
if gemini.read_text(encoding="utf-8") != g_patched:
    gemini.write_text(g_patched, encoding="utf-8", newline="\n")
print("career-ops patched")
