# Test-Recommendation Prompt — v1

You produce `chunks/<name>/test-recommendation.json` for one chunk. The schema is in spec §6.1.

## Construction rules

1. Read every AC line from each issue body literally.
2. Assign **at least one test.id per AC** in `acceptanceMapping`. If you cannot, list the AC under `unmappable[]` with a concrete reason.
3. Default `kind` to `smoke` (one read call) when in doubt. Only escalate to `round-trip` when the AC genuinely requires CRUD verification.
4. Every test with `stateChanging: true` MUST have a non-null `cleanup` block. **No exceptions** (R5).
5. Every fixture the test needs goes in `needsHumanInput[]` with: `key`, `description`, `example`. Be specific in `description` (`"existing user_primary_id with at least one active loan"` beats `"a user"`). The `example` MUST be a synthetic/placeholder value (e.g., `"tau000123"`, `"<user_primary_id>"`, `"9912345"`) — **never an actual operator-supplied identifier** (R9 in CLAUDE.md).
6. `pythonCalls` are exact Python statements. Use `${var}` for fixtures.
7. `passCriteria` are plain English; the test runner will turn each into a pytest assertion.
8. `endpoints` lists only the endpoints actually touched by `pythonCalls` (no aspirational "we should also test...").

## What to never do

- Invent tests for ACs you can't actually verify against SANDBOX. Use `unmappable[]` instead.
- Mark a test `stateChanging: false` to skip cleanup — the runner cross-checks endpoints; lying here is a hard breakpoint.
- Reuse a fixture key with a different description across tests. Fixtures are aggregated by `key`; conflicting descriptions confuse the operator.
- Suggest tests against PROD. Only SANDBOX (R8).
- Use a real operator-supplied identifier in any field of the JSON file (R9). Synthetic placeholders only.

## Output

Write the JSON file. Return: `{ "path": "chunks/<name>/test-recommendation.json", "summary": "<brief>" }`.
