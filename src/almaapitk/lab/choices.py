"""Allowed values of Raw console query parameters, shown as a dropdown.

Alma's API definitions give these only in a parameter's free-text description
(e.g. "Currently, the options are 'mark_in_erp', 'paid', 'process_invoice' or
'rejected'"), so they are written out here by hand, copied from those
descriptions. Only complete, single-value lists are included: code-table values,
numeric ranges, comma-separated lists and sort keys stay free text.

Keys are ``(method, path below /almaws/v1, parameter)``. A test checks that every
key is a real parameter of an indexed endpoint.
"""
from __future__ import annotations

_OP = "op"
_ASC_DESC = ("asc", "desc")
_REMINDER_ORDER = ("type", "status", "reminder_date")
_PERIOD = ("days", "weeks", "months")
_FEE_METHOD = ("CREDIT_CARD", "ONLINE", "CASH")

PARAM_CHOICES: dict[tuple[str, str, str], tuple[str, ...]] = {
    # Acquisitions
    ("GET", "/acq/funds", "view"): ("full", "brief"),
    ("GET", "/acq/funds/{fund_id}", "view"): ("full", "brief"),
    ("POST", "/acq/funds/{fund_id}", _OP): ("activate", "deactivate"),
    ("GET", "/acq/invoices/", "base_status"): ("ACTIVE", "CLOSED"),
    ("POST", "/acq/invoices/{invoice_id}", _OP): ("mark_in_erp", "paid", "process_invoice", "rejected"),
    ("GET", "/acq/licenses/", "status"): ("ACTIVE", "DELETED", "DRAFT", "EXPIRED", "RETIRED", "ALL"),
    ("GET", "/acq/licenses/", "type"): ("LICENSE", "NEGOTIATION", "ADDENDUM", "ALL"),
    ("GET", "/acq/po-lines", "status"): ("CLOSED", "CANCELLED", "ACTIVE", "ALL", "ALL_WITH_CLOSED"),
    ("POST", "/acq/po-lines/{po_line_id}/items/{item_id}", _OP): ("receive",),
    ("POST", "/acq/purchase-requests/{id}", _OP): ("approve", "reject"),
    # Bibs
    ("POST", "/bibs/{mms_id}", _OP): ("unlink_from_nz",),
    ("GET", "/bibs/{mms_id}/booking-availability", "period_type"): _PERIOD,
    ("GET", "/bibs/{mms_id}/holdings/{holding_id}/items/{item_id}/requests", "request_type"):
        ("HOLD", "DIGITIZATION", "BOOKING"),
    ("POST", "/bibs/{mms_id}/holdings/{holding_id}/items/{item_pid}", _OP): ("scan",),
    ("GET", "/bibs/{mms_id}/holdings/{holding_id}/items/{item_pid}/booking-availability",
     "period_type"): _PERIOD,
    ("POST", "/bibs/{mms_id}/holdings/{holding_id}/items/{item_pid}/loans/{loan_id}", _OP):
        ("renew",),
    ("POST", "/bibs/{mms_id}/holdings/{holding_id}/items/{item_pid}/requests/{request_id}", _OP):
        ("next_step",),
    ("GET", "/bibs/{mms_id}/reminders", "order_by"): _REMINDER_ORDER,
    ("GET", "/bibs/{mms_id}/reminders", "direction"): _ASC_DESC,
    ("GET", "/bibs/{mms_id}/requests", "request_type"):
        ("HOLD", "DIGITIZATION", "BOOKING", "MOVE", "WORK_ORDER"),
    ("POST", "/bibs/{mms_id}/requests/{request_id}", _OP): ("next_step",),
    # Configuration
    ("GET", "/conf/jobs", "type"): ("MANUAL", "SCHEDULED", "OTHER"),
    ("POST", "/conf/jobs/{job_id}", _OP): ("run",),
    ("GET", "/conf/jobs/{job_id}/instances/{instance_id}/matches", "population"):
        ("SINGLE_MATCHES", "MULTI_MATCHES"),
    ("POST", "/conf/md-import-profiles/{profile_id}", _OP): ("run",),
    ("GET", "/conf/reminders", "order_by"): _REMINDER_ORDER,
    ("GET", "/conf/reminders", "direction"): _ASC_DESC,
    ("GET", "/conf/sets", "set_type"): ("ITEMIZED", "LOGICAL"),
    ("GET", "/conf/sets", "set_origin"): ("UI", "UI_CZ"),
    ("POST", "/conf/sets/{set_id}", _OP): ("add_members", "delete_members", "replace_members"),
    # Courses
    ("POST", "/courses/{course_id}", _OP): ("enroll_user", "associate_to_reading_lists"),
    ("POST", "/courses/{course_id}/reading-lists/{reading_list_id}/citations/{citation_id}", _OP):
        ("remove_file",),
    # Partners
    ("GET", "/partners", "status"): ("ACTIVE", "INACTIVE"),
    # Users
    ("GET", "/users/{user_id}", "view"): ("full", "brief"),
    ("POST", "/users/{user_id}", _OP): ("auth", "refresh"),
    ("GET", "/users/{user_id}/attachments/{attachment_id}", "expand"):
        ("content", "content_no_encoding"),
    ("POST", "/users/{user_id}/deposits/{deposit_id}", _OP): ("submit", "withdraw"),
    ("POST", "/users/{user_id}/fees/all", _OP): ("pay",),
    ("POST", "/users/{user_id}/fees/all", "method"): _FEE_METHOD,
    ("POST", "/users/{user_id}/fees/{fee_id}", _OP): ("pay", "waive", "dispute", "restore"),
    ("POST", "/users/{user_id}/fees/{fee_id}", "method"): _FEE_METHOD,
    ("POST", "/users/{user_id}/loans/{loan_id}", _OP): ("renew",),
    ("GET", "/users/{user_id}/purchase-requests", "status"):
        ("INREVIEW", "APPROVED", "REJECTED", "DEFERRED"),
    ("GET", "/users/{user_id}/purchase-requests", "direction"): _ASC_DESC,
    ("POST", "/users/{user_id}/purchase-requests/{purchase_request_id}", _OP): ("cancel",),
    ("GET", "/users/{user_id}/requests", "request_type"): ("HOLD", "DIGITIZATION", "BOOKING"),
    ("POST", "/users/{user_id}/requests/{request_id}", _OP): ("next_step",),
    ("POST", "/users/{user_id}/resource-sharing-requests/{request_id}", _OP): ("update_shipping",),
}


def param_choices(method: str, short_path: str, name: str) -> tuple[str, ...]:
    """Allowed values of one query parameter, or ``()`` when it is free text."""
    return PARAM_CHOICES.get((method, short_path, name), ())
