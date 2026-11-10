# Raw requests

`AlmaAPIClient.raw_request()` calls any Alma REST path, including endpoints almaapitk
does not wrap yet. It is a **bridge until typed coverage lands**: when a typed domain
method exists, use it. Planned coverage is tracked in the repository's `api-coverage`
issues.

```python
from almaapitk import AlmaAPIClient, AlmaAPIError

with AlmaAPIClient("SANDBOX") as client:
    resp = client.raw_request("GET", "almaws/v1/courses", params={"limit": 50})
    for course in resp.data.get("course", []):
        print(course["code"]["value"])

    # Collections: page with iter_paged, which accepts any path.
    for course in client.iter_paged("almaws/v1/courses", record_key="course"):
        ...

    try:
        client.raw_request("POST", "almaws/v1/courses",
                           data={"code": {"value": "<course_code>"}, "name": "Example"})
    except AlmaAPIError as exc:
        print(exc.status_code, exc.alma_code, exc.tracking_id)
```

## What you get

`raw_request` runs through the same engine as `get`/`post`/`put`/`delete`:

- the `Authorization: apikey` header, from `ALMA_SB_API_KEY` / `ALMA_PROD_API_KEY` (never logged);
- region and base-URL resolution, SANDBOX vs PRODUCTION;
- the pooled session, and a clear error after `close()`;
- redacted request/response logging;
- the typed errors from [Error Handling](error-handling.md), identical to a typed call.

## What you do not get

- No request-body validation or required-field checks.
- No typed or normalised results: you receive Alma's raw payload.
- No stability promise from almaapitk: you couple to Alma's own compatibility.
- No pagination: use `iter_paged(endpoint, record_key=...)`.

## Rules and gotchas

- `method` is `GET`, `POST`, `PUT` or `DELETE` (any case). `endpoint` is a path relative to
  the base URL; an absolute URL is refused. Both checks run before anything is sent.
- `content_type="application/xml"` also sends `Accept: application/xml`. Alma then answers
  in XML, so `.data` / `.json()` fail; read `.text()`.
- Check paths, parameters and body shapes against the swagger snapshot in
  `docs/alma-swagger/` (TaskLists has no published swagger).
- Domains without typed methods yet (for example Courses and TaskLists) are reached this way
  until their typed methods land.
