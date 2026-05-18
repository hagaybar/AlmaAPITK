#!/usr/bin/env bash
# install-git-hooks.sh — wire up the project's git hooks for the current clone.
#
# Run once per clone:
#   bash scripts/install-git-hooks.sh
#
# Idempotent. Backs up any existing hook before replacing.

set -eu

repo_root="$(git rev-parse --show-toplevel)"
hooks_dir="$repo_root/.git/hooks"

mkdir -p "$hooks_dir"

# If the user has a global core.hooksPath override, our per-repo hook will be
# ignored by git. Set a per-repo override so .git/hooks/ is honored here.
# This does NOT affect any other repository.
current_path="$(git config --local --get core.hooksPath 2>/dev/null || true)"
if [ "$current_path" != ".git/hooks" ]; then
  git config --local core.hooksPath .git/hooks
  echo "  ✓ per-repo core.hooksPath set to .git/hooks (overrides any global setting for this clone only)"
fi

# pre-commit: secret-shape scanner
pre_commit_target="$hooks_dir/pre-commit"
if [ -e "$pre_commit_target" ] && ! [ -L "$pre_commit_target" ]; then
  backup="$pre_commit_target.backup-$(date +%Y%m%d-%H%M%S)"
  mv "$pre_commit_target" "$backup"
  echo "  Existing pre-commit hook backed up to: $backup"
fi
rm -f "$pre_commit_target"
cat > "$pre_commit_target" <<'EOF'
#!/usr/bin/env bash
# Auto-installed by scripts/install-git-hooks.sh.
# Refuses commits containing likely secret values.
set -e
repo_root="$(git rev-parse --show-toplevel)"
exec "$repo_root/scripts/check-secrets-in-staged.sh"
EOF
chmod +x "$pre_commit_target"

chmod +x "$repo_root/scripts/check-secrets-in-staged.sh"
chmod +x "$repo_root/scripts/env-status"

echo "  ✓ pre-commit hook installed at: $pre_commit_target"
echo "  ✓ scripts/check-secrets-in-staged.sh executable"
echo "  ✓ scripts/env-status executable"
echo ""
echo "Test it: stage a fake credential-shape line and try to commit — the hook should refuse."
