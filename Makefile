# Workflow smoke tests (issue #156/#157). Friendly wrappers over pytest so
# "validate this version" is one command.
.PHONY: check smoke smoke-live

# One local gate (issue #221): same set CI runs on every PR.
check:
	poetry run python scripts/smoke_import.py
	poetry run pytest tests/test_public_api_contract.py tests/test_version.py tests/unit/ tests/logging/ tests/integration/ tests/meta/ -q

# Dry-run only (no credentials needed): validates each workflow's wiring.
smoke:
	poetry run python -m pytest tests/smoke/ -q

# Live mode: real read-only calls. Live checks whose env credentials are
# absent auto-skip (they never fail the run).
smoke-live:
	ALMA_SMOKE_LIVE=1 poetry run python -m pytest tests/smoke/ -q
