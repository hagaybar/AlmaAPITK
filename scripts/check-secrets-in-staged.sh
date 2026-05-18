#!/usr/bin/env bash
# check-secrets-in-staged.sh — refuse commits that contain likely secret values.
#
# Invoked by .git/hooks/pre-commit (set up via scripts/install-git-hooks.sh).
# Scans the unified diff of staged changes for high-confidence secret-shape
# matches. Exits non-zero on a hit, with a clear message naming the file,
# line, and the matched pattern category (never the matched value).
#
# Design notes:
# - Scans `git diff --cached --unified=0` (added/changed lines only, not full files)
# - Patterns target the SHAPE of the secret (length + character class + prefix),
#   not the value, so this scanner does not need to know the actual secret list.
# - Patterns include common Alma, AWS, OpenAI, Google, and generic env-export shapes.
# - The forbidden-files list refuses to allow ANY content from credential-bearing
#   filenames to be staged in the first place.

set -u
set -o pipefail

RED=$'\033[0;31m'
YEL=$'\033[1;33m'
NC=$'\033[0m'

hits=0

emit_hit() {
  local file="$1"
  local line="$2"
  local category="$3"
  printf "%sBLOCKED%s  %s:%s  matched pattern: %s\n" "$RED" "$NC" "$file" "$line" "$category" >&2
  hits=$((hits + 1))
}

# 1. Forbidden filenames — refuse if any of these are staged at all.
forbidden_files=$(git diff --cached --name-only --diff-filter=AM | grep -E '^(\.env(\..+)?|.*\.env|secrets/.*|credentials/.*|.*\.pem|.*\.key|.*\.crt)$' || true)
if [ -n "$forbidden_files" ]; then
  while IFS= read -r f; do
    emit_hit "$f" "(file)" "credential-bearing filename (.env, secrets/, credentials/, *.pem, *.key)"
  done <<< "$forbidden_files"
fi

# 2. Scan the staged diff for secret-shape patterns.
# We use git diff --cached --unified=0 and parse @@ hunk headers + added lines.

current_file=""
current_added_line_no=0

while IFS= read -r line; do
  case "$line" in
    "diff --git "*)
      # New file diff begins; remember the right-hand path.
      current_file=$(echo "$line" | awk '{print $4}' | sed 's|^b/||')
      current_added_line_no=0
      ;;
    "@@ "*)
      # Hunk header: extract the new-side starting line.
      hunk_info=$(echo "$line" | sed -E 's/^@@ -[0-9]+(,[0-9]+)? \+([0-9]+)(,[0-9]+)? @@.*/\2/')
      if [[ "$hunk_info" =~ ^[0-9]+$ ]]; then
        current_added_line_no=$hunk_info
        # We'll increment for each '+' line we see.
        # Set to one less so first '+' becomes the actual starting line.
        current_added_line_no=$((current_added_line_no - 1))
      fi
      ;;
    "+++ "*|"--- "*|" "*|-*)
      # File header or context or removed line — skip.
      ;;
    "+"*)
      current_added_line_no=$((current_added_line_no + 1))
      content="${line:1}"  # strip leading '+'

      # Pattern A: Alma API key (l7xx... / l8xx... + 32 hex chars)
      if echo "$content" | grep -qE 'l[78]xx[0-9a-f]{32}'; then
        emit_hit "$current_file" "$current_added_line_no" "Alma API key shape (l7xx/l8xx + 32 hex)"
        continue
      fi
      # Pattern B: AWS access-key id (AKIA[0-9A-Z]{16})
      if echo "$content" | grep -qE 'AKIA[0-9A-Z]{16}'; then
        emit_hit "$current_file" "$current_added_line_no" "AWS access-key id (AKIA...)"
        continue
      fi
      # Pattern C: OpenAI keys (sk-proj-..., sk-admin-..., sk- + 40+ chars)
      if echo "$content" | grep -qE 'sk-(proj|admin)?-[A-Za-z0-9_-]{20,}'; then
        emit_hit "$current_file" "$current_added_line_no" "OpenAI API key shape (sk-...)"
        continue
      fi
      # Pattern D: Google API key (AIza + 35 base64-url chars)
      if echo "$content" | grep -qE 'AIza[0-9A-Za-z_-]{35}'; then
        emit_hit "$current_file" "$current_added_line_no" "Google API key shape (AIza...)"
        continue
      fi
      # Pattern E: Generic export of *_(KEY|SECRET|TOKEN|API_KEY|PASSWORD) with non-empty value
      # (but allow placeholder syntax: <something>, $VAR, ${VAR}, or "" empty)
      if echo "$content" | grep -qE '^[[:space:]]*export[[:space:]]+[A-Za-z_][A-Za-z0-9_]*_(KEY|SECRET|TOKEN|API_KEY|PASSWORD|PASS|CREDENTIAL)s?[[:space:]]*=[[:space:]]*[^<$"'"'"'[:space:]]'; then
        emit_hit "$current_file" "$current_added_line_no" "shell export of credential-named variable with non-placeholder value"
        continue
      fi
      # Pattern F: AWS-style 40-char secret on its own (heuristic; high false-positive rate, so only flag
      # in combination with an obvious context like AWS_SECRET= or aws_secret_access_key=)
      if echo "$content" | grep -qE '(aws_secret_access_key|AWS_SECRET[A-Z_]*)[[:space:]]*=[[:space:]]*[^<$"'"'"'[:space:]]{20,}'; then
        emit_hit "$current_file" "$current_added_line_no" "AWS secret access key context"
        continue
      fi
      ;;
  esac
done < <(git diff --cached --unified=0 2>/dev/null)

if [ "$hits" -gt 0 ]; then
  echo "" >&2
  echo "${RED}Commit refused: $hits secret-shape hit(s) in staged content.${NC}" >&2
  echo "" >&2
  echo "If a hit is a false positive (e.g., a fixture documenting a key SHAPE without a real value)," >&2
  echo "you can bypass with: ${YEL}git commit --no-verify${NC}" >&2
  echo "(But this is a strong signal to double-check the line in question first.)" >&2
  exit 1
fi

exit 0
