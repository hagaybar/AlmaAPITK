"""
Enhanced Users Domain Class for Alma API
Aligned with AlmaAPIClient integration patterns and focused on email update workflow
for users expired 2+ years from Alma sets.
"""

import base64
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Import the working AlmaAPIClient and its response/error classes
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'client'))
from almaapitk.client.AlmaAPIClient import AlmaAPIClient, AlmaResponse, AlmaAPIError, AlmaValidationError


class Users:
    """
    Enhanced Users domain class for Alma API operations.
    
    Focused on email update workflow for expired users:
    - Retrieve users by ID from sets
    - Analyze expiry dates (2+ years expired)
    - Extract and validate email addresses
    - Update user email addresses
    - Bulk processing capabilities
    """
    
    def __init__(self, client: AlmaAPIClient):
        """
        Initialize the Users domain.
        
        Args:
            client: The AlmaAPIClient instance for making HTTP requests
        """
        self.client = client
        self.logger = client.logger
        self.environment = client.get_environment()
         # Setup enhanced logger with optional file handler
        self.logger = self._setup_enhanced_logger("sb_log_file.log" if self.environment == "SANDBOX" else "prod_log_file.log")
    
    # Core User Retrieval Methods



    def _setup_enhanced_logger(self, log_file: str = None):
        """
        Setup enhanced logger with both console and optional file handlers.
        
        Args:
            log_file: Optional path to log file
            
        Returns:
            Enhanced logger instance
        """
        
        # Create logger name
        logger_name = f"Users_{self.environment}"
        logger = logging.getLogger(logger_name)
        
        # Clear existing handlers to avoid duplicates
        logger.handlers.clear()
        logger.setLevel(logging.DEBUG)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler (INFO level)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler (DEBUG level) - if log_file specified
        if log_file:
            try:
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                file_handler.setLevel(logging.DEBUG)
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
                logger.info(f"File logging enabled: {log_file}")
            except Exception as e:
                logger.error(f"Could not create file handler for {log_file}: {e}")
        
        return logger





    
    def get_user(self, user_id: str, expand: str = "none") -> AlmaResponse:
        """
        Retrieve a user by their ID.
        
        Args:
            user_id: User identifier (primary ID, barcode, etc.)
            expand: Additional data to include (loans, requests, fees)
        
        Returns:
            AlmaResponse containing user data
            
        Raises:
            AlmaValidationError: If user_id is empty
            AlmaAPIError: If API request fails
        """
        if not user_id or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        
        params = {'expand': expand} if expand != "none" else {}
        endpoint = f'almaws/v1/users/{user_id.strip()}'
        
        try:
            response = self.client.get(endpoint, params=params)
            self.logger.info(f"Retrieved user {user_id}")
            return response
            
        except AlmaAPIError as e:
            if e.status_code == 404:
                self.logger.warning(f"User not found: {user_id}")
            else:
                self.logger.error(f"API error retrieving user {user_id}: {e}")
            raise
    
    def list_users(
        self,
        limit: int = 10,
        offset: int = 0,
        q: Optional[str] = None,
        order_by: Optional[str] = None,
        expand: Optional[str] = None,
        source_user_id: Optional[str] = None,
        source_institution_code: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List or search users via ``GET /almaws/v1/users``.

        Calls the Alma users list/search endpoint and unwraps the
        response envelope (``{"user": [...], "total_record_count": N}``)
        into a flat list. ``q`` enables Alma's specialized SRU-style
        query syntax — e.g. ``last_name~Smith`` or ``primary_id~ST123``.
        Any non-``None`` filter is forwarded as a query parameter; ``None``
        values are dropped so Alma applies its own defaults.

        Args:
            limit: Maximum number of users to return per request
                (Alma caps at 100). Defaults to 10.
            offset: Zero-based offset into the result set. Defaults to 0.
            q: Alma query string (e.g. ``last_name~Smith``). Optional.
            order_by: Field to sort by (e.g. ``last_name``). Optional.
            expand: Additional data to include (e.g. ``loans,requests``).
                Optional.
            source_user_id: Filter by source-system user identifier
                (fulfillment-network use case). Optional.
            source_institution_code: Filter by source-institution code
                (fulfillment-network use case). Optional.

        Returns:
            List of user dicts as returned by Alma. Returns an empty
            list when no users match (or when the response envelope is
            missing the ``user`` key).

        Raises:
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: Configuration.list_libraries
        # (configuration.py line 218, issue #24) for the
        # "single GET, unwrap envelope, return list" idiom. The audit
        # (2026-05-01) flagged the prior narrower signature as missing
        # several documented optional filters; surface them explicitly
        # here so IDE/type-check users get autocompletion.
        params: Dict[str, Any] = {
            "limit": str(limit),
            "offset": str(offset),
        }
        if q is not None:
            params["q"] = q
        if order_by is not None:
            params["order_by"] = order_by
        if expand is not None:
            params["expand"] = expand
        if source_user_id is not None:
            params["source_user_id"] = source_user_id
        if source_institution_code is not None:
            params["source_institution_code"] = source_institution_code

        self.logger.info(
            f"Listing users (limit={limit}, offset={offset}, q={q!r})"
        )
        try:
            response = self.client.get("almaws/v1/users", params=params)
            payload = response.json() or {}
            users = payload.get("user") or []
            if isinstance(users, dict):
                # Single-record responses can come back as a dict; normalise.
                users = [users]
            self.logger.info(f"Retrieved {len(users)} users")
            return users
        except AlmaAPIError as e:
            self.logger.error(
                f"API error listing users: {e}",
            )
            raise

    def search_users(
        self,
        q: str,
        limit: int = 10,
        offset: int = 0,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Search users with a required Alma query string.

        Convenience wrapper around :meth:`list_users` for the common
        case of "find users matching this query". Validates that ``q``
        is a non-empty string and forwards every other parameter to
        :meth:`list_users`.

        Args:
            q: Alma query string (e.g. ``last_name~Smith``,
                ``primary_id~ST123``). Required and must be a non-empty
                string.
            limit: Maximum number of users to return. Defaults to 10.
            offset: Zero-based offset into the result set. Defaults to 0.
            **kwargs: Additional optional filters forwarded to
                :meth:`list_users` (``order_by``, ``expand``,
                ``source_user_id``, ``source_institution_code``).

        Returns:
            List of user dicts matching the query. Returns an empty list
            when no users match.

        Raises:
            AlmaValidationError: If ``q`` is empty or not a string.
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: list_users (above) — thin wrapper that adds a
        # required-q validation gate before delegating.
        if not isinstance(q, str) or not q.strip():
            raise AlmaValidationError(
                "Query string 'q' must be a non-empty string"
            )
        return self.list_users(
            q=q.strip(),
            limit=limit,
            offset=offset,
            **kwargs,
        )

    def get_user_personal_data(self, user_id: str) -> Dict[str, Any]:
        """Fetch the GDPR personal-data export for a single user.

        Calls ``GET /almaws/v1/users/{user_id}/personal-data`` and
        returns the raw export payload as a dict. The response body is
        sensitive (full GDPR data-portability export) — only the
        ``user_id`` and result-shape are logged, never the body itself.

        Args:
            user_id: User identifier (primary ID, barcode, etc.). Must
                be a non-empty string.

        Returns:
            The personal-data export dict as returned by Alma.

        Raises:
            AlmaValidationError: If ``user_id`` is empty or not a string.
            AlmaAPIError: If the API request fails (including 404 / 400
                + errorCode 401890 when the user does not exist).
        """
        # Pattern source: get_user (above) — validate, log entry, GET,
        # log success without body, propagate API errors.
        if not isinstance(user_id, str) or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        clean_id = user_id.strip()

        endpoint = f"almaws/v1/users/{clean_id}/personal-data"
        self.logger.info(f"Retrieving personal data for user {clean_id}")
        try:
            response = self.client.get(endpoint)
            data: Dict[str, Any] = response.data or {}
            # Personal-data responses are sensitive; log only the shape
            # (top-level key count), never the body itself.
            self.logger.info(
                f"Retrieved personal data for user {clean_id} "
                f"(top-level keys: {len(data)})"
            )
            return data
        except AlmaAPIError as e:
            self.logger.error(
                f"API error retrieving personal data for user {clean_id}: {e}"
            )
            raise

    # ------------------------------------------------------------------
    # User attachments (issue #39)
    # ------------------------------------------------------------------
    #
    # The user-attachments endpoints expose three operations: list, get,
    # and upload. Alma documents (and the public Swagger) does NOT expose
    # a DELETE endpoint, and live SANDBOX probing on 2026-05-08 confirmed
    # that ``DELETE /almaws/v1/users/{id}/attachments/{att_id}`` is not
    # routed (alma_code 401861, "User with identifier ... not found"
    # because the router collapses the path into a malformed user
    # lookup). No ``delete_user_attachment`` is provided.
    #
    # Upload is JSON+base64 (verified live 2026-05-08), NOT multipart.
    # The request body's ``type`` field is a plain string ("GENERAL"),
    # NOT the ``{"value": "GENERAL"}`` wrapper Alma uses elsewhere — that
    # wrapper produces 400 ("Cannot deserialize value of type
    # java.lang.String from Object value"). File contents and the base64
    # payload are NEVER logged (matches the GDPR-discipline established
    # by ``get_user_personal_data`` above).
    #
    # Read patterns mirror ``Configuration.list_libraries`` /
    # ``Configuration.get_library`` (issue #24): single GET, unwrap the
    # Alma envelope, return list/dict.

    def list_user_attachments(self, user_id: str) -> List[Dict[str, Any]]:
        """List all attachments for a user.

        Calls ``GET /almaws/v1/users/{user_id}/attachments`` and unwraps
        the Alma response envelope into a flat list. The envelope key
        observed in live SANDBOX is ``user_attachment``; fall back to
        ``attachment`` defensively in case the endpoint reverts to the
        legacy shape on a future Alma release.

        Args:
            user_id: User identifier (primary ID, barcode, etc.). Must
                be a non-empty string.

        Returns:
            List of attachment dicts as returned by Alma. Returns an
            empty list when the user has no attachments (or when the
            response envelope is missing both candidate keys).

        Raises:
            AlmaValidationError: If ``user_id`` is empty or not a string.
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: Configuration.list_libraries (configuration.py
        # line 218, issue #24) for the "single GET, unwrap envelope,
        # return list" idiom. ``user_id`` validation mirrors
        # ``get_user_personal_data`` (above).
        if not isinstance(user_id, str) or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        clean_id = user_id.strip()

        endpoint = f"almaws/v1/users/{clean_id}/attachments"
        self.logger.info(
            f"Listing attachments for user {clean_id}"
        )
        try:
            response = self.client.get(endpoint)
            payload = response.json() or {}
            # The live response envelope is ``user_attachment``; some
            # legacy / undocumented variants use plain ``attachment``.
            attachments = (
                payload.get("user_attachment")
                or payload.get("attachment")
                or []
            )
            if isinstance(attachments, dict):
                # Single-record responses can come back as a dict; normalise.
                attachments = [attachments]
            self.logger.info(
                f"Retrieved {len(attachments)} attachments for user {clean_id}"
            )
            return attachments
        except AlmaAPIError as e:
            self.logger.error(
                f"API error listing attachments for user {clean_id}: {e}"
            )
            raise

    def get_user_attachment(
        self,
        user_id: str,
        attachment_id: str,
        expand: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve a single attachment's metadata (and optionally content).

        Calls ``GET /almaws/v1/users/{user_id}/attachments/{attachment_id}``.
        The ``expand`` query parameter is forwarded only when non-``None``
        and supports Alma's documented values ``"content"`` (returns the
        base64-encoded file inline) and ``"content_no_encoding"`` (returns
        raw content).

        Args:
            user_id: User identifier (primary ID, barcode, etc.). Must
                be a non-empty string.
            attachment_id: Attachment identifier as returned by
                :meth:`list_user_attachments` (key ``id`` on each entry).
                Must be a non-empty string.
            expand: Optional Alma ``expand`` directive. Pass
                ``"content"`` to receive the file bytes inline (the
                ``content`` key in the response will hold the base64
                payload), ``"content_no_encoding"`` for unencoded
                bytes, or ``None`` for metadata only. Defaults to
                ``None``.

        Returns:
            The attachment dict as returned by Alma. Callers that
            requested ``expand="content"`` are responsible for
            base64-decoding ``result["content"]`` themselves.

        Raises:
            AlmaValidationError: If ``user_id`` or ``attachment_id`` is
                empty or not a string.
            AlmaAPIError: If the API request fails (including 404 when
                the user or attachment does not exist).
        """
        # Pattern source: Configuration.get_library (configuration.py
        # line 270, issue #24) — validate, log entry, GET, log success,
        # propagate API errors.
        if not isinstance(user_id, str) or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        if not isinstance(attachment_id, str) or not attachment_id.strip():
            raise AlmaValidationError("Attachment ID cannot be empty")
        clean_user_id = user_id.strip()
        clean_attachment_id = attachment_id.strip()

        params: Dict[str, Any] = {}
        if expand is not None:
            params["expand"] = expand

        endpoint = (
            f"almaws/v1/users/{clean_user_id}/attachments/"
            f"{clean_attachment_id}"
        )
        self.logger.info(
            f"Retrieving attachment {clean_attachment_id} for user "
            f"{clean_user_id} (expand={expand!r})"
        )
        try:
            response = self.client.get(
                endpoint, params=params if params else None
            )
            data: Dict[str, Any] = response.json() or {}
            # Never log the body — when expand="content" the response
            # carries the file payload itself.
            self.logger.info(
                f"Retrieved attachment {clean_attachment_id} for user "
                f"{clean_user_id}"
            )
            return data
        except AlmaAPIError as e:
            self.logger.error(
                f"API error retrieving attachment {clean_attachment_id} "
                f"for user {clean_user_id}: {e}"
            )
            raise

    def upload_user_attachment(
        self,
        user_id: str,
        file_path: str,
        attachment_data: Optional[Dict[str, Any]] = None,
    ) -> AlmaResponse:
        """Upload a new attachment to a user record.

        Calls ``POST /almaws/v1/users/{user_id}/attachments`` with a
        JSON body containing the file's base64-encoded contents. The
        body shape was verified against live SANDBOX on 2026-05-08:

        .. code-block:: json

            {
              "type": "GENERAL",
              "note": "<description>",
              "file_name": "<filename>",
              "content": "<base64-encoded file bytes>"
            }

        Notably, ``type`` is a **plain string**, not the
        ``{"value": "GENERAL"}`` wrapper Alma uses elsewhere — the
        wrapped form returns 400 ("Cannot deserialize value of type
        java.lang.String from Object value"). The file's bytes and the
        base64 payload are never logged; only ``user_id``, ``file_name``,
        and ``size_bytes`` reach the audit trail.

        Args:
            user_id: User identifier (primary ID, barcode, etc.). Must
                be a non-empty string.
            file_path: Filesystem path to the file to upload. Must be a
                non-empty string and must point to an existing file.
            attachment_data: Optional override dict for the request
                body. When supplied it is shallow-copied; ``file_name``
                defaults to the basename of ``file_path`` (when not
                already set), ``content`` is overridden with the
                base64-encoded file bytes, and ``type`` defaults to
                ``"GENERAL"`` when not already set. Useful for
                supplying ``note`` / ``description`` fields without
                rebuilding the body shape.

        Returns:
            ``AlmaResponse`` wrapping the Alma response. The created
            attachment's identifier lives at ``response.data["id"]``.

        Raises:
            AlmaValidationError: If ``user_id`` or ``file_path`` is
                empty / not a string, or if ``file_path`` does not point
                to an existing file.
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: get_user_personal_data (above) for the
        # "validate inputs, log without leaking sensitive content"
        # discipline; Configuration.list_libraries for the
        # AlmaResponse handoff pattern.
        if not isinstance(user_id, str) or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        if not isinstance(file_path, str) or not file_path.strip():
            raise AlmaValidationError(
                "file_path is required and must be a non-empty string"
            )

        clean_user_id = user_id.strip()
        path = Path(file_path)
        if not path.is_file():
            raise AlmaValidationError(
                f"file_path does not point to an existing file: {file_path}"
            )

        # Read file bytes and base64-encode. The encoded payload is
        # passed to Alma as a UTF-8 string — never logged.
        file_bytes = path.read_bytes()
        size_bytes = len(file_bytes)
        encoded = base64.b64encode(file_bytes).decode("ascii")

        # Build the JSON body. Shallow-copy any caller-supplied dict so
        # we never mutate the operator's data.
        body: Dict[str, Any] = (
            dict(attachment_data) if attachment_data else {}
        )
        body.setdefault("type", "GENERAL")
        body.setdefault("file_name", path.name)
        # Always override content with the freshly-read base64 payload
        # so a caller-supplied stale ``content`` cannot win.
        body["content"] = encoded

        endpoint = f"almaws/v1/users/{clean_user_id}/attachments"
        # Audit-log: identifier + filename + size only. NEVER the body
        # or the base64 payload.
        self.logger.info(
            f"Uploading attachment for user {clean_user_id} "
            f"(file_name={body['file_name']!r}, size_bytes={size_bytes})"
        )
        try:
            response = self.client.post(endpoint, data=body)
            attachment_id: Any = None
            try:
                attachment_id = (response.data or {}).get("id")
            except (ValueError, AttributeError):
                # Non-JSON / unparseable body — surface the AlmaResponse
                # to the caller anyway; the error path below logs only
                # the status code, not any body content.
                attachment_id = None
            self.logger.info(
                f"Uploaded attachment for user {clean_user_id} "
                f"(attachment_id={attachment_id!r}, "
                f"file_name={body['file_name']!r})"
            )
            return response
        except AlmaAPIError as e:
            self.logger.error(
                f"API error uploading attachment for user "
                f"{clean_user_id} (file_name={body['file_name']!r}): {e}"
            )
            raise

    # ------------------------------------------------------------------
    # User fines & fees (issue #44)
    # ------------------------------------------------------------------
    #
    # The fines/fees endpoints expose three reads (list/get/create) and
    # five op-driven posts (pay-all, pay, waive, dispute, restore). All
    # five op-driven posts use the documented Alma convention of passing
    # the operation and its scalar arguments as **query parameters**:
    #
    #   POST /users/{id}/fees/all?op=pay&amount=ALL&method=CASH
    #   POST /users/{id}/fees/{fee_id}?op=waive&reason=...&amount=...
    #
    # The audit (2026-05-08) flagged three signature mismatches in the
    # original spec and these methods correct them:
    #   1. ``pay_all_user_fees`` defaults ``amount="ALL"`` (string sentinel,
    #      not a number) and forwards ``op``, ``amount``, ``method`` as
    #      **params** — never body.
    #   2. ``dispute_user_fee.reason`` is OPTIONAL — only ``waive``
    #      requires a reason.
    #   3. ``method`` is only sent on ``op=pay`` / ``op=pay_all``; waive,
    #      dispute, and restore have no ``method`` arg in their signature.
    #
    # Read patterns mirror ``Configuration.list_libraries`` /
    # ``Configuration.get_library`` (issue #24) for "single GET, unwrap
    # envelope, return list" and ``list_user_attachments`` /
    # ``get_user_attachment`` (issue #39) for the fees envelope key
    # discipline.

    @staticmethod
    def _validate_pay_amount(amount: str) -> None:
        """Validate the ``amount`` argument for op=pay / op=pay_all.

        Allowed: the literal string ``"ALL"`` (sentinel meaning "the full
        outstanding balance"), or a numeric string consisting of digits
        with at most one decimal point. Anything else raises
        :class:`AlmaValidationError`.
        """
        if not isinstance(amount, str) or not amount.strip():
            raise AlmaValidationError(
                "amount must be a non-empty string ('ALL' or a numeric value)"
            )
        clean = amount.strip()
        if clean == "ALL":
            return
        # Reject obviously non-numeric values. Allow optional leading
        # minus only for a defensive future-proofing — Alma rejects
        # negatives at the server, but the client validator is about
        # *shape*, not policy.
        candidate = clean[1:] if clean.startswith("-") else clean
        if candidate.count(".") > 1 or not candidate.replace(".", "").isdigit():
            raise AlmaValidationError(
                f"amount must be 'ALL' or a numeric string, got: {amount!r}"
            )

    def list_user_fees(
        self,
        user_id: str,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List a user's active fines and fees.

        Calls ``GET /almaws/v1/users/{user_id}/fees`` and unwraps the
        Alma response envelope (``{"fee": [...], "total_record_count":
        N}``) into a flat list. The optional ``status`` filter is
        forwarded as a query parameter when supplied; otherwise Alma
        applies its own default (``ACTIVE``).

        Args:
            user_id: User identifier (primary ID, barcode, etc.). Must
                be a non-empty string.
            status: Optional fee-status filter (e.g. ``"ACTIVE"``,
                ``"INDISPUTE"``, ``"CLOSED"``). When ``None`` (default),
                no ``status`` query parameter is sent and Alma returns
                the default set.

        Returns:
            List of fee dicts as returned by Alma. Returns an empty list
            when the user has no matching fees (or when the response
            envelope is missing the ``fee`` key).

        Raises:
            AlmaValidationError: If ``user_id`` is empty or not a string.
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: list_user_attachments (above, issue #39) for
        # the "single GET, unwrap envelope, return list" idiom plus
        # single-record-as-dict normalisation. ``list_users``
        # (issue #36) for the optional-filter forwarding pattern.
        if not isinstance(user_id, str) or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        clean_id = user_id.strip()

        params: Dict[str, Any] = {}
        if status is not None:
            params["status"] = status

        endpoint = f"almaws/v1/users/{clean_id}/fees"
        self.logger.info(
            f"Listing fees for user {clean_id} (status={status!r})"
        )
        try:
            response = self.client.get(
                endpoint, params=params if params else None
            )
            payload = response.json() or {}
            fees = payload.get("fee") or []
            if isinstance(fees, dict):
                # Single-record responses can come back as a dict; normalise.
                fees = [fees]
            self.logger.info(
                f"Retrieved {len(fees)} fees for user {clean_id}"
            )
            return fees
        except AlmaAPIError as e:
            self.logger.error(
                f"API error listing fees for user {clean_id}: {e}"
            )
            raise

    def create_user_fee(
        self,
        user_id: str,
        fee_data: Dict[str, Any],
    ) -> AlmaResponse:
        """Create a new fine/fee on a user record.

        Calls ``POST /almaws/v1/users/{user_id}/fees`` with the
        operator-supplied ``fee_data`` dict as the JSON body. The body
        is passed through verbatim — the caller is responsible for
        supplying the Alma-required fields (``type``, ``original_amount``,
        ``owner``, etc.; see Alma's ``user fine/fee type/amount/owner is
        required`` validation errors).

        Args:
            user_id: User identifier (primary ID, barcode, etc.). Must
                be a non-empty string.
            fee_data: Fee body as a non-empty dict. Passed through to
                Alma verbatim.

        Returns:
            ``AlmaResponse`` wrapping the Alma response. The created
            fee's identifier lives at ``response.data["id"]``.

        Raises:
            AlmaValidationError: If ``user_id`` is empty/not a string,
                or if ``fee_data`` is empty or not a dict.
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: upload_user_attachment (above, issue #39) for
        # the "validate, log entry without body, POST, log success with
        # the new id" discipline. update_user (below) for the
        # "fee_data passed through verbatim" pattern.
        if not isinstance(user_id, str) or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        if not isinstance(fee_data, dict) or not fee_data:
            raise AlmaValidationError(
                "fee_data must be a non-empty dictionary"
            )
        clean_id = user_id.strip()

        endpoint = f"almaws/v1/users/{clean_id}/fees"
        # Audit-log: the user_id and the fee type only (not amounts /
        # comments / arbitrary caller-supplied fields).
        fee_type = fee_data.get("type")
        self.logger.info(
            f"Creating fee for user {clean_id} (type={fee_type!r})"
        )
        try:
            response = self.client.post(endpoint, data=fee_data)
            fee_id: Any = None
            try:
                fee_id = (response.data or {}).get("id")
            except (ValueError, AttributeError):
                fee_id = None
            self.logger.info(
                f"Created fee for user {clean_id} (fee_id={fee_id!r})"
            )
            return response
        except AlmaAPIError as e:
            self.logger.error(
                f"API error creating fee for user {clean_id}: {e}"
            )
            raise

    def get_user_fee(self, user_id: str, fee_id: str) -> Dict[str, Any]:
        """Retrieve a single fee's details.

        Calls ``GET /almaws/v1/users/{user_id}/fees/{fee_id}`` and
        returns the unwrapped fee dict.

        Args:
            user_id: User identifier (primary ID, barcode, etc.). Must
                be a non-empty string.
            fee_id: Fee identifier as returned by :meth:`list_user_fees`
                (key ``id`` on each entry). Must be a non-empty string.

        Returns:
            The fee dict as returned by Alma.

        Raises:
            AlmaValidationError: If ``user_id`` or ``fee_id`` is empty
                or not a string.
            AlmaAPIError: If the API request fails (including 404 when
                the user or fee does not exist).
        """
        # Pattern source: get_user_attachment (above, issue #39) — same
        # "validate two ids, GET, return dict" shape.
        if not isinstance(user_id, str) or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        if not isinstance(fee_id, str) or not fee_id.strip():
            raise AlmaValidationError("Fee ID cannot be empty")
        clean_user_id = user_id.strip()
        clean_fee_id = fee_id.strip()

        endpoint = (
            f"almaws/v1/users/{clean_user_id}/fees/{clean_fee_id}"
        )
        self.logger.info(
            f"Retrieving fee {clean_fee_id} for user {clean_user_id}"
        )
        try:
            response = self.client.get(endpoint)
            data: Dict[str, Any] = response.json() or {}
            self.logger.info(
                f"Retrieved fee {clean_fee_id} for user {clean_user_id}"
            )
            return data
        except AlmaAPIError as e:
            self.logger.error(
                f"API error retrieving fee {clean_fee_id} for user "
                f"{clean_user_id}: {e}"
            )
            raise

    def pay_all_user_fees(
        self,
        user_id: str,
        amount: str = "ALL",
        method: str = "CASH",
        external_transaction_id: Optional[str] = None,
    ) -> AlmaResponse:
        """Pay all of a user's outstanding fees in one operation.

        Calls
        ``POST /almaws/v1/users/{user_id}/fees/all?op=pay&amount=...&method=...``.
        The ``op``, ``amount``, ``method``, and (when supplied)
        ``external_transaction_id`` are sent as **query parameters**, not
        in the request body — Alma's documented convention for this
        endpoint.

        Args:
            user_id: User identifier (primary ID, barcode, etc.). Must
                be a non-empty string.
            amount: The literal string ``"ALL"`` (default — pay the full
                outstanding balance) or a numeric string (e.g.
                ``"12.50"``). Validated client-side; non-conforming
                values raise :class:`AlmaValidationError` before any
                HTTP call is issued.
            method: Payment method (Alma values: ``"CASH"``, ``"CREDIT"``,
                ``"CHECK"``, ``"ONLINE"``, ``"WIRE"``). Defaults to
                ``"CASH"``.
            external_transaction_id: Optional external system identifier
                (e.g. payment-gateway transaction id). Forwarded only
                when non-``None``.

        Returns:
            ``AlmaResponse`` wrapping the Alma response.

        Raises:
            AlmaValidationError: If ``user_id`` is empty/not a string,
                or if ``amount`` is not ``"ALL"`` and not a numeric
                string.
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: upload_user_attachment (issue #39) for the
        # validate-and-POST discipline. This is the audit-corrected
        # signature: ``amount="ALL"`` default + query-param transport.
        if not isinstance(user_id, str) or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        self._validate_pay_amount(amount)
        if not isinstance(method, str) or not method.strip():
            raise AlmaValidationError("method must be a non-empty string")
        clean_id = user_id.strip()

        params: Dict[str, Any] = {
            "op": "pay",
            "amount": amount.strip(),
            "method": method.strip(),
        }
        if external_transaction_id is not None:
            params["external_transaction_id"] = external_transaction_id

        endpoint = f"almaws/v1/users/{clean_id}/fees/all"
        self.logger.info(
            f"Paying all fees for user {clean_id} "
            f"(amount={params['amount']!r}, method={params['method']!r})"
        )
        try:
            response = self.client.post(endpoint, params=params)
            self.logger.info(
                f"Paid all fees for user {clean_id}"
            )
            return response
        except AlmaAPIError as e:
            self.logger.error(
                f"API error paying all fees for user {clean_id}: {e}"
            )
            raise

    def pay_user_fee(
        self,
        user_id: str,
        fee_id: str,
        amount: str,
        method: str = "CASH",
        external_transaction_id: Optional[str] = None,
    ) -> AlmaResponse:
        """Pay (in full or in part) a single fee.

        Calls
        ``POST /almaws/v1/users/{user_id}/fees/{fee_id}?op=pay&amount=...&method=...``.
        ``op``, ``amount``, ``method``, and (when supplied)
        ``external_transaction_id`` are sent as **query parameters**.

        Args:
            user_id: User identifier (primary ID, barcode, etc.). Must
                be a non-empty string.
            fee_id: Fee identifier. Must be a non-empty string.
            amount: ``"ALL"`` (sentinel — pay the full remaining balance)
                or a numeric string (e.g. ``"5.00"``). Validated
                client-side.
            method: Payment method (default ``"CASH"``).
            external_transaction_id: Optional external system identifier
                forwarded only when non-``None``.

        Returns:
            ``AlmaResponse`` wrapping the Alma response.

        Raises:
            AlmaValidationError: If any required input is empty/wrong
                type, or if ``amount`` is malformed.
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: pay_all_user_fees (above) — same op-driven
        # POST shape, scoped to a specific fee.
        if not isinstance(user_id, str) or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        if not isinstance(fee_id, str) or not fee_id.strip():
            raise AlmaValidationError("Fee ID cannot be empty")
        self._validate_pay_amount(amount)
        if not isinstance(method, str) or not method.strip():
            raise AlmaValidationError("method must be a non-empty string")
        clean_user_id = user_id.strip()
        clean_fee_id = fee_id.strip()

        params: Dict[str, Any] = {
            "op": "pay",
            "amount": amount.strip(),
            "method": method.strip(),
        }
        if external_transaction_id is not None:
            params["external_transaction_id"] = external_transaction_id

        endpoint = (
            f"almaws/v1/users/{clean_user_id}/fees/{clean_fee_id}"
        )
        self.logger.info(
            f"Paying fee {clean_fee_id} for user {clean_user_id} "
            f"(amount={params['amount']!r}, method={params['method']!r})"
        )
        try:
            response = self.client.post(endpoint, params=params)
            self.logger.info(
                f"Paid fee {clean_fee_id} for user {clean_user_id}"
            )
            return response
        except AlmaAPIError as e:
            self.logger.error(
                f"API error paying fee {clean_fee_id} for user "
                f"{clean_user_id}: {e}"
            )
            raise

    def waive_user_fee(
        self,
        user_id: str,
        fee_id: str,
        reason: str,
        amount: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> AlmaResponse:
        """Waive (in full or in part) a single fee.

        Calls
        ``POST /almaws/v1/users/{user_id}/fees/{fee_id}?op=waive&reason=...``.
        ``op``, ``reason``, and (when supplied) ``amount`` and
        ``comment`` are sent as **query parameters**. ``method`` is NOT
        sent on waive — only on pay / pay_all.

        Args:
            user_id: User identifier (primary ID, barcode, etc.). Must
                be a non-empty string.
            fee_id: Fee identifier. Must be a non-empty string.
            reason: Reason for the waiver. **Required** for ``op=waive``;
                empty / whitespace / non-string values raise
                :class:`AlmaValidationError`.
            amount: Optional partial-waive amount as a string (e.g.
                ``"3.00"``). When ``None``, Alma waives the full balance.
            comment: Optional free-text comment. Forwarded only when
                non-``None``.

        Returns:
            ``AlmaResponse`` wrapping the Alma response.

        Raises:
            AlmaValidationError: If any required input is empty/wrong
                type. ``reason`` is required.
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: pay_user_fee (above) — same op-driven POST
        # shape, but ``reason`` is required (audit fix #2: dispute does
        # NOT require reason; only waive does).
        if not isinstance(user_id, str) or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        if not isinstance(fee_id, str) or not fee_id.strip():
            raise AlmaValidationError("Fee ID cannot be empty")
        if not isinstance(reason, str) or not reason.strip():
            raise AlmaValidationError(
                "reason is required for op=waive and must be a non-empty string"
            )
        clean_user_id = user_id.strip()
        clean_fee_id = fee_id.strip()

        params: Dict[str, Any] = {
            "op": "waive",
            "reason": reason.strip(),
        }
        if amount is not None:
            params["amount"] = amount
        if comment is not None:
            params["comment"] = comment

        endpoint = (
            f"almaws/v1/users/{clean_user_id}/fees/{clean_fee_id}"
        )
        self.logger.info(
            f"Waiving fee {clean_fee_id} for user {clean_user_id} "
            f"(reason={params['reason']!r}, amount={amount!r})"
        )
        try:
            response = self.client.post(endpoint, params=params)
            self.logger.info(
                f"Waived fee {clean_fee_id} for user {clean_user_id}"
            )
            return response
        except AlmaAPIError as e:
            self.logger.error(
                f"API error waiving fee {clean_fee_id} for user "
                f"{clean_user_id}: {e}"
            )
            raise

    def dispute_user_fee(
        self,
        user_id: str,
        fee_id: str,
        reason: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> AlmaResponse:
        """Mark a single fee as disputed.

        Calls
        ``POST /almaws/v1/users/{user_id}/fees/{fee_id}?op=dispute``.
        ``op`` is always sent; ``reason`` and ``comment`` are sent only
        when non-``None``. ``method`` is NOT sent on dispute.

        Args:
            user_id: User identifier (primary ID, barcode, etc.). Must
                be a non-empty string.
            fee_id: Fee identifier. Must be a non-empty string.
            reason: **Optional** dispute reason. The audit (2026-05-08)
                corrected the original "reason required" bug — only
                ``waive`` requires a reason. Forwarded only when
                non-``None`` and non-empty.
            comment: Optional free-text comment. Forwarded only when
                non-``None``.

        Returns:
            ``AlmaResponse`` wrapping the Alma response.

        Raises:
            AlmaValidationError: If ``user_id`` or ``fee_id`` is empty.
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: waive_user_fee (above) — same op-driven POST
        # shape, but ``reason`` is OPTIONAL (audit fix #2).
        if not isinstance(user_id, str) or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        if not isinstance(fee_id, str) or not fee_id.strip():
            raise AlmaValidationError("Fee ID cannot be empty")
        clean_user_id = user_id.strip()
        clean_fee_id = fee_id.strip()

        params: Dict[str, Any] = {"op": "dispute"}
        # Only forward ``reason`` if a non-empty string was supplied —
        # an empty / whitespace value would just clutter the query
        # string. ``None`` default makes the arg fully optional.
        if reason is not None and isinstance(reason, str) and reason.strip():
            params["reason"] = reason.strip()
        if comment is not None:
            params["comment"] = comment

        endpoint = (
            f"almaws/v1/users/{clean_user_id}/fees/{clean_fee_id}"
        )
        self.logger.info(
            f"Disputing fee {clean_fee_id} for user {clean_user_id} "
            f"(reason={params.get('reason')!r})"
        )
        try:
            response = self.client.post(endpoint, params=params)
            self.logger.info(
                f"Disputed fee {clean_fee_id} for user {clean_user_id}"
            )
            return response
        except AlmaAPIError as e:
            self.logger.error(
                f"API error disputing fee {clean_fee_id} for user "
                f"{clean_user_id}: {e}"
            )
            raise

    def restore_user_fee(
        self,
        user_id: str,
        fee_id: str,
        comment: Optional[str] = None,
    ) -> AlmaResponse:
        """Restore a previously-disputed fee back to active status.

        Calls
        ``POST /almaws/v1/users/{user_id}/fees/{fee_id}?op=restore``.
        Only ``op`` and (optionally) ``comment`` are sent — no
        ``reason``, no ``amount``, no ``method``.

        Args:
            user_id: User identifier (primary ID, barcode, etc.). Must
                be a non-empty string.
            fee_id: Fee identifier. Must be a non-empty string.
            comment: Optional free-text comment. Forwarded only when
                non-``None``.

        Returns:
            ``AlmaResponse`` wrapping the Alma response.

        Raises:
            AlmaValidationError: If ``user_id`` or ``fee_id`` is empty.
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: dispute_user_fee (above) — same op-driven POST
        # shape; restore takes only the comment kwarg (audit fix #3:
        # no reason / amount / method).
        if not isinstance(user_id, str) or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        if not isinstance(fee_id, str) or not fee_id.strip():
            raise AlmaValidationError("Fee ID cannot be empty")
        clean_user_id = user_id.strip()
        clean_fee_id = fee_id.strip()

        params: Dict[str, Any] = {"op": "restore"}
        if comment is not None:
            params["comment"] = comment

        endpoint = (
            f"almaws/v1/users/{clean_user_id}/fees/{clean_fee_id}"
        )
        self.logger.info(
            f"Restoring fee {clean_fee_id} for user {clean_user_id}"
        )
        try:
            response = self.client.post(endpoint, params=params)
            self.logger.info(
                f"Restored fee {clean_fee_id} for user {clean_user_id}"
            )
            return response
        except AlmaAPIError as e:
            self.logger.error(
                f"API error restoring fee {clean_fee_id} for user "
                f"{clean_user_id}: {e}"
            )
            raise

    # ------------------------------------------------------------------
    # User deposits (issue #45)
    # ------------------------------------------------------------------
    #
    # The deposits endpoints expose three reads (list/get/create) and one
    # op-driven post (perform-action via ``op`` query param). The op-driven
    # post mirrors exactly the shape established by the fines/fees op-posts
    # (issue #44) — ``op`` and any caller-supplied scalars travel as query
    # parameters; the request body is empty. The wrapper does NOT enumerate
    # which ``op`` values are valid (Alma docs cite ``pay`` / ``refund`` /
    # ``dispute`` / ``restore`` but a future Alma release may add more);
    # we just validate non-empty and let Alma reject invalid ops with its
    # own error response.
    #
    # Read patterns mirror ``list_user_attachments`` / ``get_user_attachment``
    # (issue #39) and ``list_user_fees`` / ``get_user_fee`` (issue #44).

    def list_user_deposits(self, user_id: str) -> List[Dict[str, Any]]:
        """List a user's deposits.

        Calls ``GET /almaws/v1/users/{user_id}/deposits`` and unwraps the
        Alma response envelope (``{"deposit": [...], "total_record_count":
        N}``) into a flat list.

        Args:
            user_id: User identifier (primary ID, barcode, etc.). Must
                be a non-empty string.

        Returns:
            List of deposit dicts as returned by Alma. Returns an empty
            list when the user has no deposits (or when the response
            envelope is missing the ``deposit`` key).

        Raises:
            AlmaValidationError: If ``user_id`` is empty or not a string.
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: list_user_attachments (issue #39) for the
        # "single GET, unwrap envelope, return list" idiom plus
        # single-record-as-dict normalisation.
        if not isinstance(user_id, str) or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        clean_id = user_id.strip()

        endpoint = f"almaws/v1/users/{clean_id}/deposits"
        self.logger.info(
            f"Listing deposits for user {clean_id}"
        )
        try:
            response = self.client.get(endpoint)
            payload = response.json() or {}
            deposits = payload.get("deposit") or []
            if isinstance(deposits, dict):
                # Single-record responses can come back as a dict; normalise.
                deposits = [deposits]
            self.logger.info(
                f"Retrieved {len(deposits)} deposits for user {clean_id}"
            )
            return deposits
        except AlmaAPIError as e:
            self.logger.error(
                f"API error listing deposits for user {clean_id}: {e}"
            )
            raise

    def create_user_deposit(
        self,
        user_id: str,
        deposit_data: Dict[str, Any],
    ) -> AlmaResponse:
        """Create a new deposit on a user record.

        Calls ``POST /almaws/v1/users/{user_id}/deposits`` with the
        operator-supplied ``deposit_data`` dict as the JSON body. The
        body is passed through verbatim — the caller is responsible for
        supplying the Alma-required fields (see Alma's ``X parameter is
        not valid.`` / ``Input parameter X (Y) is not numeric.`` /
        ``General Error - An error has occurred while creating the
        deposit.`` validation errors).

        Args:
            user_id: User identifier (primary ID, barcode, etc.). Must
                be a non-empty string.
            deposit_data: Deposit body as a non-empty dict. Passed
                through to Alma verbatim.

        Returns:
            ``AlmaResponse`` wrapping the Alma response. The created
            deposit's identifier lives at ``response.data["id"]``.

        Raises:
            AlmaValidationError: If ``user_id`` is empty/not a string,
                or if ``deposit_data`` is empty or not a dict.
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: create_user_fee (issue #44) for the
        # "validate, log entry without body, POST verbatim, log success
        # with the new id" discipline.
        if not isinstance(user_id, str) or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        if not isinstance(deposit_data, dict) or not deposit_data:
            raise AlmaValidationError(
                "deposit_data must be a non-empty dictionary"
            )
        clean_id = user_id.strip()

        endpoint = f"almaws/v1/users/{clean_id}/deposits"
        self.logger.info(
            f"Creating deposit for user {clean_id}"
        )
        try:
            response = self.client.post(endpoint, data=deposit_data)
            deposit_id: Any = None
            try:
                deposit_id = (response.data or {}).get("id")
            except (ValueError, AttributeError):
                deposit_id = None
            self.logger.info(
                f"Created deposit for user {clean_id} "
                f"(deposit_id={deposit_id!r})"
            )
            return response
        except AlmaAPIError as e:
            self.logger.error(
                f"API error creating deposit for user {clean_id}: {e}"
            )
            raise

    def get_user_deposit(
        self,
        user_id: str,
        deposit_id: str,
    ) -> Dict[str, Any]:
        """Retrieve a single deposit's details.

        Calls ``GET /almaws/v1/users/{user_id}/deposits/{deposit_id}``
        and returns the unwrapped deposit dict.

        Args:
            user_id: User identifier (primary ID, barcode, etc.). Must
                be a non-empty string.
            deposit_id: Deposit identifier as returned by
                :meth:`list_user_deposits` (key ``id`` on each entry).
                Must be a non-empty string.

        Returns:
            The deposit dict as returned by Alma.

        Raises:
            AlmaValidationError: If ``user_id`` or ``deposit_id`` is
                empty or not a string.
            AlmaAPIError: If the API request fails (including 404 when
                the user or deposit does not exist).
        """
        # Pattern source: get_user_attachment (issue #39) / get_user_fee
        # (issue #44) — same "validate two ids, GET, return dict" shape.
        if not isinstance(user_id, str) or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        if not isinstance(deposit_id, str) or not deposit_id.strip():
            raise AlmaValidationError("Deposit ID cannot be empty")
        clean_user_id = user_id.strip()
        clean_deposit_id = deposit_id.strip()

        endpoint = (
            f"almaws/v1/users/{clean_user_id}/deposits/{clean_deposit_id}"
        )
        self.logger.info(
            f"Retrieving deposit {clean_deposit_id} for user "
            f"{clean_user_id}"
        )
        try:
            response = self.client.get(endpoint)
            data: Dict[str, Any] = response.json() or {}
            self.logger.info(
                f"Retrieved deposit {clean_deposit_id} for user "
                f"{clean_user_id}"
            )
            return data
        except AlmaAPIError as e:
            self.logger.error(
                f"API error retrieving deposit {clean_deposit_id} for "
                f"user {clean_user_id}: {e}"
            )
            raise

    def perform_user_deposit_action(
        self,
        user_id: str,
        deposit_id: str,
        op: str,
    ) -> AlmaResponse:
        """Perform an action on a single deposit.

        Calls
        ``POST /almaws/v1/users/{user_id}/deposits/{deposit_id}?op=<op>``
        with an empty request body. The ``op`` query parameter selects
        the deposit action — Alma's documented values include ``"pay"``,
        ``"refund"``, ``"dispute"``, and ``"restore"``, but the wrapper
        does NOT enumerate / restrict the set: invalid ops are rejected
        by Alma with its own error response (a future Alma release may
        add new ops, and the wrapper should not be the bottleneck).

        Args:
            user_id: User identifier (primary ID, barcode, etc.). Must
                be a non-empty string.
            deposit_id: Deposit identifier. Must be a non-empty string.
            op: Action to perform. Must be a non-empty string. Common
                values per Alma docs are ``"pay"``, ``"refund"``,
                ``"dispute"``, ``"restore"`` — not validated client-side.

        Returns:
            ``AlmaResponse`` wrapping the Alma response.

        Raises:
            AlmaValidationError: If ``user_id``, ``deposit_id``, or
                ``op`` is empty/not a string.
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: restore_user_fee (issue #44) — same op-driven
        # POST shape (op as query param, empty body). The wrapper is
        # deliberately op-agnostic; per the issue ticket "let Alma
        # reject invalid ops with its own error".
        if not isinstance(user_id, str) or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        if not isinstance(deposit_id, str) or not deposit_id.strip():
            raise AlmaValidationError("Deposit ID cannot be empty")
        if not isinstance(op, str) or not op.strip():
            raise AlmaValidationError("op must be a non-empty string")
        clean_user_id = user_id.strip()
        clean_deposit_id = deposit_id.strip()
        clean_op = op.strip()

        params: Dict[str, Any] = {"op": clean_op}

        endpoint = (
            f"almaws/v1/users/{clean_user_id}/deposits/{clean_deposit_id}"
        )
        self.logger.info(
            f"Performing deposit action for user {clean_user_id} "
            f"(deposit_id={clean_deposit_id!r}, op={clean_op!r})"
        )
        try:
            response = self.client.post(endpoint, params=params)
            self.logger.info(
                f"Performed deposit action for user {clean_user_id} "
                f"(deposit_id={clean_deposit_id!r}, op={clean_op!r})"
            )
            return response
        except AlmaAPIError as e:
            self.logger.error(
                f"API error performing deposit action for user "
                f"{clean_user_id} (deposit_id={clean_deposit_id!r}, "
                f"op={clean_op!r}): {e}"
            )
            raise

    # -----------------------------------------------------------------
    # Loans (issue #40)
    # -----------------------------------------------------------------

    def list_user_loans(
        self,
        user_id: str,
        limit: int = 10,
        offset: int = 0,
        expand: Optional[str] = None,
        order_by: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List a user's active loans.

        Calls ``GET /almaws/v1/users/{user_id}/loans`` and unwraps the
        Alma response envelope (``{"item_loan": [...],
        "total_record_count": N}``) into a flat list. Pagination
        parameters are forwarded to Alma; ``expand`` and ``order_by``
        are forwarded only when supplied.

        Args:
            user_id: User identifier (primary ID, barcode, etc.). Must
                be a non-empty string.
            limit: Page size (Alma default 10, valid range 0-100).
                Forwarded as ``limit`` query parameter.
            offset: Page offset (Alma default 0). Forwarded as
                ``offset`` query parameter.
            expand: Optional comma-separated expand values
                (e.g. ``"renewable"``). Forwarded only when non-``None``.
            order_by: Optional sort key (e.g. ``"due_date"``,
                ``"loan_date"``, ``"barcode"``, ``"title"``).
                Forwarded only when non-``None``.

        Returns:
            List of loan dicts as returned by Alma. Returns an empty
            list when the user has no loans (or when the response
            envelope lacks the ``item_loan`` key).

        Raises:
            AlmaValidationError: If ``user_id`` is empty or not a string.
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: list_user_fees (issue #44) for the
        # "single GET, unwrap envelope, return list" idiom plus
        # single-record-as-dict normalisation; list_users (issue #36)
        # for the optional-filter forwarding pattern. Swagger:
        # GET /almaws/v1/users/{user_id}/loans returns rest_item_loans.
        if not isinstance(user_id, str) or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        clean_id = user_id.strip()

        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if expand is not None:
            params["expand"] = expand
        if order_by is not None:
            params["order_by"] = order_by

        endpoint = f"almaws/v1/users/{clean_id}/loans"
        self.logger.info(
            f"Listing loans for user {clean_id} "
            f"(limit={limit}, offset={offset}, expand={expand!r}, "
            f"order_by={order_by!r})"
        )
        try:
            response = self.client.get(endpoint, params=params)
            payload = response.json() or {}
            loans = payload.get("item_loan") or []
            if isinstance(loans, dict):
                # Single-record responses can come back as a dict; normalise.
                loans = [loans]
            self.logger.info(
                f"Retrieved {len(loans)} loans for user {clean_id}"
            )
            return loans
        except AlmaAPIError as e:
            self.logger.error(
                f"API error listing loans for user {clean_id}: {e}"
            )
            raise

    def create_user_loan(
        self,
        user_id: str,
        item_barcode: Optional[str] = None,
        item_pid: Optional[str] = None,
        user_id_type: Optional[str] = None,
        loan_data: Optional[Dict[str, Any]] = None,
    ) -> AlmaResponse:
        """Create (loan) an item to a user.

        Calls ``POST /almaws/v1/users/{user_id}/loans``. Per the Alma
        OpenAPI spec, ``item_barcode``, ``item_pid``, and
        ``user_id_type`` are **query parameters**; the request body is
        the Loan object (``rest_item_loan-post.json``) carrying
        ``circ_desk`` / ``library`` and any other Alma-accepted fields.
        Exactly one of ``item_barcode`` or ``item_pid`` must be
        supplied; ``loan_data`` is optional (Alma can derive
        circ_desk / library from the operator context for some flows).

        Args:
            user_id: User identifier (primary ID, barcode, etc.). Must
                be a non-empty string.
            item_barcode: The Item barcode. Mutually exclusive with
                ``item_pid``; forwarded as a **query** parameter when
                supplied.
            item_pid: The Item PID. Mutually exclusive with
                ``item_barcode``; forwarded as a **query** parameter when
                supplied.
            user_id_type: Optional user identifier type (any value from
                the Alma "User Identifier Type" code table, e.g.
                ``"all_unique"`` / ``"BARCODE"``). Forwarded as a
                **query** parameter only when non-``None``.
            loan_data: Optional Loan body dict (e.g.
                ``{"circ_desk": {"value": "DEFAULT_CIRC_DESK"},
                "library": {"value": "MAIN"}}``). When ``None``, no
                body is sent and Alma applies its defaults.

        Returns:
            ``AlmaResponse`` wrapping the Alma response. The created
            loan's identifier lives at ``response.data["loan_id"]``.

        Raises:
            AlmaValidationError: If ``user_id`` is empty / not a string,
                if neither or both of ``item_barcode`` / ``item_pid``
                are supplied, or if ``loan_data`` is supplied but is
                not a dict.
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: create_user_fee (issue #44) for "validate,
        # log entry, POST with body, log success with new id"; and
        # pay_user_fee (issue #44) for "build params dict dynamically,
        # only include non-None keys". Swagger: POST
        # /almaws/v1/users/{user_id}/loans uses query params for the
        # item / user_id_type identifiers and accepts a Loan body.
        if not isinstance(user_id, str) or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        if item_barcode is not None and item_pid is not None:
            raise AlmaValidationError(
                "Exactly one of item_barcode or item_pid must be supplied "
                "(got both)"
            )
        if item_barcode is None and item_pid is None:
            raise AlmaValidationError(
                "Exactly one of item_barcode or item_pid must be supplied "
                "(got neither)"
            )
        if loan_data is not None and not isinstance(loan_data, dict):
            raise AlmaValidationError(
                "loan_data must be a dict when supplied"
            )
        clean_id = user_id.strip()

        params: Dict[str, Any] = {}
        if item_barcode is not None:
            params["item_barcode"] = item_barcode
        if item_pid is not None:
            params["item_pid"] = item_pid
        if user_id_type is not None:
            params["user_id_type"] = user_id_type

        endpoint = f"almaws/v1/users/{clean_id}/loans"
        # Audit-log: only the user_id and the item identifier — never
        # the full loan_data (may carry patron-adjacent fields).
        self.logger.info(
            f"Creating loan for user {clean_id} "
            f"(item_barcode={item_barcode!r}, item_pid={item_pid!r})"
        )
        try:
            response = self.client.post(
                endpoint,
                data=loan_data,
                params=params if params else None,
            )
            loan_id: Any = None
            try:
                loan_id = (response.data or {}).get("loan_id")
            except (ValueError, AttributeError):
                loan_id = None
            self.logger.info(
                f"Created loan for user {clean_id} (loan_id={loan_id!r})"
            )
            return response
        except AlmaAPIError as e:
            self.logger.error(
                f"API error creating loan for user {clean_id} "
                f"(item_barcode={item_barcode!r}, item_pid={item_pid!r}): {e}"
            )
            raise

    def get_user_loan(
        self,
        user_id: str,
        loan_id: str,
    ) -> Dict[str, Any]:
        """Retrieve a single loan's details.

        Calls ``GET /almaws/v1/users/{user_id}/loans/{loan_id}`` and
        returns the unwrapped loan dict.

        Args:
            user_id: User identifier (primary ID, barcode, etc.). Must
                be a non-empty string.
            loan_id: Loan identifier. Must be a non-empty string.

        Returns:
            The loan dict as returned by Alma.

        Raises:
            AlmaValidationError: If ``user_id`` or ``loan_id`` is empty
                or not a string.
            AlmaAPIError: If the API request fails (including 400 with
                error code ``401823`` when the loan does not exist).
        """
        # Pattern source: get_user_fee (issue #44) — same
        # "validate two ids, GET, return dict" shape.
        if not isinstance(user_id, str) or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        if not isinstance(loan_id, str) or not loan_id.strip():
            raise AlmaValidationError("Loan ID cannot be empty")
        clean_user_id = user_id.strip()
        clean_loan_id = loan_id.strip()

        endpoint = (
            f"almaws/v1/users/{clean_user_id}/loans/{clean_loan_id}"
        )
        self.logger.info(
            f"Retrieving loan {clean_loan_id} for user {clean_user_id}"
        )
        try:
            response = self.client.get(endpoint)
            data: Dict[str, Any] = response.json() or {}
            self.logger.info(
                f"Retrieved loan {clean_loan_id} for user {clean_user_id}"
            )
            return data
        except AlmaAPIError as e:
            self.logger.error(
                f"API error retrieving loan {clean_loan_id} for user "
                f"{clean_user_id}: {e}"
            )
            raise

    def renew_user_loan(
        self,
        user_id: str,
        loan_id: str,
    ) -> AlmaResponse:
        """Renew a single loan.

        Calls
        ``POST /almaws/v1/users/{user_id}/loans/{loan_id}?op=renew``
        with an empty request body. The swagger documents only
        ``op=renew`` for this endpoint.

        Args:
            user_id: User identifier (primary ID, barcode, etc.). Must
                be a non-empty string.
            loan_id: Loan identifier. Must be a non-empty string.

        Returns:
            ``AlmaResponse`` wrapping the Alma response (the renewed
            loan body, including the new ``due_date``).

        Raises:
            AlmaValidationError: If ``user_id`` or ``loan_id`` is empty
                or not a string.
            AlmaAPIError: If the API request fails (e.g. error code
                ``401822`` "Cannot renew loan" or ``401823``
                "Loan ID does not exist").
        """
        # Pattern source: perform_user_deposit_action (issue #45) —
        # same op-driven POST shape (op as query param, empty body).
        # Pinned to op=renew per the swagger ("currently only op=renew
        # is supported").
        if not isinstance(user_id, str) or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        if not isinstance(loan_id, str) or not loan_id.strip():
            raise AlmaValidationError("Loan ID cannot be empty")
        clean_user_id = user_id.strip()
        clean_loan_id = loan_id.strip()

        params: Dict[str, Any] = {"op": "renew"}

        endpoint = (
            f"almaws/v1/users/{clean_user_id}/loans/{clean_loan_id}"
        )
        self.logger.info(
            f"Renewing loan {clean_loan_id} for user {clean_user_id}"
        )
        try:
            response = self.client.post(endpoint, params=params)
            self.logger.info(
                f"Renewed loan {clean_loan_id} for user {clean_user_id}"
            )
            return response
        except AlmaAPIError as e:
            self.logger.error(
                f"API error renewing loan {clean_loan_id} for user "
                f"{clean_user_id}: {e}"
            )
            raise

    def update_user_loan(
        self,
        user_id: str,
        loan_id: str,
        loan_data: Dict[str, Any],
    ) -> AlmaResponse:
        """Update a loan (typically the due date).

        Calls ``PUT /almaws/v1/users/{user_id}/loans/{loan_id}`` with
        ``loan_data`` as the JSON body. The swagger documents this
        endpoint as "Change loan due date" — Alma's typical use is to
        ship a body containing at least ``{"due_date": "<ISO-8601>"}``.
        The body is passed through verbatim; the caller is responsible
        for the loan-object shape.

        Args:
            user_id: User identifier (primary ID, barcode, etc.). Must
                be a non-empty string.
            loan_id: Loan identifier. Must be a non-empty string.
            loan_data: Loan body as a non-empty dict. Passed through to
                Alma verbatim.

        Returns:
            ``AlmaResponse`` wrapping the Alma response (the updated
            loan body).

        Raises:
            AlmaValidationError: If ``user_id`` / ``loan_id`` is empty,
                or if ``loan_data`` is empty / not a dict.
            AlmaAPIError: If the API request fails (e.g. error code
                ``401824`` "Due date is not in loan object" or
                ``401681`` "Due date cannot be in the past").
        """
        # Pattern source: update_user (above) — same
        # "validate ids + non-empty dict, PUT body verbatim" shape.
        if not isinstance(user_id, str) or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        if not isinstance(loan_id, str) or not loan_id.strip():
            raise AlmaValidationError("Loan ID cannot be empty")
        if not isinstance(loan_data, dict) or not loan_data:
            raise AlmaValidationError(
                "loan_data must be a non-empty dictionary"
            )
        clean_user_id = user_id.strip()
        clean_loan_id = loan_id.strip()

        endpoint = (
            f"almaws/v1/users/{clean_user_id}/loans/{clean_loan_id}"
        )
        # Audit-log: never log the full loan_data body (may include
        # patron-adjacent free-text fields like notes).
        self.logger.info(
            f"Updating loan {clean_loan_id} for user {clean_user_id}"
        )
        try:
            response = self.client.put(endpoint, data=loan_data)
            self.logger.info(
                f"Updated loan {clean_loan_id} for user {clean_user_id}"
            )
            return response
        except AlmaAPIError as e:
            self.logger.error(
                f"API error updating loan {clean_loan_id} for user "
                f"{clean_user_id}: {e}"
            )
            raise

    def create_user(self, user_data: Dict[str, Any]) -> AlmaResponse:
        """Create a new Alma user.

        Wraps ``POST /almaws/v1/users``. ``user_data`` is passed through
        to Alma verbatim — the caller is responsible for supplying any
        optional fields (emails, addresses, identifiers, user statistics,
        etc.). This method validates only the four core fields Alma
        requires to materialise a user record:

        - ``primary_id`` (str)
        - ``account_type`` (str or ``{"value": "..."}`` dict)
        - ``status`` (str or ``{"value": "..."}`` dict)
        - ``user_group`` (str or ``{"value": "..."}`` dict)

        The ``{"value": "..."}`` wrapper is the canonical shape Alma
        returns on reads; both the bare string and the wrapper dict are
        accepted so callers can round-trip a user object without having
        to reshape it before sending it back.

        Args:
            user_data: User object payload. Must be a non-empty dict
                containing the four required keys above. Any extra keys
                are forwarded verbatim and validated by Alma server-side.

        Returns:
            ``AlmaResponse`` wrapping the create response. The created
            user's primary identifier lives at
            ``response.data["primary_id"]``.

        Raises:
            AlmaValidationError: If ``user_data`` is empty/not a dict, or
                if any of ``primary_id`` / ``account_type`` / ``status``
                / ``user_group`` is missing or empty.
            AlmaAPIError: If the API request fails (typed subclass when
                the Alma error code or HTTP status maps to one — see
                ``AlmaAPIClient._classify_error``).

        Example:
            >>> response = users.create_user({
            ...     "primary_id": "<user_primary_id>",
            ...     "account_type": {"value": "INTERNAL"},
            ...     "status": {"value": "ACTIVE"},
            ...     "user_group": {"value": "STAFF"},
            ...     "first_name": "Ada",
            ...     "last_name": "Lovelace",
            ... })
            >>> created_id = response.data["primary_id"]
        """
        # Pattern source: Admin.create_set (issue #23) — same
        # validate-via-helper / log-without-body / POST-verbatim shape,
        # including the bare-string-vs-{"value": ...}-dict acceptance.
        # See also Users.create_user_fee (above, issue #44) for the
        # state-changing log discipline (entry, success, error with
        # alma_code + tracking_id).
        self._validate_user_data_for_create(user_data)
        primary_id = user_data.get("primary_id")

        # Audit-log shape per R9 (no PII): only the primary_id and a
        # count of top-level keys on the body. Never log the full body —
        # it may contain personal data, addresses, identifiers, etc.
        self.logger.info(
            f"Creating user: {primary_id} (user_data_keys={len(user_data)})"
        )

        try:
            response = self.client.post("almaws/v1/users", data=user_data)
            created_primary_id = None
            try:
                created_primary_id = response.data.get("primary_id")
            except (ValueError, AttributeError):
                # Body may not be JSON / dict; the response itself is
                # still a valid AlmaResponse and we should hand it back.
                created_primary_id = None

            if created_primary_id:
                self.logger.info(
                    f"Created user: {created_primary_id}"
                )
            else:
                self.logger.info(
                    f"Created user: {primary_id}"
                )
            return response

        except AlmaAPIError as e:
            alma_code = getattr(e, "alma_code", "")
            tracking_id = getattr(e, "tracking_id", None)
            self.logger.error(
                f"API error creating user {primary_id}: {e} "
                f"(alma_code={alma_code!r}, tracking_id={tracking_id!r})"
            )
            raise

    def delete_user(self, user_id: str) -> AlmaResponse:
        """Delete a user by primary id.

        Wraps ``DELETE /almaws/v1/users/{user_id}``. Alma rejects the
        delete when the user has active loans, requests, or unpaid fees
        — those rejections surface as ``AlmaAPIError`` with the Alma
        error code intact for the caller to dispatch on.

        Args:
            user_id: The user's primary identifier (or any other
                Alma-accepted id type). Must be a non-empty string.

        Returns:
            ``AlmaResponse`` wrapping the delete response. Alma typically
            echoes the deleted user's payload back in the body, which is
            useful for audit trails — callers that record deletions
            should persist ``response.data`` before discarding the
            response.

        Raises:
            AlmaValidationError: If ``user_id`` is empty or not a string.
            AlmaAPIError: On API failure (typed subclass when the Alma
                error code or HTTP status maps to one — e.g.,
                ``AlmaResourceNotFoundError`` for an unknown user). The
                exception carries ``alma_code`` and ``tracking_id`` so
                callers can surface the precise reason (active loans,
                outstanding fees, etc.).
        """
        # Pattern source: Admin.delete_set (issue #23) — same
        # validate-id / log entry / DELETE / log success / log error with
        # alma_code + tracking_id shape.
        if not isinstance(user_id, str) or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        clean_id = user_id.strip()

        self.logger.info(f"Deleting user: {clean_id}")

        try:
            response = self.client.delete(f"almaws/v1/users/{clean_id}")
            self.logger.info(f"Deleted user: {clean_id}")
            return response

        except AlmaAPIError as e:
            alma_code = getattr(e, "alma_code", "")
            tracking_id = getattr(e, "tracking_id", None)
            self.logger.error(
                f"API error deleting user {clean_id}: {e} "
                f"(alma_code={alma_code!r}, tracking_id={tracking_id!r})"
            )
            raise

    @staticmethod
    def _validate_user_data_for_create(user_data: Any) -> None:
        """Validate the ``user_data`` argument to ``create_user``.

        Enforces the four core fields Alma requires on user creation:
        ``primary_id``, ``account_type``, ``status``, ``user_group``.
        The latter three accept either a bare string or the canonical
        ``{"value": "..."}`` wrapper dict (the shape Alma returns on
        reads).

        Args:
            user_data: Candidate payload for ``create_user``.

        Raises:
            AlmaValidationError: If ``user_data`` is not a non-empty
                dict, or if any required key is missing or empty.
        """
        # Pattern source: Admin._validate_set_data_for_create (issue
        # #23) — same {bare-string | {"value": ...} dict} acceptance.
        if not isinstance(user_data, dict) or not user_data:
            raise AlmaValidationError(
                "user_data must be a non-empty dict"
            )

        primary_id = user_data.get("primary_id")
        if not isinstance(primary_id, str) or not primary_id.strip():
            raise AlmaValidationError(
                "user_data['primary_id'] is required and must be a "
                "non-empty string"
            )

        for field in ("account_type", "status", "user_group"):
            value = user_data.get(field)
            if isinstance(value, dict):
                inner = value.get("value")
                if not isinstance(inner, str) or not inner.strip():
                    raise AlmaValidationError(
                        f"user_data[{field!r}]['value'] is required and "
                        f"must be a non-empty string"
                    )
            elif isinstance(value, str):
                if not value.strip():
                    raise AlmaValidationError(
                        f"user_data[{field!r}] must be a non-empty string"
                    )
            else:
                raise AlmaValidationError(
                    f"user_data[{field!r}] is required (string or "
                    f"{{'value': '<CODE>'}} dict)"
                )

    def update_user(self, user_id: str, user_data: Dict[str, Any]) -> AlmaResponse:
        """
        Update a user record.

        Args:
            user_id: User identifier
            user_data: Complete user data to update

        Returns:
            AlmaResponse containing updated user data

        Raises:
            AlmaValidationError: If user_id is empty or user_data is invalid
            AlmaAPIError: If API request fails
        """
        if not user_id or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")

        if not user_data or not isinstance(user_data, dict):
            raise AlmaValidationError("User data must be a non-empty dictionary")

        endpoint = f'almaws/v1/users/{user_id.strip()}'

        try:
            response = self.client.put(endpoint, data=user_data)
            self.logger.info(f"Updated user {user_id}")
            return response

        except AlmaAPIError as e:
            self.logger.error(f"API error updating user {user_id}: {e}")
            raise
    
    # Expiry Date Analysis Methods
    
    def get_user_expiry_date(self, user_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract expiry date from user data.
        
        Args:
            user_data: User data from Alma API
        
        Returns:
            Expiry date as string (YYYY-MM-DDTZ format) or None if not found
        """
        try:
            expiry_date = user_data.get('expiry_date')
            if expiry_date and isinstance(expiry_date, str):
                return expiry_date.strip()
            return None
        except Exception as e:
            self.logger.error(f"Error extracting expiry date: {e}")
            return None
    
    def parse_expiry_date(self, expiry_date_str: str) -> Optional[datetime]:
        """
        Parse Alma expiry date string to datetime object.
        
        Args:
            expiry_date_str: Expiry date string from Alma (YYYY-MM-DDTZ format)
        
        Returns:
            datetime object or None if parsing fails
        """
        if not expiry_date_str:
            return None
        
        try:
            # Handle Alma date format: remove 'Z' suffix if present
            clean_date = expiry_date_str.replace('Z', '')
            
            # Parse the date (assuming YYYY-MM-DD format)
            expiry_dt = datetime.strptime(clean_date, '%Y-%m-%d')
            return expiry_dt
            
        except ValueError as e:
            self.logger.error(f"Error parsing expiry date '{expiry_date_str}': {e}")
            return None
    
    def is_user_expired_years(self, user_data: Dict[str, Any], years_threshold: int = 2) -> Tuple[bool, Optional[int]]:
        """
        Check if user is expired for the specified number of years or more.
        
        Args:
            user_data: User data from Alma API
            years_threshold: Minimum years expired to return True (default: 2)
        
        Returns:
            Tuple of (is_expired_enough, years_expired)
            - is_expired_enough: True if expired >= years_threshold
            - years_expired: Number of years expired (None if no expiry date)
        """
        expiry_date_str = self.get_user_expiry_date(user_data)
        if not expiry_date_str:
            self.logger.debug("User has no expiry date")
            return False, None
        
        expiry_dt = self.parse_expiry_date(expiry_date_str)
        if not expiry_dt:
            self.logger.warning(f"Could not parse expiry date: {expiry_date_str}")
            return False, None
        
        # Calculate years expired
        today = datetime.now()
        time_diff = today - expiry_dt
        years_expired = time_diff.days // 365  # Simple years calculation
        
        is_expired_enough = years_expired >= years_threshold
        
        self.logger.debug(f"User expired {years_expired} years ago, threshold: {years_threshold}, qualifies: {is_expired_enough}")
        return is_expired_enough, years_expired
    
    # Email Management Methods
    
    def extract_user_emails(self, user_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract all email addresses from user data.
        
        Args:
            user_data: User data from Alma API
        
        Returns:
            List of email dictionaries with type, address, and preferred status
        """
        emails = []
        
        try:
            contact_info = user_data.get('contact_info', {})
            email_list = contact_info.get('email', [])
            
            # Handle three possible cases for email_list
            if isinstance(email_list, dict):
                # Single email as dict
                email_list = [email_list]
            elif not isinstance(email_list, list):
                # No emails or invalid format
                email_list = []
            
            for email_entry in email_list:
                if isinstance(email_entry, dict):
                    email_address = email_entry.get('email_address', '').strip()
                    if email_address:
                        email_info = {
                            'address': email_address,
                            'type': self._extract_email_type(email_entry),
                            'preferred': email_entry.get('preferred', False),
                            'original_entry': email_entry  # Keep for updates
                        }
                        emails.append(email_info)
            
            self.logger.debug(f"Extracted {len(emails)} emails from user")
            return emails
            
        except Exception as e:
            self.logger.error(f"Error extracting user emails: {e}")
            return []
    
    def _extract_email_type(self, email_entry: Dict[str, Any]) -> str:
        """Extract email type from email entry."""
        email_type = email_entry.get('email_type', {})
        if isinstance(email_type, dict):
            return email_type.get('value', 'unknown')
        return str(email_type) if email_type else 'unknown'
    
    def validate_email(self, email: str) -> bool:
        """
        Validate email format.
        
        Args:
            email: Email address to validate
        
        Returns:
            True if valid, False otherwise
        """
        if not email or not isinstance(email, str):
            return False
        
        # Basic email validation regex
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_pattern, email.strip()) is not None
    
    def generate_new_email(self, user_data: Dict[str, Any], email_pattern: str) -> str:
        """
        Generate new email address using pattern and user data.
        
        Args:
            user_data: User data from Alma API
            email_pattern: Email pattern with placeholders like "expired-{user_id}@institution.edu"
        
        Returns:
            Generated email address
            
        Raises:
            AlmaValidationError: If pattern is invalid or required data is missing
        """
        if not email_pattern or '{user_id}' not in email_pattern:
            raise AlmaValidationError("Email pattern must contain {user_id} placeholder")
        
        try:
            # Extract user information for pattern replacement
            user_id = user_data.get('primary_id', '')
            first_name = user_data.get('first_name', '').lower()
            last_name = user_data.get('last_name', '').lower()
            
            if not user_id:
                raise AlmaValidationError("User ID not found in user data")
            
            # Replace placeholders
            new_email = email_pattern.format(
                user_id=user_id,
                first_name=first_name,
                last_name=last_name
            )
            
            if not self.validate_email(new_email):
                raise AlmaValidationError(f"Generated email is invalid: {new_email}")
            
            return new_email
            
        except KeyError as e:
            raise AlmaValidationError(f"Unknown placeholder in email pattern: {e}")
        except Exception as e:
            raise AlmaValidationError(f"Error generating email: {e}")
    
    def update_user_email(self, user_id: str, new_email: str, email_type: str = 'personal') -> AlmaResponse:
        """
        Update a user's primary email address.
        
        Args:
            user_id: User identifier
            new_email: New email address
            email_type: Type of email (personal, work, etc.)
        
        Returns:
            AlmaResponse containing updated user data
            
        Raises:
            AlmaValidationError: If inputs are invalid
            AlmaAPIError: If API request fails
        """
        if not self.validate_email(new_email):
            raise AlmaValidationError(f"Invalid email format: {new_email}")
        
        try:
            # Get current user data
            user_response = self.get_user(user_id)
            user_data = user_response.json()
            
            # Get current contact info
            contact_info = user_data.get('contact_info', {})
            email_list = contact_info.get('email', [])
            
            # Handle email list format
            if isinstance(email_list, dict):
                email_list = [email_list]
            elif not isinstance(email_list, list):
                email_list = []
            
            # Update existing email or add new one
            email_updated = False
            for email_entry in email_list:
                if isinstance(email_entry, dict):
                    # Update preferred email or the first one if only one exists
                    if email_entry.get('preferred', False) or len(email_list) == 1:
                        email_entry['email_address'] = new_email
                        email_updated = True
                        break
            
            # If no email was updated, add a new one
            if not email_updated:
                new_email_entry = {
                    'email_address': new_email,
                    'email_type': {'value': email_type},
                    'preferred': True
                }
                email_list.append(new_email_entry)
            
            # Update the user data
            contact_info['email'] = email_list
            user_data['contact_info'] = contact_info
            
            # Send the update to Alma
            response = self.update_user(user_id, user_data)
            self.logger.info(f"Updated email for user {user_id} to {new_email}")
            return response
            
        except AlmaAPIError:
            raise  # Re-raise API errors
        except Exception as e:
            raise AlmaAPIError(f"Failed to update user email: {e}")
    
    # Set-Based Processing Methods
    
    def process_user_for_expiry(self, user_id: str, years_threshold: int = 2) -> Dict[str, Any]:
        """
        Process a single user to determine if they qualify for email update.
        
        Args:
            user_id: User identifier
            years_threshold: Minimum years expired to qualify
        
        Returns:
            Dict with processing results including qualification status
        """
        result = {
            'user_id': user_id,
            'success': False,
            'qualifies_for_update': False,
            'error': None,
            'user_data': None,
            'emails': [],
            'years_expired': None,
            'expiry_date': None
        }
        
        try:
            # Get user data
            user_response = self.get_user(user_id)
            user_data = user_response.json()
            result['user_data'] = user_data
            result['success'] = True
            
            # Check expiry status
            is_expired_enough, years_expired = self.is_user_expired_years(user_data, years_threshold)
            result['years_expired'] = years_expired
            result['expiry_date'] = self.get_user_expiry_date(user_data)
            
            # Extract emails
            emails = self.extract_user_emails(user_data)
            result['emails'] = emails
            
            # Determine if user qualifies for email update
            has_email = len(emails) > 0
            result['qualifies_for_update'] = is_expired_enough and has_email
            
            if result['qualifies_for_update']:
                self.logger.info(f"User {user_id} qualifies: expired {years_expired} years, has {len(emails)} emails")
            else:
                if not is_expired_enough:
                    self.logger.debug(f"User {user_id} not expired enough: {years_expired} years")
                if not has_email:
                    self.logger.debug(f"User {user_id} has no email addresses")
            
        except AlmaAPIError as e:
            result['error'] = f"API error: {e}"
            self.logger.error(f"Error processing user {user_id}: {e}")
        except Exception as e:
            result['error'] = f"Processing error: {e}"
            self.logger.error(f"Unexpected error processing user {user_id}: {e}")
        
        return result
    
    def process_users_batch(self, user_ids: List[str], years_threshold: int = 2, 
                           max_workers: int = 5) -> List[Dict[str, Any]]:
        """
        Process multiple users for expiry qualification in batch.
        
        Args:
            user_ids: List of user IDs to process
            years_threshold: Minimum years expired to qualify
            max_workers: NOTE — currently a no-op. Concurrency is planned for a
                future release; passing this argument has no effect today. The
                function processes users sequentially.

        Returns:
            List of processing results for each user
        """
        if not user_ids:
            return []
        
        results = []
        total_users = len(user_ids)
        
        self.logger.info(f"Processing {total_users} users for expiry qualification")
        
        for i, user_id in enumerate(user_ids, 1):
            # Progress reporting
            if i % 10 == 0 or i == total_users:
                self.logger.info(f"Processing user {i}/{total_users}: {user_id}")
            
            result = self.process_user_for_expiry(user_id, years_threshold)
            results.append(result)
            
            # Basic rate limiting - pause every 50 requests
            if i % 50 == 0:
                time.sleep(1)
        
        # Summary statistics
        successful = sum(1 for r in results if r['success'])
        qualified = sum(1 for r in results if r['qualifies_for_update'])
        
        self.logger.info(f"Batch processing complete: {successful}/{total_users} successful, {qualified} qualified for update")
        
        return results
    
    def bulk_update_emails(self, email_updates: List[Dict[str, str]], 
                          dry_run: bool = True) -> List[Dict[str, Any]]:
        """
        Update multiple users' emails in bulk.
        
        Args:
            email_updates: List of dicts with 'user_id' and 'new_email' keys
            dry_run: If True, don't actually update emails (default: True for safety)
        
        Returns:
            List of update results
        """
        if not email_updates:
            return []
        
        results = []
        total_updates = len(email_updates)
        
        mode = "DRY RUN" if dry_run else "LIVE UPDATE"
        self.logger.info(f"Starting bulk email update ({mode}) for {total_updates} users")
        
        for i, update in enumerate(email_updates, 1):
            user_id = update.get('user_id', '')
            new_email = update.get('new_email', '')
            email_type = update.get('email_type', 'personal')
            
            result = {
                'user_id': user_id,
                'new_email': new_email,
                'success': False,
                'error': None,
                'dry_run': dry_run
            }
            
            # Progress reporting
            if i % 5 == 0 or i == total_updates:
                self.logger.info(f"Processing email update {i}/{total_updates}: {user_id}")
            
            try:
                if dry_run:
                    # Validate inputs without updating
                    if not user_id or not new_email:
                        raise AlmaValidationError("Missing user_id or new_email")
                    if not self.validate_email(new_email):
                        raise AlmaValidationError(f"Invalid email format: {new_email}")
                    
                    # Try to get user to verify they exist
                    self.get_user(user_id)
                    
                    result['success'] = True
                    self.logger.debug(f"DRY RUN: Would update {user_id} email to {new_email}")
                else:
                    # Actually update the email
                    self.update_user_email(user_id, new_email, email_type)
                    result['success'] = True
                    self.logger.info(f"Updated {user_id} email to {new_email}")
                
            except (AlmaAPIError, AlmaValidationError) as e:
                result['error'] = str(e)
                self.logger.error(f"Error updating email for {user_id}: {e}")
            except Exception as e:
                result['error'] = f"Unexpected error: {e}"
                self.logger.error(f"Unexpected error updating email for {user_id}: {e}")
            
            results.append(result)
            
            # Rate limiting for bulk operations
            if i % 25 == 0:
                time.sleep(2)
        
        # Summary statistics
        successful = sum(1 for r in results if r['success'])
        failed = total_updates - successful
        
        self.logger.info(f"Bulk email update complete ({mode}): {successful} successful, {failed} failed")
        
        return results
    
    # Utility Methods
    
    def get_environment(self) -> str:
        """Get current environment from client."""
        return self.client.get_environment()
    
    def test_connection(self) -> bool:
        """
        Test if the users endpoints are accessible.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try to get current user (which should always work with a valid API key)
            response = self.client.get("almaws/v1/users", params={"limit": "1"})
            success = response.status_code == 200
            
            if success:
                self.logger.info(f"✓ Users API connection successful ({self.environment})")
            else:
                self.logger.error(f"✗ Users API connection failed: {response.status_code}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"✗ Users API connection error: {e}")
            return False


# Usage examples for the email update workflow
if __name__ == "__main__":
    """
    Example usage of the enhanced Users class for email update workflow
    """
    
    def example_workflow():
        # Initialize client and users domain
        from almaapitk.client.AlmaAPIClient import AlmaAPIClient
        
        client = AlmaAPIClient('SANDBOX')
        users = Users(client)

        print(f"Logger name: {users.logger.name}")
        print(f"Logger level: {users.logger.level}")
        print(f"Logger handlers: {users.logger.handlers}")
        for handler in users.logger.handlers:
            print(f"  Handler: {type(handler).__name__}, Level: {handler.level}")
            if hasattr(handler, 'baseFilename'):
                print(f"    File: {handler.baseFilename}")
        
        # Test connection
        if not users.test_connection():
            print("Cannot proceed - users API connection failed")
            return
        
        # Example: Process single user for expiry
        print("=== Single User Processing ===")
        user_id = "123456789"
        result = users.process_user_for_expiry(user_id, years_threshold=2)
        
        if result['success']:
            print(f"User {user_id}: qualifies={result['qualifies_for_update']}, expired {result['years_expired']} years")
        else:
            print(f"Error processing user {user_id}: {result['error']}")
        
        # Example: Batch processing from set
        print("\n=== Batch User Processing ===")
        user_ids = ['222333444', '987654321', '333444555']  # Would come from admin.get_set_members()
        batch_results = users.process_users_batch(user_ids, years_threshold=2)
        
        qualified_users = [r for r in batch_results if r['qualifies_for_update']]
        print(f"Found {len(qualified_users)} users qualified for email update")
        
        # Example: Bulk email update (DRY RUN)
        if qualified_users:
            print("\n=== Email Update (DRY RUN) ===")
            email_updates = []
            for result in qualified_users:
                user_data = result['user_data']
                new_email = users.generate_new_email(user_data, "expired-{user_id}@institution.edu")
                email_updates.append({
                    'user_id': result['user_id'],
                    'new_email': new_email
                })
            
            update_results = users.bulk_update_emails(email_updates, dry_run=True)
            successful_updates = sum(1 for r in update_results if r['success'])
            print(f"DRY RUN: {successful_updates}/{len(email_updates)} email updates would succeed")
    
    # Uncomment to run example
    example_workflow()