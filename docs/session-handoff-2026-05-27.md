# Session handoff — Consumer-safety testing rollout (2026-05-27)

**Read this first next session.** It's the single entry point for the
"automated testing of almaapitk version bumps" initiative. Deeper detail is
in the spec, plan, and meta-issue linked below; persistent memory points here.

## 1. The goal (why this exists)

Bumping `almaapitk` in a production consumer is risky and, today, validated by
**manually re-running every workflow on the `masedet` Windows box** — slow, and
worse, a bad bump on a **scheduled** repo fails *silently* in prod. We're
building a **repeatable, layered testing process** that catches client changes
that would break consumers as early/cheaply as possible, and gradually replaces
the manual masedet check with automated ones.

## 2. The strategy — 3 test layers + 1 shared infra (canonical model)

| | Answers | Lives in | Runs |
|---|---|---|---|
| **Infra (plumbing)** | *(toolkit)* build-client, read-only rail, dry-run, flaky-tolerance, `@workflow`/`alma` fixture | `almaapitk[smoke]` | — |
| **L1 — Contract tests** | "did almaapitk change a behaviour consumers rely on?" | `almaapitk` (all consumers) | every almaapitk change |
| **L2 — Mock/golden** | "did *this repo's* logic / its almaapitk integration regress?" | each repo | every commit, offline |
| **L3 — Live smoke** | "does it genuinely still work against real Alma?" (the masedet replacement) | each repo (uses Infra) | before a bump / scheduled |

Mocked layers (L1/L2) are a fast regression net; only **L3** has live certainty.
Full design + invariants (R-H1..R-H6) + the per-repo onboarding playbook:
`docs/superpowers/specs/2026-05-25-workflow-smoke-harness-design.md`.
Tracking: **meta-issue #158**.

## 3. Status

