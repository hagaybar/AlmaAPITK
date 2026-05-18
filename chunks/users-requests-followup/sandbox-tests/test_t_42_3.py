"""t-42-3: live SANDBOX round-trip for the user-side resource-sharing-request
wrappers (issue #42).

Sequence:
  create → get → update_shipping action → cancel → post-cancel get (must fail)

Exercises all four wrappers from #42:
  - create_user_rs_request
  - get_user_rs_request
  - perform_user_rs_request_action(op='update_shipping')
  - cancel_user_rs_request

Agent-safety design (see conftest.py):
  - alma_logging output routed to a per-run detail log file (operator-only)
  - StageRecorder tracks (stage, ok, alma_code, duration_ms) without storing
    or serializing the wrapper's return value or any operator-supplied fixture
  - Summary JSON contains only booleans, numeric Alma codes, and counts
  - print() emits only stage banners, never identifier values
"""

from __future__ import annotations

import time

from almaapitk import AlmaAPIClient, Users
from almaapitk.client.AlmaAPIClient import AlmaAPIError

from conftest import StageRecorder, now_iso, write_summary

TEST_NAME = "t-42-3"


def _extract_request_id(response) -> str | None:
    data = getattr(response, "data", None) if response is not None else None
    if not isinstance(data, dict):
        return None
    rid = data.get("request_id") or data.get("id")
    return str(rid) if rid else None


def test_t_42_3(test_data, detail_log_path):
    print(f"[{TEST_NAME}] starting")
    started_at = now_iso()

    client = AlmaAPIClient("SANDBOX")
    users = Users(client)
    rec = StageRecorder()

    request_id: str | None = None
    cleanup_ok = False

    # --- CREATE -----------------------------------------------------------
    with rec.stage("create") as st:
        resp = users.create_user_rs_request(
            test_data["existing_user_primary_id"],
            {
                "citation_type": "BOOK",
                "format": {"value": "PHYSICAL"},
                "title": "AlmaAPITK regression-smoke RS request",
                "author": "AlmaAPITK",
                "owner": {"value": test_data["rs_library_code"]},
                "pickup_location": {"value": test_data["pickup_library_code"]},
            },
        )
        request_id = _extract_request_id(resp)
        rec.store("request_id", request_id)
        if not getattr(resp, "success", False):
            raise AlmaAPIError("create did not return success=True", 0, None)

    # --- GET (round-trip the request_id) ----------------------------------
    if request_id:
        with rec.stage("get") as st:
            resp = users.get_user_rs_request(
                test_data["existing_user_primary_id"], request_id
            )
            # Verify the get returns a dict with matching request_id, but
            # never record the value itself in summary.
            if not isinstance(resp, dict) or len(resp) == 0:
                raise AlmaAPIError("get returned empty response", 0, None)
            echo_id = str(resp.get("request_id") or resp.get("id") or "")
            if echo_id != str(request_id):
                raise AlmaAPIError("get response request_id mismatch", 0, None)
    else:
        rec.stages.append(
            {
                "name": "get",
                "ok": False,
                "duration_ms": 0,
                "alma_code": None,
                "exception_class": "no-request-id-from-create",
            }
        )

    # --- UPDATE_SHIPPING action -------------------------------------------
    if request_id:
        with rec.stage("update_shipping") as st:
            # Non-fatal: Alma may reject the update if the request is not
            # yet in the right workflow state. Record outcome either way;
            # don't raise so cancel still runs.
            try:
                resp = users.perform_user_rs_request_action(
                    test_data["existing_user_primary_id"],
                    request_id,
                    op="update_shipping",
                    shipping_cost=test_data.get("shipping_cost", "0.00"),
                    fund_code=test_data["fund_code"],
                )
                if not getattr(resp, "success", False):
                    raise AlmaAPIError("update_shipping did not succeed", 0, None)
            except AlmaAPIError as e:
                # Soft-fail: record but don't re-raise. The next stages still run.
                st.alma_code = getattr(e, "alma_code", None) or "soft-fail"
                # Re-raise within the context so the recorder marks ok=False
                # for this stage; but use expected_failure to suppress propagation.
                st.expected_failure = True
                raise

    # --- CANCEL (in-band cleanup happy path) ------------------------------
    if request_id:
        with rec.stage("cancel") as st:
            resp = users.cancel_user_rs_request(
                test_data["existing_user_primary_id"],
                request_id,
                reason="AUTOMATED_REGRESSION_TEST_CLEANUP",
                notify_user=False,
            )
            if not getattr(resp, "success", False):
                raise AlmaAPIError("cancel did not succeed", 0, None)
            cleanup_ok = True

    # --- POST-CANCEL GET (must fail with AlmaAPIError) --------------------
    if request_id:
        with rec.stage("post_cancel_get") as st:
            st.expected_failure = True
            users.get_user_rs_request(
                test_data["existing_user_primary_id"], request_id
            )
            # If we reach here, no exception was raised — that's a fail.
            raise AssertionError(
                "post-cancel get unexpectedly succeeded; request not cancelled?"
            )

    # --- Belt-and-braces finally-cancel (if in-band cancel didn't run) ---
    if request_id and not cleanup_ok:
        try:
            users.cancel_user_rs_request(
                test_data["existing_user_primary_id"],
                request_id,
                reason="AUTOMATED_REGRESSION_TEST_CLEANUP",
                notify_user=False,
            )
            cleanup_ok = True
        except AlmaAPIError:
            # Operator must do manual cleanup. The detail log carries the
            # request_id; the agent doesn't see it. The summary records
            # cleanup_ok=False as the signal.
            pass

    ended_at = now_iso()
    write_summary(
        test_name=TEST_NAME,
        stages=rec.stages,
        started_at=started_at,
        ended_at=ended_at,
        cleanup_ok=cleanup_ok,
        request_id_returned=request_id is not None,
        detail_log_path=detail_log_path,
    )
    print(f"[{TEST_NAME}] done")

    # Final assert for pytest: every stage must have ok=True for the test
    # itself to pass.
    failed_stages = [s for s in rec.stages if not s["ok"]]
    assert not failed_stages, f"{len(failed_stages)} stage(s) failed; see summary JSON"
