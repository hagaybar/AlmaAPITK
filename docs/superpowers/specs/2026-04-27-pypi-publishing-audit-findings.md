# Pre-Publish Audit Findings — almaapitk 0.3.0

**Date run:** 2026-04-27
**Tools:** ruff, bandit, vulture, grep, manual review of public API
**Source under review:** `src/almaapitk/`

## 🔴 Block publish (must fix before any upload)

Items in this section are hard blockers. Each line below should describe one specific finding with file:line and a brief note on why it blocks publish.

**None found.**

(Audit verification: zero hits in `/tmp/audit-identifying.txt` for institution identifiers, hostnames, or contact emails inside `src/almaapitk/`. Bandit reported zero High-severity findings. No hardcoded API keys, tokens, or passwords were detected — bandit's B105 did not fire. The package contains zero non-Python files inside `src/almaapitk/` — `find -type f ! -name '*.py'` returned empty, so there are no stray fixtures or data files at risk of shipping.)

## 🟡 Should fix (fix unless reason to defer)

- **`src/almaapitk/domains/users.py:482` — `process_users_batch(..., max_workers: int = 5)` parameter is declared and documented as "Maximum concurrent processing (respect rate limits)" but never used; execution is sequential.** Vulture flags this at 100% confidence. This is a real public-API contract bug: consumers of the wheel will pass `max_workers` and get no concurrency. Either implement concurrency or drop the parameter and adjust the docstring before shipping a public release.
- **5 bare `except:` clauses in `src/almaapitk/client/AlmaAPIClient.py`** — lines 147, 186, 250, 311, 434 (ruff E722). All swallow every exception type including `KeyboardInterrupt` / `SystemExit`. Should be `except (ValueError, json.JSONDecodeError):` (or similar) with re-raise where appropriate.
- **1 bare `except:` clause in `src/almaapitk/domains/acquisition.py:1743`** (ruff E722). Same concern as above.
- **6 `requests` calls without `timeout=` in `src/almaapitk/client/AlmaAPIClient.py`** — lines 180 (GET), 238 / 241 (POST), 299 / 302 (PUT), 347 (DELETE). Bandit B113 Medium severity. A consumer hitting a hung Alma endpoint will block forever. Add a default timeout (60s suggested).
- **272 stray `print()` calls inside the package source**, distributed:
  - `src/almaapitk/domains/acquisition.py` — 152
  - `src/almaapitk/utils/tsv_generator.py` — 49
  - `src/almaapitk/domains/admin.py` — 33
  - `src/almaapitk/client/AlmaAPIClient.py` — 14
  - `src/almaapitk/domains/users.py` — 13
  - `src/almaapitk/utils/citation_metadata.py` — 6
  - `src/almaapitk/domains/resource_sharing.py` — 5

  This violates the project's own CLAUDE.md standard ("use almaapitk.alma_logging framework — never print statements"). Consumers of the wheel will see these prints on their stdout whether they want them or not. Not a security blocker but a real UX/standards drift for a publishable library.
- **Swallowed `except Exception as e:` pattern across domain code (~31 of 57 instances do not re-raise)**, breaking the documented `AlmaAPIError` contract:
  - acquisition.py: 17 clauses, 10 do not re-raise
  - admin.py: 11 clauses, 7 do not re-raise
  - users.py: 8 clauses, 6 do not re-raise
  - bibs.py: 2 clauses, 1 does not re-raise (line 822 returns `[]` from `get_marc_subfield` — defensible)
  - analytics.py: 2 clauses, both re-raise — clean
  - resource_sharing.py: 1 clause, re-raises — clean

  These silent failures should either be narrowed to specific exception types or documented as intentional (e.g., a listing method that wants to return `[]` on failure).
- **16 TODO comments in `src/almaapitk/alma_logging/`** — all marked "Phase 1.1" / "Phase 1.3" referring to features the logging module advertises but does not implement (recursive redaction for nested dicts/lists, file-loading error handling, date-based log file switching, parent directory creation, configuration saving). See `/tmp/audit-todo.txt` for the full list. Should either implement, gate behind a feature flag, or remove the unimplemented entry points before shipping.
- **`F401` unused imports in package source** (will be visible to anyone running ruff against the wheel):
  - `src/almaapitk/alma_logging/formatters.py:19` — `typing.Dict`
  - `src/almaapitk/alma_logging/logger.py:24` — `typing.Optional`, `typing.Any`
  - `src/almaapitk/client/AlmaAPIClient.py:8` — `json`
  - `src/almaapitk/client/AlmaAPIClient.py:9` — `typing.List`
  - `src/almaapitk/domains/acquisition.py:8` — `AlmaResponse`
  - `src/almaapitk/domains/users.py:12` — `datetime.timedelta` (also flagged by vulture)
  - `src/almaapitk/utils/tsv_generator.py:11` — `typing.Optional`
- **`F811` redefinition in `src/almaapitk/client/AlmaAPIClient.py:21`** — module-level `import json` (line 8) is shadowed by `def json(self)` method on `AlmaResponse`. The method is the real intent; remove the unused module import.
- **`F841` unused local assignments**:
  - `src/almaapitk/domains/acquisition.py:1833` — `receive_result = self.receive_item(...)` assigned and never read.
  - `src/almaapitk/utils/tsv_generator.py:138` — `column_name = column.get('name', 'Unknown')` assigned and never read.

## 🟢 FYI (style nits, opinions)

- **30 ruff F541 (f-string without placeholders)** across `acquisition.py`, `admin.py`, and `tsv_generator.py`. Pure style — `f"text"` should be `"text"`. ruff `--fix` handles all 30 automatically. Examples: `acquisition.py:395, 558, 560, 947, 995, 1586, 1588, 1592, 1600, 1619, 1827, 1842`; `admin.py:622, 627, 635, 649, 657, 702, 726, 750, 751`; `tsv_generator.py:106, 239, 257, 279, 290, 296, 307, 418, 422`.
- **6 bandit B314 `xml.etree.ElementTree.fromstring` warnings** at `acquisition.py:1748`, `analytics.py:129`, `analytics.py:269`, `bibs.py:31`, `bibs.py:128`, `bibs.py:169`, `bibs.py:252`, `citation_metadata.py:126` (8 hits in audit, deduped above to the unique call sites). The XML source is the trusted Alma endpoint, not arbitrary user input, so practical XXE / billion-laughs risk is low. Could swap to `defusedxml.ElementTree` for defense-in-depth or document the trust boundary.
- **Vulture 90%-confidence finding**: `src/almaapitk/domains/users.py:12` unused import `timedelta` — duplicates the ruff F401 finding above; mentioned here only because vulture surfaced it independently.
- **`example_user_set_workflow()` (admin.py:594) and `example_workflow()` (users.py:636)** lack docstrings, but both live inside `if __name__ == "__main__":` blocks and are dead code at import time — not part of the public API surface. Mentioned for completeness only.

## Tool output excerpts

### ruff
```
F401 [*] `typing.Dict` imported but unused
  --> src/almaapitk/alma_logging/formatters.py:19:25
   |
17 | import logging
18 | import json
19 | from typing import Any, Dict, Optional
   |                         ^^^^
20 | from datetime import datetime, timezone
   |
help: Remove unused import: `typing.Dict`

F401 [*] `typing.Optional` imported but unused
  --> src/almaapitk/alma_logging/logger.py:24:20
   |
22 | import logging
23 | import sys
24 | from typing import Optional, Dict, Any
   |                    ^^^^^^^^

F401 [*] `typing.Any` imported but unused
  --> src/almaapitk/alma_logging/logger.py:24:36

F401 [*] `json` imported but unused
  --> src/almaapitk/client/AlmaAPIClient.py:8:8

F401 [*] `typing.List` imported but unused
  --> src/almaapitk/client/AlmaAPIClient.py:9:48

F811 Redefinition of unused `json` from line 8
  --> src/almaapitk/client/AlmaAPIClient.py:21:9
[... 41 more findings ...]

Found 47 errors.
[*] 38 fixable with the `--fix` option (2 hidden fixes can be enabled with the `--unsafe-fixes` option).
```

Aggregate: 47 findings — 30x F541, 8x F401, 6x E722, 2x F841, 1x F811. Full content: `/tmp/audit-ruff.txt`.

### bandit
```
Run started:2026-04-27 12:48:53.381066+00:00

>> Issue: [B113:request_without_timeout] Call to requests without timeout
   Severity: Medium   Confidence: Low
   Location: src/almaapitk/client/AlmaAPIClient.py:180:19
        response = requests.get(url, headers=headers, params=params)

>> Issue: [B113:request_without_timeout]
   Location: src/almaapitk/client/AlmaAPIClient.py:238:23
        response = requests.post(url, headers=headers, json=data, params=params)

>> Issue: [B113:request_without_timeout]
   Location: src/almaapitk/client/AlmaAPIClient.py:241:23

>> Issue: [B113:request_without_timeout]
   Location: src/almaapitk/client/AlmaAPIClient.py:299:23

>> Issue: [B113:request_without_timeout]
   Location: src/almaapitk/client/AlmaAPIClient.py:302:23

>> Issue: [B113:request_without_timeout]
   Location: src/almaapitk/client/AlmaAPIClient.py:347:19

>> Issue: [B314:blacklist] Using xml.etree.ElementTree.fromstring to parse untrusted XML data ...
   Severity: Medium   Confidence: High
   Location: src/almaapitk/domains/acquisition.py:1748:27
   Location: src/almaapitk/domains/analytics.py:129:19
   Location: src/almaapitk/domains/analytics.py:269:19
   Location: src/almaapitk/domains/bibs.py:31:19
   Location: src/almaapitk/domains/bibs.py:128:12
   Location: src/almaapitk/domains/bibs.py:169:12
   Location: src/almaapitk/domains/bibs.py:252:23
   Location: src/almaapitk/utils/citation_metadata.py:126:15

Run metrics:
    Total issues (by severity): Undefined: 0  Low: 4  Medium: 14  High: 0
    Total issues (by confidence): Undefined: 0  Low: 6  Medium: 0  High: 12
```

Aggregate: 14 Medium severity (6x B113, 8x B314), 0 High. Full content: `/tmp/audit-bandit.txt`.

### vulture (min-confidence 70)
```
src/almaapitk/domains/users.py:12: unused import 'timedelta' (90% confidence)
src/almaapitk/domains/users.py:482: unused variable 'max_workers' (100% confidence)
```

### grep
- `TODO/FIXME/XXX/HACK` lines in /tmp/audit-todo.txt: **16**
- `print()` lines in /tmp/audit-print.txt: **272**
- Identifying-info lines in /tmp/audit-identifying.txt: **0**

#### TODO/FIXME/XXX/HACK lines (verbatim from `/tmp/audit-todo.txt`)
```
src/almaapitk/alma_logging/config.py:118:        # TODO: Phase 1.3 - Implement file loading with error handling
src/almaapitk/alma_logging/config.py:119:        # TODO: Phase 1.3 - Validate configuration structure
src/almaapitk/alma_logging/config.py:120:        # TODO: Phase 1.3 - Merge with defaults for missing keys
src/almaapitk/alma_logging/config.py:221:        # TODO: Phase 1.3 - Implement configuration saving
src/almaapitk/alma_logging/config.py:222:        # TODO: Phase 1.3 - Pretty-print JSON with indentation
src/almaapitk/alma_logging/handlers.py:49:        # TODO: Phase 1.1 - Create parent directories if they don't exist
src/almaapitk/alma_logging/handlers.py:94:        # TODO: Phase 1.1 - Implement date-based file switching
src/almaapitk/alma_logging/handlers.py:95:        # TODO: Phase 1.1 - Integrate with rotating file handler
src/almaapitk/alma_logging/handlers.py:104:        # TODO: Phase 1.1 - Check if date has changed
src/almaapitk/alma_logging/handlers.py:105:        # TODO: Phase 1.1 - Create new handler if needed
src/almaapitk/alma_logging/handlers.py:106:        # TODO: Phase 1.1 - Delegate to current handler
src/almaapitk/alma_logging/handlers.py:148:    # TODO: Phase 1.1 - Create all standard log directories
src/almaapitk/alma_logging/formatters.py:213:    # TODO: Phase 1.1 - Implement recursive redaction for dicts
src/almaapitk/alma_logging/formatters.py:214:    # TODO: Phase 1.1 - Implement recursive redaction for lists
src/almaapitk/alma_logging/formatters.py:215:    # TODO: Phase 1.1 - Handle nested structures
src/almaapitk/alma_logging/formatters.py:216:    # TODO: Phase 1.1 - Case-insensitive pattern matching
```

#### `print()` distribution (count per file; full file:line list in `/tmp/audit-print.txt`, 272 lines total)
```
152  src/almaapitk/domains/acquisition.py
 49  src/almaapitk/utils/tsv_generator.py
 33  src/almaapitk/domains/admin.py
 14  src/almaapitk/client/AlmaAPIClient.py
 13  src/almaapitk/domains/users.py
  6  src/almaapitk/utils/citation_metadata.py
  5  src/almaapitk/domains/resource_sharing.py
```

First 30 lines of `/tmp/audit-print.txt` (representative sample):
```
src/almaapitk/utils/tsv_generator.py:65:                print(f"✓ Using direct TSV input: {tsv_path}")
src/almaapitk/utils/tsv_generator.py:72:                print(f"✓ Using Alma set ID: {input_config['alma_set_id']}")
src/almaapitk/utils/tsv_generator.py:81:            print(f"✓ Configuration loaded successfully from {self.config_path}")
src/almaapitk/utils/tsv_generator.py:93:            print(f"Initializing Alma API client for {environment} environment...")
src/almaapitk/utils/tsv_generator.py:106:            print(f"✓ Alma API clients initialized successfully")
src/almaapitk/utils/tsv_generator.py:115:        print(f"Retrieving MMS IDs from Alma set: {set_id}")
src/almaapitk/utils/tsv_generator.py:119:            print(f"✓ Retrieved {len(mms_ids)} MMS IDs from set {set_id}")
src/almaapitk/utils/tsv_generator.py:159:        print(f"✓ Output directory ready: {output_path}")
src/almaapitk/utils/tsv_generator.py:187:        print(f"Writing TSV file: {full_path}")
src/almaapitk/utils/tsv_generator.py:188:        print(f"Processing {len(mms_ids)} records...")
src/almaapitk/utils/tsv_generator.py:198:        print(f"  ✓ Headers written: {headers}")
src/almaapitk/utils/tsv_generator.py:207:        print(f"  Processed {i}/{len(mms_ids)} records...")
src/almaapitk/utils/tsv_generator.py:209:        print(f"✓ TSV file created successfully: {full_path}")
src/almaapitk/utils/tsv_generator.py:210:        print(f"  Total records: {len(mms_ids)}")
src/almaapitk/utils/tsv_generator.py:211:        print(f"  Columns: {len(self.config['columns'])}")
src/almaapitk/utils/tsv_generator.py:239:        print(f"✓ TSV file validation passed")
src/almaapitk/utils/tsv_generator.py:240:        print(f"  Data rows: {actual_data_rows}")
src/almaapitk/utils/tsv_generator.py:241:        print(f"  Columns per row: {expected_columns}")
src/almaapitk/utils/tsv_generator.py:257:        print(f"\n=== TSV Generation Started ===")
src/almaapitk/utils/tsv_generator.py:258:        print(f"Config file: {self.config_path}")
src/almaapitk/utils/tsv_generator.py:279:        print(f"\n=== TSV Generation Completed Successfully ===")
src/almaapitk/utils/tsv_generator.py:280:        print(f"Output file: {tsv_path}")
src/almaapitk/utils/tsv_generator.py:285:        print(f"\n✗ TSV Generation Failed: {e}")
src/almaapitk/utils/tsv_generator.py:290:        print(f"\n=== Configuration Preview ===")
src/almaapitk/utils/tsv_generator.py:291:        print(f"Config file: {self.config_path}")
src/almaapitk/utils/tsv_generator.py:292:        print(f"Alma Set ID: {self.config['input']['alma_set_id']}")
src/almaapitk/utils/tsv_generator.py:293:        print(f"Environment: {self.config['input']['environment']}")
src/almaapitk/utils/tsv_generator.py:294:        print(f"Number of columns: {len(self.config['columns'])}")
src/almaapitk/utils/tsv_generator.py:296:        print(f"\nColumns:")
src/almaapitk/utils/tsv_generator.py:302:        print(f"  {i}. {name}: [MMS IDs from Alma set]")
```

#### Identifying-info lines
No findings (`/tmp/audit-identifying.txt` is empty — 0 lines).

### Manual review notes

- Public API surface (`__init__.py`) is well-organized: lazy imports via `_lazy_imports` table; clean `__all__`; explicit migration notes. `__version__` is currently `"0.2.0"` (will be bumped to `"0.3.0"` by Task 1.2 of the publish plan; out of scope here).
- All listed `__all__` symbols resolve to existing modules; no obviously private-looking exports.
- Each domain class has class-level + method-level docstrings on its public surface. No public methods missing docstrings.
- All public method signatures examined have type hints on parameters and return values (`Dict[str, Any]`, `List[str]`, `Optional[...]`, `AlmaResponse`, etc.).
- No mutable default arguments (no `=[]` or `={}` in any public def signature anywhere in the package).
- `acquisition.py` (28 public methods, 2371 lines): docstrings + type hints present. 152 stray `print()` calls. 1 bare `except:` at line 1743. 17 `except Exception as e:` clauses, 10 do not re-raise.
- `admin.py` (8 public methods, 759 lines): docstrings + type hints present. `example_user_set_workflow()` at line 594 has no docstring but lives inside `if __name__ == "__main__":` so it is dead code at import time. 11 `except Exception as e:` clauses, 7 do not re-raise.
- `analytics.py` (2 public methods + `__init__`, 300 lines): clean — type hints, docstrings, both `except` clauses re-raise as `AlmaAPIError`. Uses `xml.etree.ElementTree.fromstring` (bandit B314); XML source is the trusted Alma Analytics endpoint, so practical risk is low.
- `bibs.py` (20 public methods, 824 lines): clean. No bare `except`. 2 `except Exception as e:` clauses, 1 returns `[]` from `get_marc_subfield` (line 822), defensible.
- `resource_sharing.py` (4 public methods, 631 lines): clean. 1 `except Exception as e:` clause that re-raises after logging.
- `users.py` (14 public methods, 690 lines): docstrings + type hints present. `example_workflow()` at line 636 inside `if __name__ == "__main__":`, same as admin.py. **BUG**: `process_users_batch` (line 481) declares `max_workers: int = 5` but never uses it — vulture-confirmed misleading public API contract. 8 `except Exception as e:` clauses, 6 do not re-raise.
- Bare `except:` clauses in `client/AlmaAPIClient.py` (5 instances) and `acquisition.py` (1 instance) — flagged by ruff E722.
- Logging vs print: domain code mixes `self.logger.info(...)` with `print(...)` in many spots (most heavily in `acquisition.py`). Project's own CLAUDE.md says "use `almaapitk.alma_logging` framework (never `print` statements)". Consumers of the wheel will see these prints on their stdout whether they want them or not.
- No real institution identifiers (TAU, `library@example.com`, internal hostnames) found in package source by grep — clean.
- No hardcoded API keys, tokens, or password-like strings spotted. Bandit's "B105 hardcoded_password" did not fire.