**Done (in almaapitk, on `main`):**
- **Infra** — `src/almaapitk/testing/` + `[smoke]` extra (PR #159, #156). Read-only rail, dry-run recorder, flaky-tolerance, `@workflow` marker + `alma` fixture, `make smoke`. **Shipped on main but UNRELEASED** (not in PyPI 0.4.5).
- **L1 Analytics contract tests** — `tests/unit/contracts/test_analytics_contract.py` (#160). Pins the Analytics surface (sized-list return, kwargs, error types, limit bounds).
- **Earlier-session security work, also unreleased / bound for 0.5.0:** #142 (PII redaction + safe logging defaults), #143 (`api_key=` ctor + `CredentialError`). CI guards #150/#151 (wheel/sdist contents + bandit) merged via #155.
- **Management dashboard** — `docs/manual-qa/` (see §6).

**Done (pilot repo = `Fetch_Alma_Analytics_Reports`, the first consumer):**
- L2 mock/golden already existed (`tests/test_diff_harness.py`).
- **L3 live smoke** — `tests/test_live_smoke.py` (opt-in `RUN_LIVE_SMOKE=1`, read-only PROD).
- **`scripts/full_fetch_check.py`** — full-volume timing check for any task.
- **Validated 0.4.5**: live smoke passed + full ~15k-row biggest report (`e_titles_for_usage`) fetched with no timeout.
- **Promoted**: analytics `main` → `prod` (fast-forward; lock pins almaapitk 0.4.5).

**✅ Analytics consumer CLOSED (2026-05-28):**
- **masedet prod activation confirmed** — operator ran `git pull` in the prod folder (already up to date; `main`/`prod` both at `25fc206`) and the scheduled reports downloaded flawlessly. The analytics pilot is fully done.

**🚧 GATE NOW OPEN (2026-05-28) — repo-wide feature freeze.** Until the remaining four consumer repos are bumped to the current released `almaapitk` and verified (this initiative, meta #158), all `enhancement` + `api-coverage` work in the toolkit is blocked (GitHub label `blocked:consumer-rollout` on 51 issues; only `priority:high`/production bugs proceed). Enforced by `CLAUDE.md` **R11** (session-start gate) + the board banner. Next repo: **Alma-RS-lending-request-automation**.

## 4. The production consumer repos

S = scheduled (unattended → prioritize), M = manual (you're the backstop). All but analytics are **mutating** (their L3 needs create-then-cleanup).

| Repo (local name) | Run | I/O | Status |
|---|---|---|---|
| Fetch_Alma_Analytics_Reports | S | read-only | **✅ DONE 2026-05-28** (0.4.5 validated + promoted + masedet prod verified — reports downloading) |
| Alma-RS-lending-request-automation | S | mutating | not started — **next** |
| Update_Alma_Digital_Collections *(prod name: Update_Digital_Collections)* | S | mutating | not started |
| Alma-Digital-Upload | M | mutating | not started |
| Alma-update-expired-users-emails | M | mutating | not started |

## 5. The plan / next steps (prioritized)

1. **Close the analytics last mile** — confirm masedet prod is on 0.4.5 and the first scheduled run was clean. Rollback if not (see §7).
2. **Decide the mutating-repo path.** All four remaining repos mutate, so their L3 smokes need the **deferred "mutation + teardown"** machinery, and probably the **released harness**. Two gates to resolve:
   - Build the **mutation + teardown** Infra (create test record → verify → delete; PROD stays read-only, so this runs in SANDBOX).
   - **Release almaapitk 0.5.0** (harness + #142/#143) so repos can `pip install almaapitk[smoke]` — OR keep per-repo L3 self-contained (analytics did, no harness needed). Decide per the build-by-extraction rule (R-H1: only adopt the harness where it earns its keep).
3. **Run the per-repo playbook** on the scheduled repos first (RS-lending, then Update_Alma_Digital_Collections): audit usage → add L1 contract tests in almaapitk → ensure L2 → add L3 live smoke + `full_fetch_check` → `main→prod` → masedet activate.
4. **Housekeeping (open):** promote CI guards #150/#151 to *required* checks after a release cycle; fix the pre-existing `Electronic` export meta-categorisation test; the `chunks/electronic-bootstrap/` untracked dir.

## 6. Resuming the dashboard

`docs/manual-qa/` — local board to organize the work + chat with Claude from the browser (pattern cloned from `primo_maps`).
```bash
python3 docs/manual-qa/qa-server.py      # NOT `python` — this env has only python3
```
Open <http://localhost:8765/>. Click **💬 Ping Claude** on a card → Claude side runs `bash docs/manual-qa/qa-watch.sh` (waits for a ping) and replies with `bash docs/manual-qa/qa-reply.sh <testId> <level> <text>`. The board hydrates from the server on load (Claude's marks/status win), collapses reply history to the latest message, and shows a "your next step" panel. Analytics steps are marked done; next-step points at RS-lending.

> The server/watcher started this session die when the session ends — just restart `qa-server.py` next time.

## 7. Key learnings & gotchas (these cost real time this session)

- **masedet is Windows / PowerShell, NOT WSL.** Repo at `D:\Scripts\DevSandbox\Fetch_Alma_Analytics_Reports` (dev) + a prod folder tracking the `prod` branch. Commands there must be PowerShell (`$env:VAR="…"`, `;` not `&&`), and tests run with `poetry run pytest <file>` — **`python <file.py>` runs nothing**.
- **Deploy mechanism (per repo):** `main` (dev) → fast-forward merge into `prod` → masedet prod folder `git pull` + `poetry install` (picks up the pinned almaapitk from the committed lock). Rollback: reset `prod` to prior SHA + `--force-with-lease` push, then masedet `git pull` + `poetry install`. (Analytics prod anchor before promotion was `ed730a3`.)
- **API-key gotcha:** an interactive PowerShell / VS Code terminal can carry a **stale/wrong `ALMA_PROD_API_KEY`** (different from the Windows-defined one). Fix: open a fresh terminal, or `$env:ALMA_PROD_API_KEY=[Environment]::GetEnvironmentVariable("ALMA_PROD_API_KEY","Machine")`. The smoke now guards against the conftest fake-placeholder key.
- **0.4.5 behaviour change to watch:** default request timeout dropped **300s → 60s**. Validated OK on the biggest report, but it's the one version-specific risk for slow/large fetches across other repos — `full_fetch_check.py` exists to test it.
- **Analytics is PRODUCTION-only + read-only.** All other consumer workflows mutate.
- masedet has permission tangles (locked `%TEMP%\pytest-of-*` and `.pytest_cache`) — the smoke makes its own tempdir and we run with `-p no:cacheprovider`.

## 8. Where everything lives

- Strategy spec: `docs/superpowers/specs/2026-05-25-workflow-smoke-harness-design.md`
- Plan: `docs/superpowers/plans/2026-05-25-workflow-smoke-harness.md`
- Meta-issue: **#158** (children: #156 infra ✓, #157 L3 analytics, #160 L1 analytics ✓)
- Harness: `src/almaapitk/testing/`  |  L1 contract tests: `tests/unit/contracts/`
- Dashboard: `docs/manual-qa/`
- Pilot repo (separate, GitHub `hagaybar/Fetch_Alma_Analytics_Reports`): `tests/test_live_smoke.py`, `scripts/full_fetch_check.py`, `docs/almaapitk-0.4.5-audit.md`
- Persistent memory: `project-consumer-safety-testing-rollout` (points back here)
