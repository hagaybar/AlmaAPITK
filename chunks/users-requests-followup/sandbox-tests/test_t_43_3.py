"""t-43-3: live SANDBOX round-trip for the user-side purchase-request
wrappers (issue #43).

Sequence:
  create → get → list → cancel-via-perform-action

Exercises all four wrappers from #43:
  - create_user_purchase_request
  - get_user_purchase_request
  - list_user_purchase_requests
  - perform_user_purchase_request_action(op='cancel')

Purchase requests have NO DELETE verb per the swagger; cancellation goes
through perform_user_purchase_request_action(op='cancel').

Agent-safety design: see conftest.py + test_t_42_3.py.
"""

from __future__ import annotations

from almaapitk import AlmaAPIClient, Users
from almaapitk.client.AlmaAPIClient import AlmaAPIError

from conftest import StageRecorder, now_iso, write_summary

TEST_NAME = "t-43-3"


def _extract_pr_id(response) -> str | None:
    """Extract the purchase_request_id from a create response.

    Tries multiple field-name conventions because Alma's schema names the
    field ``request_id`` (per rest_purchase_request.json) but older toolkit
    and wrapper code referred to it as ``purchase_request_id`` or ``id``.
    """
    data = getattr(response, "data", None) if response is not None else None
    if not isinstance(data, dict):
        return None
    pr_id = (
        data.get("request_id")
        or data.get("purchase_request_id")
        or data.get("id")
    )
    return str(pr_id) if pr_id else None


def test_t_43_3(test_data, detail_log_path):
    print(f"[{TEST_NAME}] starting")
    started_at = now_iso()

    client = AlmaAPIClient("SANDBOX")
    users = Users(client)
    rec = StageRecorder()

    pr_id: str | None = None
    cleanup_ok = False
    ended_at = started_at
    try:
        # --- CREATE -------------------------------------------------------
        # Body shape per the authoritative purchase-request schema
        # (rest_purchase_request.json):
        #   - format.value: "P" or "E" — short codes; long-form "PHYSICAL"
        #     is rejected with alma_code 60270.
        #   - citation_type: lives under resource_metadata (NOT at root);
        #     mandatory; values from [BOOK,JOURNAL] per alma_code 60280.
        #   - material_type: NOT a documented field; Alma ignores it.
        with rec.stage("create") as st:
            resp = users.create_user_purchase_request(
                test_data["existing_user_primary_id"],
                {
                    "resource_metadata": {
                        "citation_type": {"value": "BOOK"},
                        "title": "AlmaAPITK regression-smoke purchase request",
                        "author": "AlmaAPITK",
                    },
                    "format": {"value": "P"},
                },
            )
            pr_id = _extract_pr_id(resp)
            rec.store("purchase_request_id", pr_id)
            if not getattr(resp, "success", False):
                raise AlmaAPIError("create did not return success=True", 0, None)

        # --- GET ----------------------------------------------------------
        if pr_id:
            with rec.stage("get") as st:
                resp = users.get_user_purchase_request(
                    test_data["existing_user_primary_id"], pr_id
                )
                if not isinstance(resp, dict) or len(resp) == 0:
                    raise AlmaAPIError("get returned empty response", 0, None)
                echo_id = str(resp.get("id") or resp.get("purchase_request_id") or "")
                if echo_id != str(pr_id):
                    raise AlmaAPIError("get response purchase_request_id mismatch", 0, None)

        # --- LIST (must contain the new request) --------------------------
        if pr_id:
            with rec.stage("list_contains_new_request") as st:
                requests_list = users.list_user_purchase_requests(
                    test_data["existing_user_primary_id"]
                )
                if not isinstance(requests_list, list):
                    raise AlmaAPIError("list did not return a list", 0, None)
                found = False
                for pr in requests_list:
                    if not isinstance(pr, dict):
                        continue
                    echo = str(pr.get("id") or pr.get("purchase_request_id") or "")
                    if echo == str(pr_id):
                        found = True
                        break
                if not found:
                    raise AlmaAPIError(
                        "newly-created purchase request not found in list", 0, None
                    )

        # --- CANCEL via perform-action ------------------------------------
        if pr_id:
            with rec.stage("cancel_via_action") as st:
                resp = users.perform_user_purchase_request_action(
                    test_data["existing_user_primary_id"],
                    pr_id,
                    op="cancel",
                )
                if not getattr(resp, "success", False):
                    raise AlmaAPIError("cancel action did not succeed", 0, None)
                cleanup_ok = True
    finally:
        # Belt-and-braces finally-cancel (if in-band cancel didn't run).
        if pr_id and not cleanup_ok:
            try:
                users.perform_user_purchase_request_action(
                    test_data["existing_user_primary_id"], pr_id, op="cancel"
                )
                cleanup_ok = True
            except AlmaAPIError:
                # Operator must do manual cleanup via Alma staff UI.
                pass

        ended_at = now_iso()
        write_summary(
            test_name=TEST_NAME,
            stages=rec.stages,
            started_at=started_at,
            ended_at=ended_at,
            cleanup_ok=cleanup_ok,
            request_id_returned=pr_id is not None,
            detail_log_path=detail_log_path,
        )
        print(f"[{TEST_NAME}] done")

    failed_stages = [s for s in rec.stages if not s["ok"]]
    assert not failed_stages, f"{len(failed_stages)} stage(s) failed; see summary JSON"
