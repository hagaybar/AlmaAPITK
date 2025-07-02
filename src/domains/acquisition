"""
Acquisitions Domain Class for Alma API
Handles invoice management operations using the AlmaAPIClient foundation.
"""
from typing import Any, Dict, List, Optional, Union
from src.client.AlmaAPIClient import AlmaAPIClient


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
        
        print(f"Retrieving invoice: {invoice_id} from {self.environment}")
        
        params = {"view": view} if view != "full" else None
        
        try:
            endpoint = f"almaws/v1/acq/invoices/{invoice_id}"
            response = self.client.get(endpoint, params=params)
            
            # Raise for HTTP errors
            response.raise_for_status()
            
            # Parse JSON response
            invoice_data = response.json()
            
            print(f"✓ Successfully retrieved invoice {invoice_id}")
            return invoice_data
            
        except Exception as e:
            print(f"✗ Failed to retrieve invoice {invoice_id}: {str(e)}")
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
            print(f"⚠️  Warning: '{operation}' is not in known operations: {valid_operations}")
        
        print(f"Processing invoice service: {invoice_id}, operation: {operation}")
        
        try:
            endpoint = f"almaws/v1/acq/invoices/{invoice_id}"
            params = {"op": operation}
            
            # Send empty object as payload according to API documentation
            empty_payload = {}
            
            response = self.client.post(endpoint, data=empty_payload, params=params)
            
            # Raise for HTTP errors
            response.raise_for_status()
            
            # Parse JSON response
            result_data = response.json()
            
            print(f"✓ Successfully processed invoice service {operation} for invoice {invoice_id}")
            return result_data
            
        except Exception as e:
            print(f"✗ Failed to process invoice service {operation} for invoice {invoice_id}: {str(e)}")
            raise
    
    def mark_invoice_paid(self, invoice_id: str) -> Dict[str, Any]:
        """
        Mark an invoice as paid using the Invoice Service API.
        
        This uses the 'paid' operation which sends an empty object {} as payload
        and specifies the operation in the query parameter.
        
        Args:
            invoice_id: The invoice ID to mark as paid
        
        Returns:
            Dict containing the operation result
        """
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
            
            summary = {
                "invoice_id": invoice_data.get("id", "Unknown"),
                "invoice_number": invoice_data.get("number", "Unknown"),
                "vendor_code": invoice_data.get("vendor", {}).get("value", "Unknown"),
                "vendor_name": invoice_data.get("vendor", {}).get("desc", "Unknown"),
                "invoice_date": invoice_data.get("invoice_date", "Unknown"),
                "total_amount": str(invoice_data.get("total_amount", {}).get("sum", "0")),
                "currency": invoice_data.get("total_amount", {}).get("currency", {}).get("value", "Unknown"),
                "status": invoice_data.get("invoice_status", {}).get("value", "Unknown"),
                "payment_status": invoice_data.get("payment_status", {}).get("value", "Unknown")
            }
            
            print(f"✓ Generated summary for invoice {invoice_id}")
            return summary
            
        except Exception as e:
            print(f"✗ Failed to generate summary for invoice {invoice_id}: {str(e)}")
            raise
    
    def list_invoices(self, limit: int = 10, offset: int = 0, 
                     status: Optional[str] = None, 
                     vendor_code: Optional[str] = None) -> Dict[str, Any]:
        """
        List invoices with optional filtering.
        
        Args:
            limit: Maximum number of results to return
            offset: Starting point for results
            status: Optional status filter
            vendor_code: Optional vendor code filter
        
        Returns:
            Dict containing the list of invoices
        """
        print(f"Listing invoices (limit: {limit}, offset: {offset})")
        
        params = {
            "limit": str(limit),
            "offset": str(offset)
        }
        
        # Build query string for filters
        query_parts = []
        if status:
            query_parts.append(f"invoice_status~{status}")
        if vendor_code:
            query_parts.append(f"vendor~{vendor_code}")
        
        if query_parts:
            params["q"] = " AND ".join(query_parts)
        
        try:
            endpoint = "almaws/v1/acq/invoices"
            response = self.client.get(endpoint, params=params)
            
            # Raise for HTTP errors
            response.raise_for_status()
            
            # Parse JSON response
            invoices_data = response.json()
            
            total_count = invoices_data.get('total_record_count', 0)
            print(f"✓ Successfully retrieved {total_count} invoices")
            return invoices_data
            
        except Exception as e:
            print(f"✗ Failed to list invoices: {str(e)}")
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
        
        print(f"Searching invoices with query: {query}")
        
        params = {
            "q": query,
            "limit": str(limit),
            "offset": str(offset)
        }
        
        try:
            endpoint = "almaws/v1/acq/invoices"
            response = self.client.get(endpoint, params=params)
            
            # Raise for HTTP errors
            response.raise_for_status()
            
            # Parse JSON response
            search_results = response.json()
            
            total_count = search_results.get('total_record_count', 0)
            print(f"✓ Search found {total_count} invoices matching query")
            return search_results
            
        except Exception as e:
            print(f"✗ Invoice search failed: {str(e)}")
            raise
    
    def get_invoice_lines(self, invoice_id: str) -> List[Dict[str, Any]]:
        """
        Get invoice lines for a specific invoice.
        
        Args:
            invoice_id: The invoice ID
        
        Returns:
            List of invoice line dictionaries
        """
        try:
            invoice_data = self.get_invoice(invoice_id)
            
            # Extract invoice lines
            invoice_lines = invoice_data.get("invoice_line", [])
            
            # Ensure it's a list (sometimes single items come as dict)
            if isinstance(invoice_lines, dict):
                invoice_lines = [invoice_lines]
            
            print(f"✓ Retrieved {len(invoice_lines)} lines for invoice {invoice_id}")
            return invoice_lines
            
        except Exception as e:
            print(f"✗ Failed to get invoice lines for {invoice_id}: {str(e)}")
            raise
    
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
                print(f"✓ Acquisitions API connection successful ({self.environment})")
            else:
                print(f"✗ Acquisitions API connection failed: {response.status_code}")
            
            return success
            
        except Exception as e:
            print(f"✗ Acquisitions API connection error: {e}")
            return False


# Usage examples and integration
if __name__ == "__main__":
    """
    Example usage of the Acquisitions domain with AlmaAPIClient.
    """
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