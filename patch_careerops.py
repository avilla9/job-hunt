from pathlib import Path

repo = Path(__file__).parent / "career-ops"
base = Path(__file__).parent / "vendor-base" / "career-ops"  # originales sin parchear
runner = repo / "batch" / "batch-runner.sh"
anchor = '  echo "--- Processing offer #$id: $url (report $report_num, attempt $((retries + 1)))"\n'
fallback = r'''  local jd_special jd_cache gh_id gh_board
  jd_special="${jd_file}.special"
  jd_cache="$PROJECT_DIR/data/jd-cache/$(node -e "process.stdout.write(require('crypto').createHash('sha1').update(process.argv[1]).digest('hex'))" "$url").txt"
  gh_id=$(printf '%s' "$url" | sed -nE 's/.*[?&]gh_jid=([0-9]+).*/\1/p')
  gh_board=$(printf '%s' "$url" | sed -nE 's/.*[?&]board=([A-Za-z0-9_-]+).*/\1/p')
  if [[ -s "$jd_cache" ]]; then
    cp "$jd_cache" "$jd_special"
    echo "    JD via local cache"
  elif [[ -n "$gh_id" && -n "$gh_board" ]] && curl -s --max-time 30 --proto =https \
    "https://boards-api.greenhouse.io/v1/boards/$gh_board/jobs/$gh_id" > "$jd_special" && [[ $(wc -c < "$jd_special") -gt 1000 ]]; then
    echo "    JD via Greenhouse API (embedded board)"
  elif node "$PROJECT_DIR/fetch-jd.mjs" "$url" > "$jd_special" 2>/dev/null && [[ -s "$jd_special" ]]; then
    echo "    JD via ATS public API"
  elif [[ "$url" == *.icims.com/* ]] && curl -sL --max-time 30 --proto =https "${url%%\?*}?in_iframe=1" > "$jd_special" \
    && [[ $(wc -c < "$jd_special") -gt 5000 ]]; then
    echo "    JD via iCIMS iframe"
  else
    : > "$jd_special"
  fi
  if [[ -s "$jd_special" ]]; then
    mv -f "$jd_special" "$jd_file"
  else
    rm -f "$jd_special"
  fi
  if [[ ! -s "$jd_file" ]]; then
    if node "$PROJECT_DIR/browser-extract.mjs" "$url" --mode jd --max-chars 20000 2>/dev/null \
      | node -e "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{try{const t=JSON.parse(s).text||'';if(t.split(/\s+/).length>=80)process.stdout.write(t);else process.exit(1)}catch{process.exit(1)}})" > "$jd_file"; then
      echo "    JD via headless browser"
    else
      : > "$jd_file"
    fi
  fi
  if ! node -e "const t=require('fs').readFileSync(process.argv[1],'utf-8').replace(/<[^>]+>/g,' ').toLowerCase();const k=['responsib','requirement','qualification','experience','what you','you will','about the role','skills','salary','benefits','requisitos','responsabilidades','experiencia','funciones','beneficios'].filter(w=>t.includes(w)).length;const n=t.split(/\s+/).length;process.exit(n>=300&&k>=1||n>=80&&k>=2?0:1)" "$jd_file" 2>/dev/null; then
    rm -f "$jd_file"
    update_state_retrying "$id" "$url" "failed" "$started_at" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$report_num" "-" "no-jd: sin descripción de empleo legible (omitida sin coste de IA)" "$MAX_RETRIES" || true
    release_report_num "$report_num"
    echo "    ⏭️  No readable job description — skipped without calling the model"
    return 0
  fi

'''

original = (base / "batch" / "batch-runner.sh").read_text(encoding="utf-8")
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
g_original = (base / "batch-evaluate-gemini.mjs").read_text(encoding="utf-8")
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
