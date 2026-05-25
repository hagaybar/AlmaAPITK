# Workflow smoke tests (issue #156/#157). Friendly wrappers over pytest so
# "validate this version" is one command.
.PHONY: smoke smoke-live

# Dry-run only (no credentials needed): validates each workflow's wiring.
smoke:
	poetry run python -m pytest tests/smoke/ -q

# Live mode: real read-only calls. Live checks whose env credentials are
# absent auto-skip (they never fail the run).
smoke-live:
	ALMA_SMOKE_LIVE=1 poetry run python -m pytest tests/smoke/ -q
