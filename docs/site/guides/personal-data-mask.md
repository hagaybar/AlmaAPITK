# Personal-data mask

almaapitk has **one** mask for personal data (issue #256, building on #142). The
library uses it on everything it writes or shows, and consumers use the same two
functions on their own output, so there is one field list and one set of rules.

## The rule: raw in memory, masked when written

- **In memory**, data stays raw. Every method returns the real record, so you can
  look up a user and then create a request for them. `redact()` returns a copy and
  never changes its argument.
- **Written anywhere** (logs, the terminal, files, error messages, reports, and so an
  agent's transcript), personal data is masked.

## What is masked

Masking is by Alma **field name**: a value alone (an ID is just a number) cannot say
whether it is personal.

| Data | Fields (examples) | Shown as |
|------|-------------------|----------|
| Credentials | `apikey`, `authorization`, `password`, `token`, `secret` | `***REDACTED***` |
| Names, contact details | `first_name`, `last_name`, `full_name`, `phone*`, `birth_date`, `gender`; by exact name: `email`, `email_address`, `address`, `line1`, `city`, `postal_code`, and the lending request's `text_email`, `text_postal_1`..`text_postal_4` | `<redacted>` |
| Staff names in records | `created_by`, `updated_by`, `last_modified_by`, `approved_by` (invoice), `operator`, `assignee` | `<redacted>` |
| Free-text notes | `note`, `notes`, `note_text`, `user_note`, `rs_note`, `receiving_note`, `vendor_note`, `renewal_note`, `cancellation_restriction_note`, `internal_note_1` | `<redacted>` |
| User identifiers | `primary_id`, `user_id`, `user_primary_id`, `requester` (id; its `desc`, the name, is blanked), each `user_identifier` value (barcode and others), `users/<id>` in a path | last 3 characters: `<...>789` |

In free text (a log message, an error message) the mask also catches these fields
written as JSON, Python `repr`, XML or `key=value`, user IDs after the singular words
*user*, *patron* or *requester* (and Alma's "User with identifier X"), and every email
address. Plurals are read as counts (`users: 1500`), a date after the word stays, and a
bare "identifier" (an MMS ID) stays.

**Stays visible:** patron-typed request text (`comment`, `citation_note`), record
identifiers that are not personal (MMS, POL, invoice, set IDs), codes, statuses,
dates, titles, flags such as `popup_note: false`, fields that only contain the words
(`ip_address`, `email_template`), and a standard number in an `{id_type, value}` object
(ISSN, ISBN): only a user identifier (under `user_identifier`, or carrying
`segment_type`) is masked.

The list lives in `src/almaapitk/redaction.py`; change it there and every path follows.

## Where the library uses it

- Logging: the toolkit's text and JSON formatters, and a filter on every `almapi.*`
  logger, so a handler you attach yourself (or Python's last-resort stderr handler)
  also gets masked messages, context fields and tracebacks.
  A malformed `%`-style call never raises into your job: the record goes through with
  template and arguments masked separately, and Python prints its usual
  "--- Logging error ---".
- Errors: `str()` and `repr()` of `AlmaAPIError`, `AlmaValidationError` and all their
  subclasses, and therefore tracebacks. `exc.args[0]` keeps the raw message;
  `repr(exc)` shows the masked message only. A `requests` error the client chains
  (`__cause__`) or re-raises (a connection error) is a masked copy of the same type, so
  the traceback's "direct cause" block is masked too and `except
  requests.ConnectionError` still matches.
- Error strings placed in returned dicts (`result['error']` in some `Users` and `Admin`
  methods) come from `str(exc)`, so they are masked. The returned *data* stays raw.
- `repr()` of `AlmaResponse` (status only), `AlmaAPIClient` (environment only), and
  of the Alma Lab and testing records that carry request or response data.
- Alma Lab **files**: evidence records and `--baseline-out` files are written masked.
  On screen (the CLI's terminal output and the full-screen app) the Lab stays raw: the
  owner needs to see and type real data there. A masked value can never be sent back:
  the Lab refuses a body, path or input holding `<redacted>` / `<...>`, and a saved
  baseline that holds personal data cannot start an update (load the current record in
  the app instead).

## Using it in a consumer

```python
from almaapitk import Users, redact, redact_text

user = users.get_user(user_primary_id)          # raw: use it for the next call
logger.info("user fetched", user=redact(user))  # masked copy for the log
print(redact_text(f"no email for {user_primary_id}: {message}"))
```

Pass every line you print and every row you write to a file or report through
`redact` / `redact_text`, and replace any local mask with these (one repo at a time,
through that repo's own issue).

## The one exception: report files on masedet

A job that genuinely needs real identifiers in its **report file** may write them
**only on masedet** (Prod and DevSandbox): it is not exposed and only a human operator
uses it. Never in logs, never in the sandbox or on WSL. Masking a report is the
default; leaving it raw is a deliberate, per-job choice.
