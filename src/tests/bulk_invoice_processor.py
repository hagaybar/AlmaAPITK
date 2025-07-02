#!/usr/bin/env python3
"""
Automated Bulk Invoice Processor
Processes invoices from a daily report without user interaction.
Uses config file for settings.
"""

import sys
import os
import json
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any
import logging

# Import our Alma classes
try:
    from src.client.AlmaAPIClient import AlmaAPIClient
    from src.domains.acquisition import Acquisitions
except ImportError as e:
    print(f"Could not import required classes: {e}")
    print("Make sure AlmaAPIClient.py and acquisitions.py are in the same directory.")
    sys.exit(1)


class AutomatedInvoiceProcessor:
    """
    Automated invoice processor that runs without user interaction.
    """
    
    def __init__(self, config_file: str = 'invoice_processor_config.json'):
        """
        Initialize the processor with config file.
        
        Args:
            config_file: Path to configuration file
        """
        self.config = self.load_config(config_file)
        self.setup_logging()
        self.results = []
        self.setup_alma_client()
    
    def load_config(self, config_file: str) -> Dict[str, Any]:
        """
        Load configuration from JSON file.
        
        Args:
            config_file: Path to config file
        
        Returns:
            Configuration dictionary
        """
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Validate required fields
            required_fields = ['environment', 'excel_file_path', 'output_directory']
            missing_fields = [field for field in required_fields if field not in config]
            
            if missing_fields:
                raise ValueError(f"Missing required config fields: {missing_fields}")
            
            # Set defaults for optional fields
            config.setdefault('log_level', 'INFO')
            config.setdefault('backup_reports', True)
            config.setdefault('max_errors_before_stop', None)
            
            return config
            
        except FileNotFoundError:
            print(f"Config file not found: {config_file}")
            print("Creating sample config file...")
            self.create_sample_config(config_file)
            sys.exit(1)
        except Exception as e:
            print(f"Error loading config: {e}")
            sys.exit(1)
    
    def create_sample_config(self, config_file: str):
        """Create a sample configuration file."""
        sample_config = {
            "environment": "SANDBOX",
            "excel_file_path": "/path/to/daily_invoice_report.xlsx",
            "output_directory": "",
            "log_level": "INFO",
            "backup_reports": True,
            "max_errors_before_stop": None,
            "comments": {
                "environment": "SANDBOX or PRODUCTION",
                "excel_file_path": "Full path to the Excel file with invoice IDs in first column",
                "output_directory": "Directory for output files (empty = current directory)",
                "log_level": "DEBUG, INFO, WARNING, ERROR",
                "backup_reports": "Whether to keep backup copies of processed reports",
                "max_errors_before_stop": "Stop processing after N errors (null = no limit)"
            }
        }
        
        with open(config_file, 'w') as f:
            json.dump(sample_config, f, indent=2)
        
        print(f"Sample config created: {config_file}")
        print("Please edit the config file with your settings and run again.")
    
    def setup_logging(self):
        """Setup logging based on config."""
        # Handle empty output_directory - use current directory
        output_dir = self.config['output_directory'].strip() if self.config['output_directory'] else '.'
        self.config['output_directory'] = output_dir
        
        # Create output directory if it doesn't exist (but not for current dir)
        if output_dir != '.':
            os.makedirs(output_dir, exist_ok=True)
        
        # Setup log file with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = os.path.join(self.config['output_directory'], f'invoice_processor_{timestamp}.log')
        
        # Configure logging
        log_level = getattr(logging, self.config['log_level'].upper(), logging.INFO)
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Starting automated invoice processor")
        self.logger.info(f"Config: {self.config}")
        self.logger.info(f"Log file: {log_file}")
    
    def setup_alma_client(self):
        """Setup Alma API client and acquisitions domain."""
        try:
            environment = self.config['environment']
            self.logger.info(f"Setting up Alma client for {environment}...")
            
            self.client = AlmaAPIClient(environment)
            self.acq = Acquisitions(self.client)
            
            # Test connection
            if not self.client.test_connection():
                raise Exception("Failed to connect to Alma API")
            
            if not self.acq.test_connection():
                raise Exception("Failed to connect to Acquisitions API")
            
            self.logger.info(f"Successfully connected to Alma {environment}")
            
        except Exception as e:
            self.logger.error(f"Failed to setup Alma client: {e}")
            raise
    
    def validate_excel_file(self) -> bool:
        """
        Validate that the Excel file exists and is readable.
        
        Returns:
            True if file is valid, False otherwise
        """
        excel_file = self.config['excel_file_path']
        
        if not os.path.exists(excel_file):
            self.logger.error(f"Excel file not found: {excel_file}")
            return False
        
        try:
            # Try to read the file to ensure it's valid
            df = pd.read_excel(excel_file, nrows=1)
            self.logger.info(f"Excel file validated: {excel_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Invalid Excel file {excel_file}: {e}")
            return False
    
    def read_invoice_ids_from_excel(self) -> List[str]:
        """
        Read invoice IDs from the first column of the configured Excel file.
        
        Returns:
            List of invoice IDs (as strings)
        """
        excel_file = self.config['excel_file_path']
        
        try:
            self.logger.info(f"Reading invoice IDs from: {excel_file}")
            
            # Read Excel file - first column only
            df = pd.read_excel(excel_file, usecols=[0])
            
            # Get the first column (regardless of header name)
            first_column = df.iloc[:, 0]
            
            # Convert to string and remove any NaN values
            invoice_ids = []
            for value in first_column:
                if pd.notna(value):  # Skip NaN/empty cells
                    invoice_id = str(value).strip()
                    if invoice_id:  # Skip empty strings
                        invoice_ids.append(invoice_id)
            
            self.logger.info(f"Found {len(invoice_ids)} invoice IDs in Excel file")
            self.logger.debug(f"First 5 invoice IDs: {invoice_ids[:5]}")
            
            return invoice_ids
            
        except Exception as e:
            self.logger.error(f"Failed to read Excel file: {e}")
            raise
    
    def process_single_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """
        Process a single invoice: get initial state, check if already closed, mark as paid if needed, verify.
        
        Args:
            invoice_id: The invoice ID to process
        
        Returns:
            Dict with processing results
        """
        result = {
            'invoice_id': invoice_id,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'initial_status': 'Unknown',
            'initial_payment_status': 'Unknown',
            'final_status': 'Unknown',
            'final_payment_status': 'Unknown',
            'operation_success': False,
            'status_changed': False,
            'payment_status_changed': False,
            'skipped': False,
            'skip_reason': None,
            'error_message': None
        }
        
        try:
            self.logger.debug(f"Processing invoice: {invoice_id}")
            
            # Step 1: Get initial state
            initial_invoice = self.acq.get_invoice(invoice_id)
            
            result['initial_status'] = initial_invoice.get('invoice_status', {}).get('value', 'Unknown')
            result['initial_payment_status'] = initial_invoice.get('payment_status', {}).get('value', 'Unknown')
            
            self.logger.debug(f"Invoice {invoice_id} - Initial: {result['initial_status']}/{result['initial_payment_status']}")
            
            # Step 2: Check if invoice is already closed/paid - skip if so
            closed_statuses = ['CLOSED', 'PAID', 'CANCELLED']  # Add other "final" statuses as needed
            closed_payment_statuses = ['PAID', 'FULLY_PAID']   # Add other "paid" statuses as needed
            
            if (result['initial_status'] in closed_statuses or 
                result['initial_payment_status'] in closed_payment_statuses):
                
                result['skipped'] = True
                result['skip_reason'] = f"Already closed - Status: {result['initial_status']}, Payment: {result['initial_payment_status']}"
                result['final_status'] = result['initial_status']
                result['final_payment_status'] = result['initial_payment_status']
                result['operation_success'] = True  # Mark as success since no action was needed
                
                self.logger.info(f"Invoice {invoice_id} - Skipped: {result['skip_reason']}")
                return result
            
            # Step 3: Mark as paid (only if not already closed)
            self.logger.debug(f"Invoice {invoice_id} - Attempting to mark as paid...")
            payment_result = self.acq.mark_invoice_paid(invoice_id)
            result['operation_success'] = True
            
            # Step 4: Verify change
            updated_invoice = self.acq.get_invoice(invoice_id)
            
            result['final_status'] = updated_invoice.get('invoice_status', {}).get('value', 'Unknown')
            result['final_payment_status'] = updated_invoice.get('payment_status', {}).get('value', 'Unknown')
            
            # Check for changes
            result['status_changed'] = result['initial_status'] != result['final_status']
            result['payment_status_changed'] = result['initial_payment_status'] != result['final_payment_status']
            
            if result['status_changed'] or result['payment_status_changed']:
                self.logger.info(f"Invoice {invoice_id} - Status changed: {result['initial_status']}/{result['initial_payment_status']} -> {result['final_status']}/{result['final_payment_status']}")
            else:
                self.logger.info(f"Invoice {invoice_id} - No status change: {result['final_status']}/{result['final_payment_status']}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing invoice {invoice_id}: {e}")
            result['error_message'] = str(e)
            return result
    
    def process_all_invoices(self, invoice_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Process all invoices from the list.
        
        Args:
            invoice_ids: List of invoice IDs to process
        
        Returns:
            List of processing results
        """
        self.logger.info(f"Starting processing of {len(invoice_ids)} invoices")
        
        results = []
        successful_count = 0
        skipped_count = 0
        error_count = 0
        max_errors = self.config.get('max_errors_before_stop')
        
        for i, invoice_id in enumerate(invoice_ids, 1):
            result = self.process_single_invoice(invoice_id)
            results.append(result)
            
            if result['operation_success']:
                if result.get('skipped', False):
                    skipped_count += 1
                else:
                    successful_count += 1
            else:
                error_count += 1
                
                # Check if we should stop due to too many errors
                if max_errors and error_count >= max_errors:
                    self.logger.error(f"Stopping processing - reached maximum errors ({max_errors})")
                    break
            
            # Log progress every 10 invoices
            if i % 10 == 0:
                self.logger.info(f"Progress: {i}/{len(invoice_ids)} processed ({successful_count} processed, {skipped_count} skipped, {error_count} errors)")
        
        self.logger.info(f"Processing complete - Total: {len(results)}, Processed: {successful_count}, Skipped: {skipped_count}, Errors: {error_count}")
        
        return results
    
    def create_tsv_report(self, results: List[Dict[str, Any]]) -> str:
        """
        Create a TSV report of all processed invoices.
        
        Args:
            results: List of processing results
        
        Returns:
            Path to the created TSV file
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(self.config['output_directory'], f'invoice_processing_results_{timestamp}.tsv')
        
        try:
            self.logger.info(f"Creating TSV report: {output_file}")
            
            # Create DataFrame from results
            df = pd.DataFrame(results)
            
            # Reorder columns for better readability
            column_order = [
                'invoice_id',
                'timestamp',
                'operation_success',
                'skipped',
                'skip_reason',
                'initial_status',
                'final_status',
                'status_changed',
                'initial_payment_status',
                'final_payment_status',
                'payment_status_changed',
                'error_message'
            ]
            
            # Ensure all columns exist
            for col in column_order:
                if col not in df.columns:
                    df[col] = None
            
            df = df[column_order]
            
            # Save as TSV
            df.to_csv(output_file, sep='\t', index=False)
            
            # Log summary statistics
            if results:
                successful = sum(1 for r in results if r['operation_success'] and not r.get('skipped', False))
                skipped = sum(1 for r in results if r.get('skipped', False))
                with_changes = sum(1 for r in results if r['status_changed'] or r['payment_status_changed'])
                
                self.logger.info(f"TSV report created: {output_file}")
                self.logger.info(f"Total records: {len(results)}, Processed: {successful}, Skipped: {skipped}, With changes: {with_changes}")
            
            return output_file
            
        except Exception as e:
            self.logger.error(f"Failed to create TSV report: {e}")
            raise
    
    def backup_source_file(self):
        """Create a backup of the source Excel file if configured."""
        if not self.config.get('backup_reports', False):
            return
        
        try:
            excel_file = self.config['excel_file_path']
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Handle empty output directory
            output_dir = self.config['output_directory'] if self.config['output_directory'] else '.'
            backup_dir = os.path.join(output_dir, 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            
            filename = os.path.basename(excel_file)
            name, ext = os.path.splitext(filename)
            backup_file = os.path.join(backup_dir, f'{name}_{timestamp}{ext}')
            
            import shutil
            shutil.copy2(excel_file, backup_file)
            
            self.logger.info(f"Source file backed up to: {backup_file}")
            
        except Exception as e:
            self.logger.warning(f"Failed to backup source file: {e}")
    
    def run(self):
        """Main execution method."""
        try:
            self.logger.info("=" * 50)
            self.logger.info("AUTOMATED INVOICE PROCESSOR STARTED")
            self.logger.info("=" * 50)
            
            # Validate Excel file
            if not self.validate_excel_file():
                self.logger.error("Excel file validation failed")
                return False
            
            # Backup source file if configured
            self.backup_source_file()
            
            # Read invoice IDs
            invoice_ids = self.read_invoice_ids_from_excel()
            
            if not invoice_ids:
                self.logger.warning("No invoice IDs found in Excel file")
                return False
            
            # Process all invoices
            results = self.process_all_invoices(invoice_ids)
            
            # Create TSV report
            report_file = self.create_tsv_report(results)
            
            # Log final summary
            successful = sum(1 for r in results if r['operation_success'] and not r.get('skipped', False))
            skipped = sum(1 for r in results if r.get('skipped', False))
            error_count = len(results) - successful - skipped
            
            self.logger.info("=" * 50)
            self.logger.info("PROCESSING COMPLETED SUCCESSFULLY")
            self.logger.info(f"Total invoices: {len(results)}")
            self.logger.info(f"Processed: {successful}")
            self.logger.info(f"Skipped (already closed): {skipped}")
            self.logger.info(f"Errors: {error_count}")
            self.logger.info(f"Report: {report_file}")
            self.logger.info("=" * 50)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Fatal error during processing: {e}")
            return False


def main():
    """Main function."""
    config_file = 'invoice_processor_config.json'
    
    # Allow config file to be specified as command line argument
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    
    try:
        processor = AutomatedInvoiceProcessor(config_file)
        success = processor.run()
        
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()