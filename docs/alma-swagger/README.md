# Alma API swagger reference snapshot

A committed, point-in-time copy of Ex Libris' machine-readable OpenAPI/swagger
definitions for the Alma REST API, one file per API domain. Use it as the
**source of truth** when verifying that `src/almaapitk/` calls the right
endpoints, verbs, parameters, request-body shapes, response keys, and error
codes — without a network round-trip.

## Provenance

| Field | Value |
|-------|-------|
| **Retrieved** | **2026-05-29** (per-file timestamps in each `*.fetched.json` sidecar) |
| **Source URL** | `https://developers.exlibrisgroup.com/wp-content/uploads/alma/openapi/<domain>.json` |
| **Fetched by** | `python -m scripts.error_codes.fetch_domain_codes <domain> --force --cache-dir docs/alma-swagger` |

Each `<domain>.json` is the raw swagger document; each `<domain>.fetched.json`
sidecar records the exact source URL and ISO fetch timestamp (swagger JSON has
no comment syntax, hence the sidecar).

## Domains included

`users`, `bibs`, `acq`, `conf`, `analytics`, `electronic`, `partners`, `courses`.

> `task-lists` is **not** included — Ex Libris returns HTTP 404 for its swagger
> file (the API has no published OpenAPI doc). The TaskLists coverage tickets
> (#70–#73) must verify against the live HTML docs instead.

Domain ⇄ source-file mapping is **not** 1:1 with `src/almaapitk/domains/`
filenames — see `DOMAIN_ALIASES` in `scripts/error_codes/fetch_domain_codes.py`.
Key aliases: `admin` + `configuration` → `conf`; `acquisition` → `acq`;
`resource_sharing` → `partners`; `bibliographic_records` → `bibs`.

## How to use it

List every endpoint a domain exposes:

```bash
python3 -c "import json; d=json.load(open('docs/alma-swagger/users.json')); \
  [print(v.upper(), p) for p,m in d['paths'].items() for v in m if v in ('get','post','put','delete','patch')]"
```

Inspect one endpoint's parameters / requestBody / responses:

```bash
python3 -c "import json; d=json.load(open('docs/alma-swagger/conf.json')); \
  import pprint; pprint.pprint(d['paths']['/almaws/v1/conf/sets/{set_id}'])"
```

Response envelopes often `$ref` an external schema (e.g.
`schemas/rest_set.json`); follow the URL to confirm a field's type. **Gotcha:**
numeric fields nested in `{value, link}` objects are typed `string`, not
integer (e.g. `rest_set.json` → `number_of_members.value`).

## Refreshing this snapshot

Re-run the fetcher against this directory and update the **Retrieved** date
above:

```bash
for d in users bibs acq conf analytics electronic partners courses; do
  python -m scripts.error_codes.fetch_domain_codes "$d" --force --cache-dir docs/alma-swagger >/dev/null
done
```

This is a *reference snapshot*, deliberately separate from
`scripts/error_codes/swagger_cache/` (the working cache the error-code harvester
reads). Refresh it whenever you do an API-contract audit so reviews compare
against current Alma behavior.

## History

- **2026-05-29** — initial snapshot, captured during the repo-wide API-contract
  audit that filed issues #162–#176 (+ comments on #139, #144).
