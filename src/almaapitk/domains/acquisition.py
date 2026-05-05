"""
Acquisitions Domain Class for Alma API
Handles invoice management operations using the AlmaAPIClient foundation.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from almaapitk.client.AlmaAPIClient import AlmaAPIClient, AlmaAPIError, AlmaResponse
from almaapitk.domains.bibs import BibliographicRecords
from almaapitk.alma_logging import get_logger


class Acquisitions:
    """
    Domain class for handling Alma Acquisitions API operations.
    Currently focused on invoice management - will be expanded later.

    This class uses the AlmaAPIClient as its foundation for all HTTP operations.
    """

    def __init__(self, client: AlmaAPIClient):
        """
        Initialize the Acquisitions domain.

        Args:
            client: The AlmaAPIClient instance for making HTTP requests
        """
        self.client = client
        self.environment = client.get_environment()
        self.logger = get_logger('acquisitions', environment=self.environment)

    # =========================================================================
    # Core Utility Methods - Invoice Creation Helpers
    # =========================================================================

    def _format_invoice_date(self, date_input: Union[str, datetime]) -> str:
        """
        Format date to Alma API format (YYYY-MM-DDZ).

        Accepts multiple input formats:
        - "YYYY-MM-DD" -> converts to "YYYY-MM-DDZ"
        - "YYYY-MM-DDZ" -> returns as-is
        - datetime object -> converts to "YYYY-MM-DDZ"

        Args:
            date_input: Date as string or datetime object

        Returns:
            Formatted date string "YYYY-MM-DDZ"

        Raises:
            ValueError: If date format is invalid

        Examples:
            >>> acq._format_invoice_date("2025-10-21")
            "2025-10-21Z"

            >>> acq._format_invoice_date("2025-10-21Z")
            "2025-10-21Z"

            >>> from datetime import datetime
            >>> acq._format_invoice_date(datetime(2025, 10, 21))
            "2025-10-21Z"
        """
        if isinstance(date_input, datetime):
            # Convert datetime object to string
            return date_input.strftime("%Y-%m-%d") + "Z"

        if isinstance(date_input, str):
            # Already formatted with Z
            if date_input.endswith("Z"):
                # Validate format YYYY-MM-DDZ
                try:
                    datetime.strptime(date_input[:-1], "%Y-%m-%d")
                    return date_input
                except ValueError:
                    raise ValueError(f"Invalid date format: {date_input}. Expected YYYY-MM-DDZ")

            # Format without Z - add it
            try:
                datetime.strptime(date_input, "%Y-%m-%d")
                return date_input + "Z"
            except ValueError:
                raise ValueError(f"Invalid date format: {date_input}. Expected YYYY-MM-DD or YYYY-MM-DDZ")

        raise ValueError(f"Date must be string or datetime object, got {type(date_input)}")

    def _build_invoice_structure(
        self,
        number: str,
        invoice_date: str,
        vendor_code: str,
        total_amount: float,
        currency: str = "ILS",
        **optional_fields
    ) -> Dict[str, Any]:
        """
        Build complete invoice data structure for Alma API.

        Constructs the nested dictionary structure required by the Alma API,
        handling all required and optional fields.

        Args:
            number: Vendor invoice number (required)
            invoice_date: Invoice date - will be formatted automatically (required)
            vendor_code: Vendor code from Alma (required)
            total_amount: Total invoice amount (required)
            currency: Currency code (default: "ILS")
            **optional_fields: Additional optional fields:
                - invoice_due_date: str
                - vendor_account: str
                - reference_number: str
                - payment_method: str
                - notes: List[str]
                - payment: Dict (voucher info, etc.)
                - invoice_vat: Dict (VAT details)
                - additional_charges: Dict (shipment, overhead, etc.)

        Returns:
            Complete invoice data dict ready for API submission

        Raises:
            ValueError: If required fields are missing or invalid

        Example:
            >>> invoice_data = acq._build_invoice_structure(
            ...     number="INV-2025-001",
            ...     invoice_date="2025-10-21",
            ...     vendor_code="RIALTO",
            ...     total_amount=100.00,
            ...     currency="ILS",
            ...     reference_number="PO-12345",
            ...     payment={"voucher_number": "V-001"}
            ... )
        """
        # Validate required fields
        if not number:
            raise ValueError("Invoice number is required")
        if not vendor_code:
            raise ValueError("Vendor code is required")
        if total_amount is None or total_amount < 0:
            raise ValueError("Total amount must be a non-negative number")

        # Format date
        formatted_date = self._format_invoice_date(invoice_date)

        # Build core structure
        invoice_data = {
            "number": str(number),
            "invoice_date": formatted_date,
            "vendor": {"value": vendor_code},
            "total_amount": total_amount,  # Alma accepts simple decimal
            "currency": {"value": currency}
        }

        # Add optional fields if provided
        if "invoice_due_date" in optional_fields:
            invoice_data["invoice_due_date"] = self._format_invoice_date(
                optional_fields["invoice_due_date"]
            )

        if "vendor_account" in optional_fields:
            invoice_data["vendor_account"] = optional_fields["vendor_account"]

        if "reference_number" in optional_fields:
            invoice_data["reference_number"] = optional_fields["reference_number"]

        if "payment_method" in optional_fields:
            invoice_data["payment_method"] = optional_fields["payment_method"]

        if "notes" in optional_fields:
            invoice_data["notes"] = optional_fields["notes"]

        if "payment" in optional_fields:
            invoice_data["payment"] = optional_fields["payment"]

        if "invoice_vat" in optional_fields:
            invoice_data["invoice_vat"] = optional_fields["invoice_vat"]

        if "additional_charges" in optional_fields:
            invoice_data["additional_charges"] = optional_fields["additional_charges"]

        return invoice_data

    def _build_invoice_line_structure(
        self,
        po_line: str,
        amount: float,
        quantity: int,
        fund_code: str,
        currency: str = "ILS",
        **optional_fields
    ) -> Dict[str, Any]:
        """
        Build complete invoice line data structure for Alma API.

        Constructs the nested dictionary structure required for invoice lines,
        including fund distribution array.

        Args:
            po_line: POL number (e.g., "POL-12349")
            amount: Line amount
            quantity: Line quantity
            fund_code: Fund code for distribution
            currency: Currency code (default: "ILS")
            **optional_fields: Additional optional fields:
                - invoice_line_type: str (default: "REGULAR")
                - note: str
                - subscription_from_date: str
                - subscription_to_date: str
                - vat: Dict

        Returns:
            Complete invoice line data dict ready for API submission

        Raises:
            ValueError: If required fields are missing or invalid

        Example:
            >>> line_data = acq._build_invoice_line_structure(
            ...     po_line="POL-12349",
            ...     amount=100.00,
            ...     quantity=1,
            ...     fund_code="LIBRARY_FUND",
            ...     currency="ILS",
            ...     note="Test invoice line"
            ... )
        """
        # Validate required fields
        if not po_line:
            raise ValueError("POL number is required")
        if amount is None or amount < 0:
            raise ValueError("Amount must be a non-negative number")
        if quantity is None or quantity < 1:
            raise ValueError("Quantity must be at least 1")
        if not fund_code:
            raise ValueError("Fund code is required")

        # Build core structure with fund distribution
        # NOTE: Alma API requires EITHER 'amount' OR 'percent' in fund_distribution, not both
        # Using percent=100 means the entire line amount goes to this fund
        line_data = {
            "po_line": po_line,
            "price": amount,  # API expects numeric value
            "quantity": quantity,
            "invoice_line_type": {"value": optional_fields.get("invoice_line_type", "REGULAR")},
            "fund_distribution": [
                {
                    "fund_code": {"value": fund_code},
                    "percent": 100  # 100% of line amount goes to this fund
                }
            ]
        }

        # Add optional fields if provided
        if "note" in optional_fields:
            line_data["note"] = optional_fields["note"]

        if "subscription_from_date" in optional_fields:
            line_data["subscription_from_date"] = self._format_invoice_date(
                optional_fields["subscription_from_date"]
            )

        if "subscription_to_date" in optional_fields:
            line_data["subscription_to_date"] = self._format_invoice_date(
                optional_fields["subscription_to_date"]
            )

        if "vat" in optional_fields:
            line_data["vat"] = optional_fields["vat"]

        return line_data

    # =========================================================================
    # End of Core Utility Methods
    # =========================================================================

    # =========================================================================
    # Simple Helper Methods - High-Level Invoice Creation
    # =========================================================================

    def create_invoice_simple(
        self,
        invoice_number: str,
        invoice_date: str,
        vendor_code: str,
        total_amount: float,
        currency: str = "ILS",
        **optional_fields
    ) -> Dict[str, Any]:
        """
        Create an invoice with simplified parameters.

        This is a high-level helper that automatically formats the invoice data
        structure and handles date formatting. It wraps the low-level create_invoice()
        method with user-friendly parameters.

        Args:
            invoice_number: Vendor invoice number (required)
            invoice_date: Invoice date - accepts "YYYY-MM-DD" or "YYYY-MM-DDZ" or datetime (required)
            vendor_code: Vendor code from Alma (required)
            total_amount: Total invoice amount (required)
            currency: Currency code (default: "ILS")
            **optional_fields: Additional optional fields:
                - invoice_due_date: str or datetime
                - vendor_account: str
                - reference_number: str
                - payment_method: str
                - notes: List[str]
                - payment: Dict (voucher info, etc.)
                - invoice_vat: Dict (VAT details)
                - additional_charges: Dict (shipment, overhead, etc.)

        Returns:
            Created invoice dict with invoice_id and all invoice data

        Raises:
            ValueError: If required fields are missing or invalid
            AlmaAPIError: If API request fails

        Example - Simple invoice:
            >>> invoice = acq.create_invoice_simple(
            ...     invoice_number="INV-2025-001",
            ...     invoice_date="2025-10-21",
            ...     vendor_code="RIALTO",
            ...     total_amount=100.00,
            ...     currency="ILS"
            ... )
            >>> print(f"Created invoice: {invoice['id']}")

        Example - Invoice with optional fields:
            >>> invoice = acq.create_invoice_simple(
            ...     invoice_number="INV-2025-002",
            ...     invoice_date="2025-10-21",
            ...     vendor_code="RIALTO",
            ...     total_amount=250.00,
            ...     currency="ILS",
            ...     reference_number="PO-12345",
            ...     payment={"voucher_number": "V-001"},
            ...     notes=["Payment for books", "Rush order"]
            ... )

        Example - With datetime object:
            >>> from datetime import datetime
            >>> invoice = acq.create_invoice_simple(
            ...     invoice_number="INV-2025-003",
            ...     invoice_date=datetime.now(),
            ...     vendor_code="VENDOR_CODE",
            ...     total_amount=500.00
            ... )
        """
        # Log operation start
        self.logger.info(
            f"Creating invoice (simple): {invoice_number}",
            invoice_number=invoice_number,
            vendor_code=vendor_code,
            total_amount=total_amount,
            currency=currency,
            invoice_date=invoice_date,
            optional_fields=list(optional_fields.keys()) if optional_fields else []
        )

        try:
            # Build invoice structure using core utility
            invoice_data = self._build_invoice_structure(
                number=invoice_number,
                invoice_date=invoice_date,
                vendor_code=vendor_code,
                total_amount=total_amount,
                currency=currency,
                **optional_fields
            )

            self.logger.debug(
                "Invoice structure built",
                invoice_number=invoice_number,
                structure_keys=list(invoice_data.keys())
            )

            # Create invoice via low-level method
            self.logger.info(f"Creating invoice {invoice_number} for vendor {vendor_code}: {total_amount} {currency}")
            created_invoice = self.create_invoice(invoice_data)

            invoice_id = created_invoice.get('id')
            if invoice_id:
                self.logger.info(f"✓ Invoice created successfully: {invoice_id}")
                self.logger.info(
                    f"Invoice created successfully: {invoice_id}",
                    invoice_id=invoice_id,
                    invoice_number=invoice_number,
                    vendor_code=vendor_code,
                    total_amount=total_amount
                )
            else:
                self.logger.warning(f"⚠️ Invoice created but no ID returned")
                self.logger.warning(
                    "Invoice created but no ID in response",
                    invoice_number=invoice_number
                )

            return created_invoice

        except ValueError as e:
            # Log validation error
            self.logger.error(
                f"Invoice validation failed: {invoice_number}",
                invoice_number=invoice_number,
                error_type="ValidationError",
                error_message=str(e)
            )
            raise ValueError(f"Invalid invoice parameters: {str(e)}")
        except AlmaAPIError as e:
            # Log API error
            self.logger.error(
                f"Invoice creation API error: {invoice_number}",
                invoice_number=invoice_number,
                vendor_code=vendor_code,
                error_type="AlmaAPIError",
                error_message=str(e)
            )
            raise AlmaAPIError(f"Failed to create invoice {invoice_number}: {str(e)}")

    def create_invoice_line_simple(
        self,
        invoice_id: str,
        pol_id: str,
        amount: float,
        quantity: int = 1,
        fund_code: Optional[str] = None,
        currency: str = "ILS",
        **optional_fields
    ) -> Dict[str, Any]:
        """
        Create an invoice line with simplified parameters.

        This is a high-level helper that automatically handles fund distribution
        structure and other complexities. If fund_code is not provided, it will
        attempt to extract it from the POL.

        Args:
            invoice_id: Invoice ID (required)
            pol_id: POL number e.g., "POL-12349" (required)
            amount: Line amount (required)
            quantity: Line quantity (default: 1)
            fund_code: Fund code for distribution (optional - will try to get from POL if not provided)
            currency: Currency code (default: "ILS")
            **optional_fields: Additional optional fields:
                - invoice_line_type: str (default: "REGULAR")
                - note: str
                - subscription_from_date: str or datetime
                - subscription_to_date: str or datetime
                - vat: Dict

        Returns:
            Created invoice line dict

        Raises:
            ValueError: If required fields are missing or invalid
            AlmaAPIError: If API request fails

        Example - Simple line:
            >>> line = acq.create_invoice_line_simple(
            ...     invoice_id="123456789",
            ...     pol_id="POL-12349",
            ...     amount=100.00,
            ...     fund_code="LIBRARY_FUND"
            ... )

        Example - Line with multiple quantities:
            >>> line = acq.create_invoice_line_simple(
            ...     invoice_id="123456789",
            ...     pol_id="POL-12350",
            ...     amount=50.00,
            ...     quantity=2,
            ...     fund_code="BOOK_FUND",
            ...     note="Textbooks for course"
            ... )

        Example - Auto-detect fund from POL:
            >>> line = acq.create_invoice_line_simple(
            ...     invoice_id="123456789",
            ...     pol_id="POL-12351",
            ...     amount=75.00
            ...     # fund_code will be extracted from POL
            ... )

        Example - Subscription line:
            >>> line = acq.create_invoice_line_simple(
            ...     invoice_id="123456789",
            ...     pol_id="POL-12352",
            ...     amount=200.00,
            ...     fund_code="JOURNAL_FUND",
            ...     subscription_from_date="2025-01-01",
            ...     subscription_to_date="2025-12-31"
            ... )
        """
        # Log operation start
        self.logger.info(
            f"Creating invoice line (simple): {pol_id}",
            invoice_id=invoice_id,
            pol_id=pol_id,
            amount=amount,
            quantity=quantity,
            fund_code=fund_code if fund_code else "auto-detect",
            currency=currency,
            optional_fields=list(optional_fields.keys()) if optional_fields else []
        )

        try:
            # If fund_code not provided, try to get from POL
            if not fund_code:
                self.logger.info(f"No fund code provided - attempting to extract from POL {pol_id}")
                self.logger.debug(
                    f"Extracting fund code from POL: {pol_id}",
                    pol_id=pol_id
                )
                fund_code = self.get_fund_from_pol(pol_id)

                if fund_code:
                    self.logger.info(f"✓ Found fund code in POL: {fund_code}")
                    self.logger.info(
                        f"Fund code extracted from POL: {fund_code}",
                        pol_id=pol_id,
                        fund_code=fund_code
                    )
                else:
                    self.logger.error(
                        f"Fund code extraction failed: {pol_id}",
                        pol_id=pol_id,
                        error_type="FundCodeMissing"
                    )
                    raise ValueError(
                        f"Fund code is required but not provided and could not be extracted from POL {pol_id}. "
                        "Please provide fund_code parameter explicitly."
                    )

            # Build invoice line structure using core utility
            line_data = self._build_invoice_line_structure(
                po_line=pol_id,
                amount=amount,
                quantity=quantity,
                fund_code=fund_code,
                currency=currency,
                **optional_fields
            )

            self.logger.debug(
                "Invoice line structure built",
                pol_id=pol_id,
                invoice_id=invoice_id,
                structure_keys=list(line_data.keys())
            )

            # Create invoice line via low-level method
            self.logger.info(f"Creating invoice line for POL {pol_id}: {quantity} x {amount} {currency} (Fund: {fund_code})")
            created_line = self.create_invoice_line(invoice_id, line_data)

            self.logger.info(f"✓ Invoice line created successfully")
            self.logger.info(
                f"Invoice line created successfully",
                invoice_id=invoice_id,
                pol_id=pol_id,
                amount=amount,
                quantity=quantity,
                fund_code=fund_code
            )
            return created_line

        except ValueError as e:
            # Log validation error
            self.logger.error(
                f"Invoice line validation failed: {pol_id}",
                invoice_id=invoice_id,
                pol_id=pol_id,
                error_type="ValidationError",
                error_message=str(e)
            )
            raise ValueError(f"Invalid invoice line parameters: {str(e)}")
        except AlmaAPIError as e:
            # Log API error
            self.logger.error(
                f"Invoice line creation API error: {pol_id}",
                invoice_id=invoice_id,
                pol_id=pol_id,
                error_type="AlmaAPIError",
                error_message=str(e)
            )
            raise AlmaAPIError(f"Failed to create invoice line for POL {pol_id}: {str(e)}")

    # =========================================================================
    # End of Simple Helper Methods
    # =========================================================================

    # =========================================================================
    # Phase 4: Complete Workflow Helper
    # =========================================================================

    def create_invoice_with_lines(
        self,
        invoice_number: str,
        invoice_date: str,
        vendor_code: str,
        lines: List[Dict[str, Any]],
        currency: str = "ILS",
        auto_process: bool = True,
        auto_pay: bool = False,
        check_duplicates: bool = False,
        **invoice_kwargs
    ) -> Dict[str, Any]:
        """
        Create a complete invoice with lines in a single workflow.

        This method automates the entire invoice creation process:
        1. Calculates total amount from lines
        2. Creates the invoice
        3. Adds all invoice lines
        4. Optionally processes (approves) the invoice
        5. Optionally marks the invoice as paid

        Args:
            invoice_number: Vendor invoice number (required)
            invoice_date: Invoice date as "YYYY-MM-DD" or datetime object (required)
            vendor_code: Vendor code from Alma (required)
            lines: List of line items, each containing:
                - pol_id: POL ID (required)
                - amount: Line amount (required)
                - quantity: Item quantity (default: 1)
                - fund_code: Fund code (optional, auto-extracted from POL if missing)
                - Additional optional fields: note, subscription_from_date, etc.
            currency: Currency code (default: "ILS")
            auto_process: Automatically approve/process the invoice (default: True)
            auto_pay: Automatically mark invoice as paid (default: False)
            check_duplicates: Check if POLs are already invoiced before creating lines (default: False)
                             Warning: This performs additional API calls and may be slow
            **invoice_kwargs: Additional invoice fields (payment, invoice_vat, etc.)

        Returns:
            Dict containing:
                - invoice_id: Created invoice ID
                - invoice_number: Invoice number
                - line_ids: List of created line IDs
                - total_amount: Calculated total
                - status: Final invoice status
                - processed: Whether invoice was processed
                - paid: Whether invoice was paid
                - errors: List of any errors encountered (empty if all successful)

        Raises:
            ValueError: If required parameters are missing or invalid
            AlmaAPIError: If any API operation fails

        Example - Simple invoice with lines:
            >>> lines = [
            ...     {"pol_id": "POL-12347", "amount": 50.00, "quantity": 1},
            ...     {"pol_id": "POL-12348", "amount": 75.00, "quantity": 2}
            ... ]
            >>> result = acq.create_invoice_with_lines(
            ...     invoice_number="INV-2025-001",
            ...     invoice_date="2025-10-22",
            ...     vendor_code="RIALTO",
            ...     lines=lines
            ... )
            >>> print(f"Invoice ID: {result['invoice_id']}")
            >>> print(f"Lines created: {len(result['line_ids'])}")

        Example - Complete workflow with auto-pay:
            >>> lines = [{"pol_id": "POL-12349", "amount": 100.00}]
            >>> result = acq.create_invoice_with_lines(
            ...     invoice_number="INV-2025-002",
            ...     invoice_date="2025-10-22",
            ...     vendor_code="RIALTO",
            ...     lines=lines,
            ...     auto_process=True,
            ...     auto_pay=True
            ... )
            >>> # Invoice is now created, processed, and paid

        Example - With explicit fund codes:
            >>> lines = [
                {"pol_id": "POL-12350", "amount": 45.00, "fund_code": "SCIENCE"},
                {"pol_id": "POL-12351", "amount": 55.00, "fund_code": "HISTORY"}
            ... ]
            >>> result = acq.create_invoice_with_lines(
            ...     invoice_number="INV-2025-003",
            ...     invoice_date="2025-10-22",
            ...     vendor_code="RIALTO",
            ...     lines=lines,
            ...     currency="USD"
            ... )

        Example - Dry run (process but don't pay):
            >>> lines = [{"pol_id": "POL-12352", "amount": 200.00}]
            >>> result = acq.create_invoice_with_lines(
            ...     invoice_number="INV-2025-004",
            ...     invoice_date="2025-10-22",
            ...     vendor_code="RIALTO",
            ...     lines=lines,
            ...     auto_process=True,
            ...     auto_pay=False  # Leave for manual payment
            ... )

        Note:
            - If a line creation fails, subsequent lines will still be attempted
            - All errors are captured in the 'errors' list in the result
            - The invoice is created even if some lines fail
            - Processing and payment only occur if all previous steps succeed
            - Once an invoice is created, it cannot be deleted via API
              (only canceled/rejected in Alma UI if needed)
        """
        # Log workflow start
        self.logger.info(
            f"Starting complete invoice workflow: {invoice_number}",
            invoice_number=invoice_number,
            vendor_code=vendor_code,
            num_lines=len(lines) if isinstance(lines, list) else 0,
            currency=currency,
            auto_process=auto_process,
            auto_pay=auto_pay,
            check_duplicates=check_duplicates
        )

        # Validate required parameters
        if not invoice_number:
            self.logger.error("Validation failed: Invoice number is required")
            raise ValueError("Invoice number is required")
        if not invoice_date:
            self.logger.error("Validation failed: Invoice date is required")
            raise ValueError("Invoice date is required")
        if not vendor_code:
            self.logger.error("Validation failed: Vendor code is required")
            raise ValueError("Vendor code is required")
        if not lines or not isinstance(lines, list) or len(lines) == 0:
            self.logger.error("Validation failed: At least one line item is required")
            raise ValueError("At least one line item is required")

        # Validate each line has required fields
        for idx, line in enumerate(lines):
            if not isinstance(line, dict):
                self.logger.error(f"Validation failed: Line {idx + 1} is not a dictionary")
                raise ValueError(f"Line {idx + 1}: Must be a dictionary")
            if 'pol_id' not in line:
                self.logger.error(f"Validation failed: Line {idx + 1} missing pol_id")
                raise ValueError(f"Line {idx + 1}: Missing required field 'pol_id'")
            if 'amount' not in line:
                self.logger.error(f"Validation failed: Line {idx + 1} missing amount")
                raise ValueError(f"Line {idx + 1}: Missing required field 'amount'")

        self.logger.debug(
            "Workflow validation passed",
            invoice_number=invoice_number,
            lines_validated=len(lines)
        )

        # Initialize result tracking
        result = {
            'invoice_id': None,
            'invoice_number': invoice_number,
            'line_ids': [],
            'total_amount': 0.0,
            'status': None,
            'processed': False,
            'paid': False,
            'errors': []
        }

        try:
            # Step 1: Calculate total amount from lines
            self.logger.info("=" * 70)
            self.logger.info("STEP 1: Calculate total amount from lines")
            self.logger.info("-" * 70)

            self.logger.info(
                "Workflow Step 1: Calculating total amount",
                invoice_number=invoice_number,
                num_lines=len(lines)
            )

            total_amount = sum(line['amount'] for line in lines)
            result['total_amount'] = total_amount

            self.logger.info(f"Lines: {len(lines)}")
            self.logger.info(f"Total amount: {total_amount} {currency}")

            self.logger.info(
                "Total amount calculated",
                invoice_number=invoice_number,
                total_amount=total_amount,
                currency=currency,
                num_lines=len(lines)
            )

            # Step 2: Create invoice
            self.logger.info("\n" + "=" * 70)
            self.logger.info("STEP 2: Create invoice")
            self.logger.info("-" * 70)

            self.logger.info(
                "Workflow Step 2: Creating invoice",
                invoice_number=invoice_number,
                vendor_code=vendor_code,
                total_amount=total_amount
            )

            created_invoice = self.create_invoice_simple(
                invoice_number=invoice_number,
                invoice_date=invoice_date,
                vendor_code=vendor_code,
                total_amount=total_amount,
                currency=currency,
                **invoice_kwargs
            )

            invoice_id = created_invoice.get('id')
            if not invoice_id:
                self.logger.error(
                    "Invoice created but no ID returned",
                    invoice_number=invoice_number
                )
                raise AlmaAPIError("Invoice created but no ID returned")

            result['invoice_id'] = invoice_id
            self.logger.info(f"✓ Invoice created: {invoice_id}")

            self.logger.info(
                "Invoice created in workflow",
                invoice_id=invoice_id,
                invoice_number=invoice_number
            )

            # Step 3: Add all lines
            self.logger.info("\n" + "=" * 70)
            self.logger.info(f"STEP 3: Add {len(lines)} invoice line(s)")
            self.logger.info("-" * 70)

            self.logger.info(
                f"Workflow Step 3: Adding {len(lines)} invoice lines",
                invoice_id=invoice_id,
                invoice_number=invoice_number,
                num_lines=len(lines),
                pol_ids=[line.get('pol_id') for line in lines]
            )

            # Optional: Check for duplicate invoicing
            if check_duplicates:
                self.logger.info("\n⚠️  Duplicate check enabled - validating POLs...")
                duplicates_found = []
                for line in lines:
                    pol_id = line['pol_id']
                    try:
                        check = self.check_pol_invoiced(pol_id)
                        if check['is_invoiced']:
                            duplicates_found.append({
                                'pol_id': pol_id,
                                'existing_invoices': check['invoices']
                            })
                    except Exception as e:
                        self.logger.exception(f"  ⚠️  Could not check {pol_id}: {e}")

                if duplicates_found:
                    error_msg = f"Duplicate invoicing detected for {len(duplicates_found)} POL(s)"
                    self.logger.error(f"\n✗ {error_msg}:")
                    for dup in duplicates_found:
                        self.logger.debug(f"  - {dup['pol_id']}: already has {len(dup['existing_invoices'])} invoice(s)")
                    raise ValueError(error_msg)
                else:
                    self.logger.debug("  ✓ No duplicates found - safe to proceed")

            for idx, line in enumerate(lines, 1):
                try:
                    pol_id = line['pol_id']
                    amount = line['amount']
                    quantity = line.get('quantity', 1)
                    fund_code = line.get('fund_code')

                    # Extract optional line fields
                    line_kwargs = {k: v for k, v in line.items()
                                   if k not in ['pol_id', 'amount', 'quantity', 'fund_code']}

                    self.logger.info(f"\nLine {idx}/{len(lines)}: POL {pol_id}, Amount: {amount}")

                    created_line = self.create_invoice_line_simple(
                        invoice_id=invoice_id,
                        pol_id=pol_id,
                        amount=amount,
                        quantity=quantity,
                        fund_code=fund_code,
                        currency=currency,
                        **line_kwargs
                    )

                    line_id = created_line.get('id')
                    if line_id:
                        result['line_ids'].append(line_id)

                except Exception as e:
                    error_msg = f"Line {idx} (POL {pol_id}): {str(e)}"
                    result['errors'].append(error_msg)
                    self.logger.exception(f"✗ {error_msg}")
                    # Continue with remaining lines

            # Check if all lines succeeded
            if len(result['line_ids']) == 0:
                self.logger.error(
                    "All invoice lines failed",
                    invoice_id=invoice_id,
                    invoice_number=invoice_number,
                    num_lines=len(lines)
                )
                raise AlmaAPIError("All invoice lines failed to create")

            if len(result['line_ids']) < len(lines):
                failed_count = len(lines) - len(result['line_ids'])
                self.logger.error(f"\n⚠️ Warning: {failed_count} line(s) failed")
                self.logger.warning(
                    f"{failed_count} invoice lines failed",
                    invoice_id=invoice_id,
                    invoice_number=invoice_number,
                    succeeded=len(result['line_ids']),
                    failed=failed_count,
                    total=len(lines)
                )
            else:
                self.logger.info(f"\n✓ All {len(lines)} line(s) created successfully")
                self.logger.info(
                    "All invoice lines created successfully",
                    invoice_id=invoice_id,
                    invoice_number=invoice_number,
                    num_lines=len(lines)
                )

            # Step 4: Process invoice (if requested)
            if auto_process:
                self.logger.info("\n" + "=" * 70)
                self.logger.info("STEP 4: Process (approve) invoice")
                self.logger.info("-" * 70)

                self.logger.info(
                    "Workflow Step 4: Processing invoice",
                    invoice_id=invoice_id,
                    invoice_number=invoice_number
                )

                try:
                    processed_invoice = self.approve_invoice(invoice_id)
                    result['processed'] = True
                    result['status'] = processed_invoice.get('invoice_status', {}).get('value')
                    self.logger.info(f"✓ Invoice processed")

                    self.logger.info(
                        "Invoice processed successfully",
                        invoice_id=invoice_id,
                        invoice_number=invoice_number,
                        status=result['status']
                    )

                except Exception as e:
                    error_msg = f"Failed to process invoice: {str(e)}"
                    result['errors'].append(error_msg)
                    self.logger.exception(f"✗ {error_msg}")
                    self.logger.error(
                        "Failed to process invoice",
                        invoice_id=invoice_id,
                        invoice_number=invoice_number,
                        error_message=str(e)
                    )

            # Step 5: Pay invoice (if requested and processed)
            if auto_pay:
                if not auto_process or not result['processed']:
                    error_msg = "Cannot pay invoice: must be processed first"
                    result['errors'].append(error_msg)
                    self.logger.error(f"\n✗ {error_msg}")
                    self.logger.warning(
                        "Cannot pay invoice: not processed",
                        invoice_id=invoice_id,
                        invoice_number=invoice_number,
                        auto_process=auto_process,
                        processed=result['processed']
                    )
                else:
                    self.logger.info("\n" + "=" * 70)
                    self.logger.info("STEP 5: Mark invoice as paid")
                    self.logger.info("-" * 70)

                    self.logger.info(
                        "Workflow Step 5: Marking invoice as paid",
                        invoice_id=invoice_id,
                        invoice_number=invoice_number
                    )

                    try:
                        paid_invoice = self.mark_invoice_paid(invoice_id)
                        result['paid'] = True
                        result['status'] = paid_invoice.get('invoice_status', {}).get('value')
                        self.logger.info(f"✓ Invoice marked as paid")

                        self.logger.info(
                            "Invoice marked as paid successfully",
                            invoice_id=invoice_id,
                            invoice_number=invoice_number,
                            status=result['status']
                        )

                    except Exception as e:
                        error_msg = f"Failed to mark invoice as paid: {str(e)}"
                        result['errors'].append(error_msg)
                        self.logger.exception(f"✗ {error_msg}")
                        self.logger.error(
                            "Failed to mark invoice as paid",
                            invoice_id=invoice_id,
                            invoice_number=invoice_number,
                            error_message=str(e)
                        )

            # Final summary
            self.logger.info("\n" + "=" * 70)
            self.logger.info("WORKFLOW SUMMARY")
            self.logger.info("=" * 70)
            self.logger.info(f"Invoice ID: {result['invoice_id']}")
            self.logger.info(f"Invoice Number: {result['invoice_number']}")
            self.logger.info(f"Total Amount: {result['total_amount']} {currency}")
            self.logger.info(f"Lines Created: {len(result['line_ids'])}/{len(lines)}")
            self.logger.info(f"Processed: {'Yes' if result['processed'] else 'No'}")
            self.logger.info(f"Paid: {'Yes' if result['paid'] else 'No'}")
            self.logger.info(f"Status: {result['status'] or 'Unknown'}")

            if result['errors']:
                self.logger.error(f"\nErrors encountered: {len(result['errors'])}")
                for error in result['errors']:
                    self.logger.error(f"  - {error}")
                self.logger.warning(
                    f"Workflow completed with {len(result['errors'])} errors",
                    invoice_id=result['invoice_id'],
                    invoice_number=invoice_number,
                    error_count=len(result['errors']),
                    errors=result['errors']
                )
            else:
                self.logger.info("\n✓ Workflow completed successfully with no errors")
                self.logger.info(
                    "Workflow completed successfully",
                    invoice_id=result['invoice_id'],
                    invoice_number=invoice_number,
                    total_amount=result['total_amount'],
                    lines_created=len(result['line_ids']),
                    processed=result['processed'],
                    paid=result['paid'],
                    status=result['status']
                )

            return result

        except ValueError as e:
            # Validation errors
            self.logger.error(
                "Workflow validation error",
                invoice_number=invoice_number,
                error_type="ValueError",
                error_message=str(e)
            )
            raise ValueError(f"Invalid workflow parameters: {str(e)}")

        except AlmaAPIError as e:
            # API errors - add to result and re-raise
            result['errors'].append(str(e))
            self.logger.error(
                "Workflow API error",
                invoice_number=invoice_number,
                invoice_id=result.get('invoice_id'),
                error_type="AlmaAPIError",
                error_message=str(e),
                workflow_result=result
            )
            raise AlmaAPIError(f"Invoice workflow failed: {str(e)}")

    # =========================================================================
    # End of Complete Workflow Helper
    # =========================================================================

    def get_invoice(self, invoice_id: str, view: str = "full") -> Dict[str, Any]:
        """
        Retrieve an invoice by ID.
        
        Args:
            invoice_id: The invoice ID to retrieve
            view: Level of detail (brief, full)
        
        Returns:
            Dict containing the invoice data
            
        Raises:
            ValueError: If invoice_id is empty or None
            requests.RequestException: If the API request fails
        """
        if not invoice_id:
            raise ValueError("Invoice ID is required")
        
        self.logger.info(f"Retrieving invoice: {invoice_id} from {self.environment}")
        
        params = {"view": view} if view != "full" else None
        
        try:
            endpoint = f"almaws/v1/acq/invoices/{invoice_id}"
            response = self.client.get(endpoint, params=params)
            
            # Raise for HTTP errors
            if not response.success:
                raise Exception(f"API request failed with status {response.status_code}")
            
            # Parse JSON response
            invoice_data = response.json()
            
            self.logger.info(f"✓ Successfully retrieved invoice {invoice_id}")
            return invoice_data
            
        except Exception as e:
            self.logger.exception(f"✗ Failed to retrieve invoice {invoice_id}: {str(e)}")
            raise
    
    def process_invoice_service(self, invoice_id: str, operation: str) -> Dict[str, Any]:
        """
        Process an invoice service operation using the Invoice Service API.
        
        According to Alma API documentation, this endpoint expects:
        - Operation specified in query parameter 'op'
        - Empty object {} as the request body
        
        Args:
            invoice_id: The invoice ID to process
            operation: The operation to perform ('paid', 'process_invoice', 'mark_in_erp', 'rejected')
        
        Returns:
            Dict containing the operation result
            
        Raises:
            ValueError: If invoice_id or operation is empty/None
            requests.RequestException: If the API request fails
        """
        if not invoice_id:
            raise ValueError("Invoice ID is required")
        
        if not operation:
            raise ValueError("Operation is required")
        
        # Validate operation
        valid_operations = ['paid', 'process_invoice', 'mark_in_erp', 'rejected']
        if operation not in valid_operations:
            self.logger.warning(f"⚠️  Warning: '{operation}' is not in known operations: {valid_operations}")
        
        self.logger.debug(f"Processing invoice service: {invoice_id}, operation: {operation}")
        
        try:
            endpoint = f"almaws/v1/acq/invoices/{invoice_id}"
            params = {"op": operation}
            
            # Send empty object as payload according to API documentation
            empty_payload = {}
            
            response = self.client.post(endpoint, data=empty_payload, params=params)
            
            # Raise for HTTP errors
            if not response.success:
                raise Exception(f"API request failed with status {response.status_code}")
            
            # Parse JSON response
            result_data = response.json()
            
            self.logger.info(f"✓ Successfully processed invoice service {operation} for invoice {invoice_id}")
            return result_data
            
        except Exception as e:
            self.logger.exception(f"✗ Failed to process invoice service {operation} for invoice {invoice_id}: {str(e)}")
            raise
    
    def check_invoice_payment_status(self, invoice_id: str) -> Dict[str, Any]:
        """
        Check if an invoice has already been paid (duplicate payment protection).

        This method retrieves the invoice and checks its payment status to prevent
        accidentally paying the same invoice twice.

        Args:
            invoice_id: The invoice ID to check

        Returns:
            Dict with:
                - is_paid: bool - Whether invoice is already paid
                - payment_status: str - Current payment status (PAID, NOT_PAID, etc.)
                - invoice_status: str - Current invoice status (ACTIVE, CLOSED, etc.)
                - approval_status: str - Current approval status
                - can_pay: bool - Whether it's safe to mark as paid
                - warnings: List[str] - Any warnings about payment

        Example:
            >>> check = acq.check_invoice_payment_status("123456")
            >>> if check['is_paid']:
            ...     print(f"⚠️ Invoice already paid! Status: {check['payment_status']}")
            >>> elif check['can_pay']:
            ...     acq.mark_invoice_paid("123456")
        """
        try:
            invoice = self.get_invoice(invoice_id)

            payment_info = invoice.get('payment', {})
            payment_status = payment_info.get('payment_status', {}).get('value', 'UNKNOWN')
            invoice_status = invoice.get('invoice_status', {}).get('value', 'UNKNOWN')
            approval_status = invoice.get('invoice_approval_status', {}).get('value', 'UNKNOWN')

            is_paid = payment_status in ['PAID', 'FULLY_PAID', 'PARTIALLY_PAID']
            is_closed = invoice_status == 'CLOSED'
            # Allow both APPROVED and PENDING states (PENDING = in workflow/InReview)
            is_approved = approval_status in ['APPROVED', 'PENDING']

            warnings = []
            if is_paid:
                warnings.append(f"Invoice already has payment status: {payment_status}")
            if is_closed:
                warnings.append(f"Invoice is already closed (status: {invoice_status})")
            if not is_approved:
                warnings.append(f"Invoice not yet approved (status: {approval_status}) - must process first")

            # Can pay if: not paid, not closed, and is approved or in review (PENDING)
            can_pay = not is_paid and not is_closed and is_approved

            return {
                'is_paid': is_paid,
                'payment_status': payment_status,
                'invoice_status': invoice_status,
                'approval_status': approval_status,
                'can_pay': can_pay,
                'warnings': warnings
            }

        except Exception as e:
            # If we can't retrieve invoice, it's definitely not safe to pay
            return {
                'is_paid': False,
                'payment_status': 'ERROR',
                'invoice_status': 'ERROR',
                'approval_status': 'ERROR',
                'can_pay': False,
                'warnings': [f"Error checking invoice: {str(e)}"]
            }

    def mark_invoice_paid(self, invoice_id: str, force: bool = False) -> Dict[str, Any]:
        """
        Mark an invoice as paid using the Invoice Service API.

        ⚠️ DUPLICATE PAYMENT PROTECTION:
        This method now includes automatic duplicate payment protection.
        It will check if the invoice is already paid before proceeding.
        Use force=True to bypass this check (not recommended).

        This uses the 'paid' operation which sends an empty object {} as payload
        and specifies the operation in the query parameter.

        Args:
            invoice_id: The invoice ID to mark as paid
            force: If True, bypass duplicate payment protection (dangerous!)

        Returns:
            Dict containing the operation result

        Raises:
            AlmaAPIError: If invoice is already paid (unless force=True)

        Example - Safe payment with automatic protection:
            >>> result = acq.mark_invoice_paid("123456")

        Example - Force payment (bypass protection):
            >>> result = acq.mark_invoice_paid("123456", force=True)  # NOT RECOMMENDED
        """
        # Duplicate payment protection (unless force=True)
        if not force:
            check = self.check_invoice_payment_status(invoice_id)

            if check['is_paid']:
                error_msg = (
                    f"⚠️ DUPLICATE PAYMENT PREVENTED!\n"
                    f"Invoice {invoice_id} is already paid.\n"
                    f"Payment Status: {check['payment_status']}\n"
                    f"Invoice Status: {check['invoice_status']}\n"
                    f"Use force=True to bypass this protection (not recommended)."
                )
                raise AlmaAPIError(error_msg)

            if not check['can_pay']:
                warnings_text = '\n'.join(f"  - {w}" for w in check['warnings'])
                error_msg = (
                    f"⚠️ Cannot pay invoice {invoice_id}:\n"
                    f"{warnings_text}\n"
                    f"Current state: {check['invoice_status']} / {check['payment_status']}"
                )
                raise AlmaAPIError(error_msg)

            # Log that payment protection check passed
            self.logger.info(f"✓ Payment protection check passed for invoice {invoice_id}")
            self.logger.debug(f"  Current state: {check['invoice_status']} / {check['approval_status']} / {check['payment_status']}")
        else:
            self.logger.warning(f"⚠️ WARNING: Bypassing payment protection for invoice {invoice_id}")

        return self.process_invoice_service(invoice_id, "paid")
    
    def approve_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """
        Process an invoice (convenience method).
        
        This uses the 'process_invoice' operation as described in the blog post.
        According to the documentation, this step is mandatory after creating 
        the invoice and its lines.
        
        Args:
            invoice_id: The invoice ID to process
        
        Returns:
            Dict containing the operation result
        """
        return self.process_invoice_service(invoice_id, "process_invoice")
    
    def reject_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """
        Reject an invoice (convenience method).
        
        Args:
            invoice_id: The invoice ID to reject
        
        Returns:
            Dict containing the operation result
        """
        return self.process_invoice_service(invoice_id, "rejected")
    
    def mark_invoice_in_erp(self, invoice_id: str) -> Dict[str, Any]:
        """
        Mark invoice in ERP system (convenience method).
        
        Args:
            invoice_id: The invoice ID to mark in ERP
        
        Returns:
            Dict containing the operation result
        """
        return self.process_invoice_service(invoice_id, "mark_in_erp")
    
    def get_invoice_summary(self, invoice_id: str) -> Dict[str, str]:
        """
        Get a summary of key invoice information.
        
        Args:
            invoice_id: The invoice ID
        
        Returns:
            Dict containing key invoice information
        """
        try:
            invoice_data = self.get_invoice(invoice_id)
            
            # Handle total_amount - can be dict or float
            total_amount = invoice_data.get("total_amount", {})
            if isinstance(total_amount, dict):
                amount_sum = str(total_amount.get("sum", "0"))
                currency = total_amount.get("currency", {}).get("value", "Unknown")
            else:
                # If it's a float/number, use it directly
                amount_sum = str(total_amount) if total_amount else "0"
                currency = "Unknown"

            # Extract payment status from nested payment object
            payment = invoice_data.get("payment", {})
            payment_status = payment.get("payment_status", {})
            if isinstance(payment_status, dict):
                payment_status_value = payment_status.get("value", "Unknown")
            else:
                payment_status_value = str(payment_status) if payment_status else "Unknown"

            summary = {
                "invoice_id": invoice_data.get("id", "Unknown"),
                "invoice_number": invoice_data.get("number", "Unknown"),
                "vendor_code": invoice_data.get("vendor", {}).get("value", "Unknown"),
                "vendor_name": invoice_data.get("vendor", {}).get("desc", "Unknown"),
                "invoice_date": invoice_data.get("invoice_date", "Unknown"),
                "total_amount": amount_sum,
                "currency": currency,
                "status": invoice_data.get("invoice_status", {}).get("value", "Unknown"),
                "payment_status": payment_status_value
            }
            
            self.logger.info(f"✓ Generated summary for invoice {invoice_id}")
            return summary
            
        except Exception as e:
            self.logger.exception(f"✗ Failed to generate summary for invoice {invoice_id}: {str(e)}")
            raise
    
    def list_invoices(self, limit: int = 10, offset: int = 0,
                     status: Optional[str] = None,
                     vendor_code: Optional[str] = None) -> Dict[str, Any]:
        """
        List invoices with optional filtering.

        Pre-#11 behaviour is preserved bit-for-bit: the method still
        accepts ``limit`` / ``offset`` and returns a single Alma list
        payload (``{"invoice": [...], "total_record_count": N}``). The
        ``offset`` kwarg is honoured by passing it as a base param into
        ``client.iter_paged`` so callers that page manually
        (e.g., ``offset=200`` to skip the first two pages) still see
        the records they expect.

        Pattern source: GitHub issue #11 (API: add iter_paged()
        generator at the client level) -- proof-point migration #1.
        ``list_invoices`` keeps a list-shaped public return for
        backwards compatibility; callers that want streaming should
        switch to ``client.iter_paged(...)`` directly.

        Args:
            limit: Maximum number of results to return.
            offset: Starting point for results.
            status: Optional status filter.
            vendor_code: Optional vendor code filter.

        Returns:
            Dict containing the list of invoices, in the same shape
            the Alma /acq/invoices endpoint returns.
        """
        self.logger.info(f"Listing invoices (limit: {limit}, offset: {offset})")

        # Build query string for filters
        base_params: Dict[str, Any] = {}
        query_parts = []
        if status:
            query_parts.append(f"invoice_status~{status}")
        if vendor_code:
            query_parts.append(f"vendor~{vendor_code}")
        if query_parts:
            base_params["q"] = " AND ".join(query_parts)

        try:
            if offset:
                # Deep-paging fall-through: ``iter_paged`` always starts
                # at offset 0 by design (the issue-#11 contract). The
                # legacy ``offset>0`` window is rarely used in this
                # toolkit (no in-tree caller exercises it), so we fall
                # back to a direct one-page fetch rather than walking
                # ``offset+limit`` records and slicing.
                page_params = {
                    **base_params,
                    "limit": str(limit),
                    "offset": str(offset),
                }
                invoices_data = self.client.get(
                    "almaws/v1/acq/invoices", params=page_params
                ).json()
                total_count = invoices_data.get('total_record_count', 0)
                self.logger.info(
                    f"✓ Successfully retrieved {total_count} invoices"
                )
                return invoices_data

            invoices = list(
                self.client.iter_paged(
                    "almaws/v1/acq/invoices",
                    params=base_params,
                    page_size=limit,
                    record_key="invoice",
                    max_records=limit,
                )
            )

            total_count = len(invoices)
            self.logger.info(f"✓ Successfully retrieved {total_count} invoices")
            # Re-shape into the legacy Alma list payload so existing
            # callers that read ``result["invoice"]`` /
            # ``result["total_record_count"]`` keep working.
            return {
                "invoice": invoices,
                "total_record_count": total_count,
            }

        except Exception as e:
            self.logger.exception(f"✗ Failed to list invoices: {str(e)}")
            raise
    
    def search_invoices(self, query: str, limit: int = 10, offset: int = 0) -> Dict[str, Any]:
        """
        Search invoices with a custom query.
        
        Args:
            query: Search query (e.g., "vendor~VENDOR_CODE AND invoice_status~WAITING_TO_BE_SENT")
            limit: Maximum number of results to return
            offset: Starting point for results
        
        Returns:
            Dict containing the search results
        """
        if not query:
            raise ValueError("Search query is required")
        
        self.logger.info(f"Searching invoices with query: {query}")
        
        params = {
            "q": query,
            "limit": str(limit),
            "offset": str(offset)
        }
        
        try:
            endpoint = "almaws/v1/acq/invoices"
            response = self.client.get(endpoint, params=params)
            
            # Raise for HTTP errors
            if not response.success:
                raise Exception(f"API request failed with status {response.status_code}")
            
            # Parse JSON response
            search_results = response.json()
            
            total_count = search_results.get('total_record_count', 0)
            self.logger.info(f"✓ Search found {total_count} invoices matching query")
            return search_results
            
        except Exception as e:
            self.logger.exception(f"✗ Invoice search failed: {str(e)}")
            raise
    
    def get_invoice_lines(self, invoice_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get invoice lines for a specific invoice using dedicated lines endpoint.

        Args:
            invoice_id: The invoice ID
            limit: Maximum number of lines to retrieve (default: 100)
            offset: Starting offset for pagination (default: 0)

        Returns:
            List of invoice line dictionaries
        """
        if not invoice_id:
            raise ValueError("Invoice ID is required")

        self.logger.info(f"Retrieving lines for invoice: {invoice_id}")

        try:
            # Use dedicated lines endpoint
            endpoint = f"almaws/v1/acq/invoices/{invoice_id}/lines"
            params = {
                "limit": str(limit),
                "offset": str(offset)
            }

            response = self.client.get(endpoint, params=params)

            if not response.success:
                raise Exception(f"API request failed with status {response.status_code}")

            lines_data = response.json()

            # Extract invoice lines from response
            invoice_lines = lines_data.get("invoice_line", [])

            # Ensure it's a list (sometimes single items come as dict)
            if isinstance(invoice_lines, dict):
                invoice_lines = [invoice_lines]

            total_count = lines_data.get('total_record_count', len(invoice_lines))
            self.logger.info(f"✓ Retrieved {len(invoice_lines)} line(s) for invoice {invoice_id} (total: {total_count})")
            return invoice_lines

        except Exception as e:
            self.logger.exception(f"✗ Failed to get invoice lines for {invoice_id}: {str(e)}")
            raise

    def get_pol(self, pol_id: str) -> Dict[str, Any]:
        """
        Retrieve a Purchase Order Line by ID.

        Args:
            pol_id: Purchase Order Line ID

        Returns:
            POL data dictionary
        """
        if not pol_id:
            raise ValueError("POL ID is required")

        endpoint = f"almaws/v1/acq/po-lines/{pol_id}"
        response = self.client.get(endpoint)

        if response.success:
            return response.json()
        else:
            raise AlmaAPIError(f"Failed to get POL {pol_id}")

    def extract_items_from_pol_data(self, pol_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract items from POL data structure.

        Items in POL data are nested in: location → copy (list of copy objects, each is an item).
        This method flattens that structure to return a simple list of item objects.

        Args:
            pol_data: POL data dictionary from get_pol()

        Returns:
            List of item dictionaries extracted from all locations

        Example POL structure:
            {
                "location": [
                    {
                        "copy": [
                            {"pid": "item1", ...},
                            {"pid": "item2", ...}
                        ]
                    },
                    {
                        "copy": [...]
                    }
                ]
            }
        """
        items = []

        # DEBUG: Check if location field exists
        self.logger.info(f"[DEBUG] Checking for 'location' field in POL data...")
        if 'location' not in pol_data:
            self.logger.info(f"[DEBUG] ✗ No 'location' field found in POL data")
            self.logger.info(f"[DEBUG] Available top-level fields: {list(pol_data.keys())}")
            return items

        self.logger.info(f"[DEBUG] ✓ 'location' field found")

        # Navigate to location list
        locations = pol_data.get('location', [])
        self.logger.info(f"[DEBUG] Location type: {type(locations)}")

        # Ensure locations is a list
        if isinstance(locations, dict):
            self.logger.info(f"[DEBUG] Location is a dict, converting to list")
            locations = [locations]

        self.logger.info(f"[DEBUG] Number of locations: {len(locations)}")

        # Extract items from each location's copy list
        for loc_idx, location in enumerate(locations):
            self.logger.debug(f"[DEBUG] Processing location {loc_idx + 1}/{len(locations)}")
            self.logger.info(f"[DEBUG] Location keys: {list(location.keys())}")

            if 'copy' not in location:
                self.logger.info(f"[DEBUG] ✗ No 'copy' field in location {loc_idx + 1}")
                continue

            copies = location.get('copy', [])
            self.logger.info(f"[DEBUG] Copy type: {type(copies)}")

            # Ensure copies is a list
            if isinstance(copies, dict):
                self.logger.info(f"[DEBUG] Copy is a dict, converting to list")
                copies = [copies]

            self.logger.info(f"[DEBUG] Number of copies in location {loc_idx + 1}: {len(copies)}")

            # Each copy is an item
            for copy_idx, copy in enumerate(copies):
                self.logger.info(f"[DEBUG] Copy {copy_idx + 1} keys: {list(copy.keys())[:10]}")  # First 10 keys
                items.append(copy)

        self.logger.info(f"[DEBUG] Total items extracted: {len(items)}")
        self.logger.info(f"✓ Extracted {len(items)} item(s) from POL data")
        return items

    def get_pol_items(self, pol_id: str) -> List[Dict[str, Any]]:
        """
        Get all items associated with a Purchase Order Line using dedicated items endpoint.

        This uses the GET /almaws/v1/acq/po-lines/{pol_id}/items endpoint which
        returns items directly without nested location structure.

        Args:
            pol_id: Purchase Order Line ID

        Returns:
            List of item dictionaries with item_id, status, receiving info, barcode, location

        Raises:
            ValueError: If pol_id is empty or None
            AlmaAPIError: If the API request fails

        Note: If you already have POL data from get_pol(), you can use
              extract_items_from_pol_data() instead to avoid an extra API call.
        """
        if not pol_id:
            raise ValueError("POL ID is required")

        self.logger.info(f"Retrieving items for POL: {pol_id}")

        endpoint = f"almaws/v1/acq/po-lines/{pol_id}/items"
        response = self.client.get(endpoint)

        if response.success:
            items_data = response.json()

            # Handle both single item (dict) and multiple items (list)
            if 'item' in items_data:
                items = items_data['item']
                if isinstance(items, dict):
                    items = [items]
                self.logger.info(f"✓ Retrieved {len(items)} item(s) for POL {pol_id}")
                return items
            else:
                self.logger.info(f"✓ No items found for POL {pol_id}")
                return []
        else:
            raise AlmaAPIError(f"Failed to get items for POL {pol_id}")

    def receive_item(self, pol_id: str, item_id: str,
                    receive_date: Optional[str] = None,
                    department: Optional[str] = None,
                    department_library: Optional[str] = None) -> Dict[str, Any]:
        """
        Receive an existing item in a Purchase Order Line.

        This operation marks an item as received in Alma. The item status will change
        to "received" and the process type will update from "acquisition" to "in transit".

        Args:
            pol_id: Purchase Order Line ID
            item_id: Item ID to receive
            receive_date: Date of receipt in format YYYY-MM-DDZ (e.g., "2025-01-15Z")
                         If not provided, current date will be used by Alma
            department: Department code for receiving (optional)
            department_library: Library code of receiving department (optional)

        Returns:
            Dict containing updated item data

        Raises:
            ValueError: If pol_id or item_id is empty/None
            AlmaAPIError: If the API request fails

        Example:
            >>> acq.receive_item("POL-12345", "23435899800121",
            ...                  receive_date="2025-01-15Z",
            ...                  department="DEPT_CODE",
            ...                  department_library="LIB_CODE")
        """
        if not pol_id:
            raise ValueError("POL ID is required")
        if not item_id:
            raise ValueError("Item ID is required")

        self.logger.info(f"Receiving item {item_id} for POL {pol_id}")

        # Build query parameters
        params = {"op": "receive"}
        if receive_date:
            params["receive_date"] = receive_date
        if department:
            params["department"] = department
        if department_library:
            params["department_library"] = department_library

        # Endpoint for receiving existing item
        endpoint = f"almaws/v1/acq/po-lines/{pol_id}/items/{item_id}"

        # Empty XML body as per API specification
        empty_item_xml = "<item/>"

        try:
            response = self.client.post(
                endpoint,
                data=empty_item_xml,
                params=params,
                content_type='application/xml'
            )

            if response.success:
                self.logger.info(f"✓ Successfully received item {item_id} for POL {pol_id}")
                # API returns XML for this endpoint, try JSON first, fall back to XML parsing
                try:
                    return response.json()
                except:
                    # Response is XML, parse it
                    import xml.etree.ElementTree as ET
                    # Get response text - response has _response attribute from requests library
                    response_text = response._response.text
                    root = ET.fromstring(response_text)
                    # Convert XML to dict with basic structure
                    item_dict = {}
                    for child in root:
                        if len(child) == 0:
                            item_dict[child.tag] = child.text
                        else:
                            # Handle nested elements (like process_type)
                            item_dict[child.tag] = {subchild.tag: subchild.text for subchild in child}
                    return item_dict
            else:
                raise AlmaAPIError(f"Failed to receive item {item_id} for POL {pol_id}")

        except AlmaAPIError:
            raise
        except Exception as e:
            self.logger.exception(f"✗ Failed to receive item {item_id} for POL {pol_id}: {str(e)}")
            raise

    def receive_and_keep_in_department(self,
                                       pol_id: str,
                                       item_id: str,
                                       mms_id: str,
                                       holding_id: str,
                                       library: str,
                                       department: str,
                                       work_order_type: str = "AcqWorkOrder",
                                       work_order_status: str = "CopyCataloging",
                                       receive_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Receive an item and immediately scan it into a department to prevent Transit status.

        This method combines the receive_item operation with a scan-in operation to keep
        the item in the acquisitions department instead of letting it go to "in transit" status.

        Workflow:
        1. Receive the item via acquisitions API
        2. Scan in the item to the specified department with a work order
        3. Item stays in department with work order status instead of going to Transit

        Args:
            pol_id: Purchase Order Line ID
            item_id: Item ID to receive (from POL items)
            mms_id: MMS ID (bibliographic record ID) - needed for scan-in
            holding_id: Holding ID - needed for scan-in
            library: Library code for the department
            department: Department code where item should stay
            work_order_type: Work order type code (default: "AcqWorkOrder")
            work_order_status: Work order status (default: "CopyCataloging")
            receive_date: Optional receive date in format YYYY-MM-DDZ

        Returns:
            Dict containing the final item data after scan-in

        Raises:
            ValueError: If required parameters are missing
            AlmaAPIError: If either API operation fails

        Example:
            >>> # Receive item and keep in acquisitions department
            >>> acq.receive_and_keep_in_department(
            ...     pol_id="POL-12345",
            ...     item_id="23123456789",
            ...     mms_id="99123456789",
            ...     holding_id="22123456789",
            ...     library="MAIN",
            ...     department="ACQ_DEPT"
            ... )

        Notes:
            - Work order type and status must be configured in Alma
            - The item will have process_type="Work Order" instead of "in transit"
            - To complete the work order later, use bibs.scan_in_item with done=True
        """
        if not all([pol_id, item_id, mms_id, holding_id, library, department]):
            raise ValueError(
                "POL ID, item ID, MMS ID, holding ID, library, and department are required"
            )

        self.logger.info(f"\n=== Receiving item and keeping in department ===")
        self.logger.info(f"POL: {pol_id}, Item: {item_id}")
        self.logger.info(f"Department: {department} at library {library}")

        # Step 1: Receive the item
        self.logger.info(f"\nStep 1: Receiving item {item_id}...")
        receive_result = self.receive_item(
            pol_id=pol_id,
            item_id=item_id,
            receive_date=receive_date,
            department=department,
            department_library=library
        )

        # Step 2: Scan in the item to keep it in department
        self.logger.info(f"\nStep 2: Scanning item into department to prevent Transit...")
        bibs = BibliographicRecords(self.client)

        scan_result = bibs.scan_in_item(
            mms_id=mms_id,
            holding_id=holding_id,
            item_pid=item_id,
            library=library,
            department=department,
            work_order_type=work_order_type,
            status=work_order_status,
            done=False  # Keep in department
        )

        if scan_result.success:
            self.logger.info(f"✓ Successfully received and kept item in department {department}")
            self.logger.debug(f"  Work order: {work_order_type} - Status: {work_order_status}")
            return scan_result.json()
        else:
            raise AlmaAPIError(
                f"Failed to scan in item {item_id} after receiving. "
                f"Item was received but may be in Transit status."
            )

    def update_pol(self, pol_id: str, pol_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a Purchase Order Line.
        
        Args:
            pol_id: Purchase Order Line ID
            pol_data: Updated POL data
            
        Returns:
            Updated POL data
        """
        if not pol_id:
            raise ValueError("POL ID is required")
        
        endpoint = f"almaws/v1/acq/po-lines/{pol_id}"
        response = self.client.put(endpoint, data=pol_data)
        
        if response.success:
            return response.json()
        else:
            raise AlmaAPIError(f"Failed to update POL {pol_id}")

    def create_invoice(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new invoice.
        
        Args:
            invoice_data: Invoice data dictionary
            
        Returns:
            Created invoice data with ID
        """
        endpoint = "almaws/v1/acq/invoices"
        response = self.client.post(endpoint, data=invoice_data)
        
        if response.success:
            return response.json()
        else:
            raise AlmaAPIError("Failed to create invoice")

    def create_invoice_line(self, invoice_id: str, 
                        line_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create an invoice line.
        
        Args:
            invoice_id: Invoice ID
            line_data: Invoice line data
            
        Returns:
            Created invoice line data
        """
        if not invoice_id:
            raise ValueError("Invoice ID is required")
        
        endpoint = f"almaws/v1/acq/invoices/{invoice_id}/lines"
        response = self.client.post(endpoint, data=line_data)
        
        if response.success:
            return response.json()
        else:
            raise AlmaAPIError(f"Failed to create invoice line for {invoice_id}")

    # =========================================================================
    # POL Utility Methods - Extract Information from POLs
    # =========================================================================

    def get_vendor_from_pol(self, pol_id: str) -> Optional[str]:
        """
        Extract vendor code from a POL.

        Retrieves the POL data and extracts the vendor code, which is useful
        when creating invoices for POLs without knowing the vendor in advance.

        Args:
            pol_id: POL number (e.g., "POL-12349")

        Returns:
            Vendor code string if found, None if vendor not found or POL doesn't exist

        Raises:
            AlmaAPIError: If POL retrieval fails

        Example:
            >>> vendor_code = acq.get_vendor_from_pol("POL-12349")
            >>> print(f"Vendor: {vendor_code}")
            Vendor: RIALTO

        Example - Handle missing vendor:
            >>> vendor_code = acq.get_vendor_from_pol("POL-12349")
            >>> if vendor_code:
            ...     invoice = acq.create_invoice_simple(
            ...         invoice_number="INV-001",
            ...         invoice_date="2025-10-22",
            ...         vendor_code=vendor_code,
            ...         total_amount=100.00
            ...     )
            ... else:
            ...     print("No vendor found on POL")
        """
        try:
            # Get POL data
            pol_data = self.get_pol(pol_id)

            # Extract vendor code from nested structure
            # Structure: pol_data -> vendor -> value
            vendor_code = pol_data.get('vendor', {}).get('value')

            if vendor_code:
                self.logger.info(f"✓ Found vendor in POL {pol_id}: {vendor_code}")
            else:
                self.logger.warning(f"⚠️ No vendor found in POL {pol_id}")

            return vendor_code

        except AlmaAPIError as e:
            self.logger.exception(f"✗ Failed to get vendor from POL {pol_id}: {e}")
            raise

    def get_fund_from_pol(self, pol_id: str) -> Optional[str]:
        """
        Extract primary fund code from a POL.

        Retrieves the POL data and extracts the first fund code from the
        fund_distribution array. This is useful when creating invoice lines
        without knowing the fund code in advance.

        Note: If POL has multiple funds, only the first (primary) fund is returned.

        Args:
            pol_id: POL number (e.g., "POL-12349")

        Returns:
            Fund code string if found, None if no fund found or POL doesn't exist

        Raises:
            AlmaAPIError: If POL retrieval fails

        Example:
            >>> fund_code = acq.get_fund_from_pol("POL-12349")
            >>> print(f"Fund: {fund_code}")
            Fund: LIBRARY_FUND

        Example - Auto-populate invoice line:
            >>> fund_code = acq.get_fund_from_pol("POL-12349")
            >>> if fund_code:
            ...     line = acq.create_invoice_line_simple(
            ...         invoice_id="123456789",
            ...         pol_id="POL-12349",
            ...         amount=100.00,
            ...         fund_code=fund_code
            ...     )
            ... else:
            ...     print("No fund found on POL - must provide explicitly")

        Example - Used automatically by create_invoice_line_simple:
            >>> # Fund code extracted automatically if not provided
            >>> line = acq.create_invoice_line_simple(
            ...     invoice_id="123456789",
            ...     pol_id="POL-12349",
            ...     amount=100.00
            ...     # fund_code omitted - will call get_fund_from_pol()
            ... )
        """
        try:
            # Get POL data
            pol_data = self.get_pol(pol_id)

            # Extract fund code from nested structure
            # Structure: pol_data -> fund_distribution (array) -> [0] -> fund_code -> value
            fund_distribution = pol_data.get('fund_distribution', [])

            if fund_distribution and len(fund_distribution) > 0:
                # Get first fund (primary fund)
                first_fund = fund_distribution[0]
                fund_code = first_fund.get('fund_code', {}).get('value')

                if fund_code:
                    self.logger.info(f"✓ Found fund in POL {pol_id}: {fund_code}")
                    if len(fund_distribution) > 1:
                        self.logger.debug(f"  Note: POL has {len(fund_distribution)} funds, using first (primary) fund")
                    return fund_code

            self.logger.warning(f"⚠️ No fund distribution found in POL {pol_id}")
            return None

        except AlmaAPIError as e:
            self.logger.exception(f"✗ Failed to get fund from POL {pol_id}: {e}")
            raise

    def get_price_from_pol(self, pol_id: str) -> Optional[float]:
        """
        Extract price (list price) from a POL.

        Retrieves the POL data and extracts the list price. This is useful when
        creating invoice lines to ensure the correct amount is invoiced.

        Args:
            pol_id: POL number (e.g., "POL-12349")

        Returns:
            Price as float if found, None if no price found or POL doesn't exist

        Raises:
            AlmaAPIError: If POL retrieval fails

        Example:
            >>> price = acq.get_price_from_pol("POL-12349")
            >>> print(f"POL Price: {price}")
            POL Price: 180.0

        Example - Create invoice line with POL's actual price:
            >>> price = acq.get_price_from_pol("POL-12349")
            >>> if price:
            ...     line = acq.create_invoice_line_simple(
            ...         invoice_id="123456789",
            ...         pol_id="POL-12349",
            ...         amount=price,  # Use POL's actual price
            ...         quantity=1
            ...     )

        Example - Complete workflow with POL prices:
            >>> pol_ids = ["POL-12349", "POL-12350"]
            >>> lines = []
            >>> for pol_id in pol_ids:
            ...     price = acq.get_price_from_pol(pol_id)
            ...     if price:
            ...         lines.append({"pol_id": pol_id, "amount": price})
            >>>
            >>> result = acq.create_invoice_with_lines(
            ...     invoice_number="INV-2025-001",
            ...     invoice_date="2025-10-22",
            ...     vendor_code="RIALTO",
            ...     lines=lines
            ... )
        """
        try:
            # Get POL data
            pol_data = self.get_pol(pol_id)

            # Extract price from nested structure
            # Structure: pol_data -> price -> sum
            price = pol_data.get('price', {}).get('sum')

            if price is not None:
                price_float = float(price)
                currency = pol_data.get('price', {}).get('currency', {}).get('value', 'N/A')
                self.logger.info(f"✓ Found price in POL {pol_id}: {price_float} {currency}")
                return price_float

            self.logger.warning(f"⚠️ No price found in POL {pol_id}")
            return None

        except (ValueError, TypeError) as e:
            self.logger.exception(f"⚠️ Could not parse price from POL {pol_id}: {e}")
            return None
        except AlmaAPIError as e:
            self.logger.exception(f"✗ Failed to get price from POL {pol_id}: {e}")
            raise

    def check_pol_invoiced(self, pol_id: str) -> Dict[str, Any]:
        """
        Check if a POL is already linked to any invoice lines.

        This is a critical validation to prevent double-invoicing. Searches through
        active and waiting invoices to find any existing invoice lines for the POL.

        Args:
            pol_id: POL number (e.g., "POL-12349")

        Returns:
            Dict with:
                - is_invoiced: bool - Whether POL has any invoice lines
                - invoice_count: int - Number of invoices with this POL
                - invoices: List[Dict] - List of invoices containing this POL
                  Each invoice dict contains:
                    - invoice_id: str
                    - invoice_number: str
                    - line_id: str
                    - amount: float
                    - status: str

        Raises:
            AlmaAPIError: If invoice search fails

        Example - Check before creating invoice line:
            >>> check = acq.check_pol_invoiced("POL-12349")
            >>> if check['is_invoiced']:
            ...     print(f"⚠️  POL already has {check['invoice_count']} invoice(s)")
            ...     for inv in check['invoices']:
            ...         print(f"  - Invoice {inv['invoice_number']}: {inv['amount']}")
            ... else:
            ...     # Safe to create invoice line
            ...     line = acq.create_invoice_line_simple(...)

        Example - Prevent double invoicing in workflow:
            >>> def safe_create_invoice_line(pol_id, amount):
            ...     check = acq.check_pol_invoiced(pol_id)
            ...     if check['is_invoiced']:
            ...         raise ValueError(f"POL {pol_id} already invoiced")
            ...     return acq.create_invoice_line_simple(...)

        Note:
            - This performs API searches which may be slow for large datasets
            - Searches invoices with statuses: ACTIVE, WAITING_TO_BE_SENT,
              WAITING_FOR_INVOICE, IN_REVIEW
            - Closed/cancelled invoices are not checked
            - May not find invoices if Alma API search has limitations
            - Best used as a safety check, not guaranteed to be exhaustive
        """
        try:
            result = {
                'is_invoiced': False,
                'invoice_count': 0,
                'invoices': []
            }

            self.logger.info(f"Checking if POL {pol_id} is already invoiced...")

            # Direct POL search - Alma API supports searching by pol_number
            # Query format: pol_number~{pol_id}
            # This is much more efficient than iterating through all invoices
            query = f"pol_number~{pol_id}"

            try:
                # Use the list invoices endpoint with POL number query
                endpoint = "almaws/v1/acq/invoices"
                params = {
                    "q": query,
                    "limit": 100  # Should cover most cases
                }

                response = self.client.get(endpoint, params=params)

                if response.success:
                    data = response.json()
                    invoices = data.get('invoice', [])

                    if invoices:
                        self.logger.debug(f"  Found {len(invoices)} invoice(s) containing POL {pol_id}")

                        # Get detailed line information for each invoice
                        for invoice in invoices:
                            invoice_id = invoice.get('id')
                            invoice_number = invoice.get('number')
                            invoice_status = invoice.get('invoice_status', {}).get('value', 'N/A')

                            # Extract payment status from invoice
                            payment_info = invoice.get('payment', {})
                            payment_status = payment_info.get('payment_status', {}).get('value', 'UNKNOWN')

                            # Extract approval status
                            approval_status = invoice.get('invoice_approval_status', {}).get('value', 'N/A')

                            # Get lines to find the specific line for this POL
                            lines = self.get_invoice_lines(invoice_id)

                            # Find line(s) matching our POL
                            for line in lines:
                                line_pol = line.get('po_line')
                                if line_pol == pol_id:
                                    # Found matching line!
                                    result['is_invoiced'] = True
                                    result['invoice_count'] += 1

                                    # Extract price information
                                    price = line.get('price', {})
                                    if isinstance(price, dict):
                                        amount = price.get('sum', 'N/A')
                                        currency = price.get('currency', {}).get('value', 'N/A')
                                        amount_display = f"{amount} {currency}"
                                    else:
                                        amount_display = str(price)

                                    result['invoices'].append({
                                        'invoice_id': invoice_id,
                                        'invoice_number': invoice_number,
                                        'invoice_status': invoice_status,
                                        'payment_status': payment_status,
                                        'approval_status': approval_status,
                                        'line_id': line.get('id'),
                                        'amount': amount_display,
                                        'line_status': line.get('status', {}).get('value', 'N/A')
                                    })
                                    self.logger.debug(f"  ⚠️  Found: Invoice {invoice_number} (status: {invoice_status}, payment: {payment_status}) has line for {pol_id}: {amount_display}")

                    if not result['is_invoiced']:
                        self.logger.debug(f"  ✓ POL {pol_id} is not yet invoiced")
                    else:
                        self.logger.debug(f"  ⚠️  POL {pol_id} has {result['invoice_count']} existing invoice line(s)")

                else:
                    self.logger.debug(f"  ⚠️ Could not search invoices: {response.status_code}")
                    result['search_error'] = f"API returned status {response.status_code}"

            except Exception as e:
                self.logger.exception(f"  ⚠️ Could not complete invoice search: {e}")
                # Return inconclusive result
                result['search_error'] = str(e)

            return result

        except AlmaAPIError as e:
            self.logger.exception(f"✗ Failed to check if POL {pol_id} is invoiced: {e}")
            raise

    # =========================================================================
    # End of POL Utility Methods
    # =========================================================================

    def get_environment(self) -> str:
        """Get the current environment from the client."""
        return self.client.get_environment()
    
    def test_connection(self) -> bool:
        """
        Test if the acquisitions endpoints are accessible.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try to list a small number of invoices as a connection test
            response = self.client.get("almaws/v1/acq/invoices", params={"limit": "1"})
            success = response.status_code == 200
            
            if success:
                self.logger.info(f"✓ Acquisitions API connection successful ({self.environment})")
            else:
                self.logger.error(f"✗ Acquisitions API connection failed: {response.status_code}")
            
            return success
            
        except Exception as e:
            self.logger.exception(f"✗ Acquisitions API connection error: {e}")
            return False


# Usage examples and integration
if __name__ == "__main__":
    """
    Example usage of the Acquisitions domain with AlmaAPIClient.
    """
    # Mirror INFO+ logger output to stderr so CLI users see the
    # progress messages that the alma_logging file handlers also
    # capture. Library code itself emits no raw stdout (issue #14).
    import logging as _logging
    import sys as _sys
    _stderr_handler = _logging.StreamHandler(_sys.stderr)
    _stderr_handler.setFormatter(_logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    _logging.getLogger("almapi").addHandler(_stderr_handler)
    _logging.getLogger("almapi").setLevel(_logging.INFO)

    try:
        # Initialize the base client
        client = AlmaAPIClient('SANDBOX')  # or 'PRODUCTION'
        
        # Test the base connection first
        if not client.test_connection():
            print("Cannot proceed - base API connection failed")
            exit(1)
        
        # Create the acquisitions domain
        acq = Acquisitions(client)
        
        # Test acquisitions connection
        if not acq.test_connection():
            print("Cannot proceed - acquisitions API connection failed")
            exit(1)
        
        print(f"\n=== Acquisitions Domain Test ({acq.get_environment()}) ===")
        
        # Example: List invoices
        try:
            print("\nTesting invoice listing...")
            invoices = acq.list_invoices(limit=5)
            print(f"Found {invoices.get('total_record_count', 0)} total invoices")
            
            # Show first invoice if available
            invoice_list = invoices.get('invoice', [])
            if isinstance(invoice_list, list) and invoice_list:
                first_invoice = invoice_list[0]
                print(f"First invoice: {first_invoice.get('number', 'Unknown')} - {first_invoice.get('invoice_status', {}).get('value', 'Unknown')}")
            elif isinstance(invoice_list, dict):
                print(f"Single invoice: {invoice_list.get('number', 'Unknown')} - {invoice_list.get('invoice_status', {}).get('value', 'Unknown')}")
            
        except Exception as e:
            print(f"Invoice listing test failed: {e}")
        
        # Example: Test with specific invoice ID (you'll need to provide a real one)
        test_invoice_id = input("\nEnter an invoice ID to test (or press Enter to skip): ").strip()
        
        if test_invoice_id:
            try:
                print(f"\nTesting invoice retrieval for ID: {test_invoice_id}")
                
                # Get invoice details
                invoice = acq.get_invoice(test_invoice_id)
                print(f"Invoice number: {invoice.get('number', 'Unknown')}")
                
                # Get invoice summary
                summary = acq.get_invoice_summary(test_invoice_id)
                print(f"Summary: {summary}")
                
                # Get invoice lines
                lines = acq.get_invoice_lines(test_invoice_id)
                print(f"Invoice has {len(lines)} lines")
                
            except Exception as e:
                print(f"Invoice test failed: {e}")
        
        print("\n=== Acquisitions Domain Test Complete ===")
        
    except Exception as e:
        print(f"Setup error: {e}")
        print("\nMake sure you have set the environment variable:")
        print("export ALMA_SB_API_KEY='your_sandbox_api_key'")