# Open tasks

Last updated: 2026-11-25

## PRs
- (none open in AlmaAPITK)

## Work in progress
- (none)

## Issues
- #211 (bump the consumers to 0.7.0) — owner: merge Alma-update-expired-users-emails PR #13 (main → prod), then close #211
- Leftover 0.7.0 bump issues Fetch_Alma_Analytics_Reports #19 and Update_Alma_Digital_Collections #12 (both repos done) — owner: OK to close?
- #250 (set members: guard when member list disagrees with set count) — triage, then fix
- #245 (check_pol_invoiced says not-invoiced when the search fails) — R10 fix, can do alone
- #244 (_extract_email_type misreads list-shaped email_type) — R10 fix, can do alone
- #243 (create_lending_request needs title even with mms_id) — R10 fix, can do alone
- #242 (create_lending_request wraps mms_id/requested_media wrongly) — R10 fix, can do alone
- #248 (docs follow-up: examples, py.typed, contributor notes, Lab guide) — can do alone
- #230 (Alma Lab) — phase 2 design: owner decides hypothesis-first vs. annotate-after
- #232 (failure-mode audit research) — not started
- Backlog: api-coverage and enhancement issues — see labels; no action now

## Other
- TAU-Alma-letters (7th consumer) has almaapitk 0.7.0 on `dev` only — reaches main/prod with its own release
- Owner: install updated Alma skills in WSL (claude-toolkit `./install-skills.sh`)
- "Loopholes with upstream consequences" issues filed 2026-11-10 in 13 repos — untouched
- Possible issue: `approve_invoice` is a misleading name for `op=process_invoice` — file?
