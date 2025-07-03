"""
TSV Generator Utility
Config-driven utility for creating TSV files from Alma sets.
Supports flexible column definitions and multiple data sources.
"""
import json
import os
import csv
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# Import your existing classes
from src.client.AlmaAPIClient import AlmaAPIClient
from src.domains.admin import Admin


class TSVGenerator:
    """
    Config-driven TSV generator for Alma data processing.
    
    This utility creates TSV files based on JSON configuration files,
    allowing for flexible column definitions and data sources.
    """
    
    def __init__(self, config_path: str):
        """
        Initialize TSV Generator with configuration.
        
        Args:
            config_path: Path to JSON configuration file
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.alma_client = None
        self.admin_client = None
        
    def _load_config(self) -> Dict[str, Any]:
        """Load and validate configuration from JSON file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Validate required sections
            required_sections = ['input', 'columns', 'output_settings']
            for section in required_sections:
                if section not in config:
                    raise ValueError(f"Missing required config section: {section}")
            
            # Validate input section
            input_config = config['input']
            if 'alma_set_id' not in input_config:
                raise ValueError("Missing 'alma_set_id' in input configuration")
            if 'environment' not in input_config:
                raise ValueError("Missing 'environment' in input configuration")
            
            # Validate columns
            if not config['columns'] or not isinstance(config['columns'], list):
                raise ValueError("'columns' must be a non-empty list")
            
            print(f"✓ Configuration loaded successfully from {self.config_path}")
            return config
            
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
    
    def _initialize_alma_clients(self, environment_override: str = None) -> None:
        """Initialize Alma API clients."""
        environment = environment_override or self.config['input']['environment']
        
        print(f"Initializing Alma API client for {environment} environment...")
        
        try:
            self.alma_client = AlmaAPIClient(environment)
            self.admin_client = Admin(self.alma_client)
            
            # Test connections
            if not self.alma_client.test_connection():
                raise RuntimeError("Failed to connect to Alma API")
            
            if not self.admin_client.test_connection():
                raise RuntimeError("Failed to connect to Alma Admin API")
            
            print(f"✓ Alma API clients initialized successfully")
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Alma clients: {e}")
    
    def _get_mms_ids(self, set_id_override: str = None) -> List[str]:
        """Get MMS IDs from the configured Alma set."""
        set_id = set_id_override or self.config['input']['alma_set_id']
        
        print(f"Retrieving MMS IDs from Alma set: {set_id}")
        
        try:
            mms_ids = self.admin_client.get_set_members(set_id)
            print(f"✓ Retrieved {len(mms_ids)} MMS IDs from set {set_id}")
            return mms_ids
            
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve MMS IDs from set {set_id}: {e}")
    
    def _generate_row_data(self, mms_id: str) -> List[str]:
        """
        Generate a single row of TSV data based on column configuration.
        
        Args:
            mms_id: The MMS ID for this row
            
        Returns:
            List of column values for this row
        """
        row_data = []
        
        for column in self.config['columns']:
            column_name = column.get('name', 'Unknown')
            source = column.get('source', '')
            default_value = column.get('default_value', '')
            
            if source == 'alma_set':
                # This column gets the MMS ID
                row_data.append(mms_id)
            else:
                # This column gets the default value
                row_data.append(default_value)
        
        return row_data
    
    def _create_output_directory(self) -> str:
        """Create output directory if it doesn't exist."""
        output_dir = self.config['output_settings'].get('output_directory', './output')
        
        # Convert to absolute path and create directory
        output_path = Path(output_dir).resolve()
        output_path.mkdir(parents=True, exist_ok=True)
        
        print(f"✓ Output directory ready: {output_path}")
        return str(output_path)
    
    def _generate_filename(self, set_id: str) -> str:
        """Generate output filename based on configuration."""
        prefix = self.config['output_settings'].get('file_prefix', 'alma_output')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        filename = f"{prefix}_{set_id}_{timestamp}.tsv"
        return filename
    
    def _write_tsv_file(self, mms_ids: List[str], output_path: str) -> str:
        """
        Write TSV file with the generated data.
        
        Args:
            mms_ids: List of MMS IDs to process
            output_path: Directory to save the file
            
        Returns:
            Full path to the created TSV file
        """
        set_id = self.config['input']['alma_set_id']
        filename = self._generate_filename(set_id)
        full_path = os.path.join(output_path, filename)
        
        include_headers = self.config['output_settings'].get('include_headers', False)
        
        print(f"Writing TSV file: {full_path}")
        print(f"Processing {len(mms_ids)} records...")
        
        try:
            with open(full_path, 'w', newline='', encoding='utf-8') as tsvfile:
                writer = csv.writer(tsvfile, delimiter='\t')
                
                # Write headers if configured
                if include_headers:
                    headers = [col.get('name', f'Column_{i}') for i, col in enumerate(self.config['columns'])]
                    writer.writerow(headers)
                    print(f"  ✓ Headers written: {headers}")
                
                # Write data rows
                for i, mms_id in enumerate(mms_ids, 1):
                    row_data = self._generate_row_data(mms_id)
                    writer.writerow(row_data)
                    
                    # Progress indicator for large sets
                    if i % 100 == 0:
                        print(f"  Processed {i}/{len(mms_ids)} records...")
                
            print(f"✓ TSV file created successfully: {full_path}")
            print(f"  Total records: {len(mms_ids)}")
            print(f"  Columns: {len(self.config['columns'])}")
            
            return full_path
            
        except Exception as e:
            raise RuntimeError(f"Failed to write TSV file: {e}")
    
    def _validate_tsv_file(self, file_path: str) -> None:
        """Validate the created TSV file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter='\t')
                rows = list(reader)
            
            if not rows:
                raise ValueError("TSV file is empty")
            
            # Check column count consistency
            expected_columns = len(self.config['columns'])
            include_headers = self.config['output_settings'].get('include_headers', False)
            
            start_row = 1 if include_headers else 0
            
            for i, row in enumerate(rows[start_row:], start_row + 1):
                if len(row) != expected_columns:
                    raise ValueError(f"Row {i} has {len(row)} columns, expected {expected_columns}")
            
            actual_data_rows = len(rows) - (1 if include_headers else 0)
            print(f"✓ TSV file validation passed")
            print(f"  Data rows: {actual_data_rows}")
            print(f"  Columns per row: {expected_columns}")
            
        except Exception as e:
            raise RuntimeError(f"TSV file validation failed: {e}")
    
    def generate_tsv(self, set_id_override: str = None, environment_override: str = None) -> str:
        """
        Generate TSV file based on configuration.
        
        Args:
            set_id_override: Optional override for the Alma set ID
            environment_override: Optional override for the environment
            
        Returns:
            Path to the created TSV file
        """
        print(f"\n=== TSV Generation Started ===")
        print(f"Config file: {self.config_path}")
        
        try:
            # Step 1: Initialize Alma clients
            self._initialize_alma_clients(environment_override)
            
            # Step 2: Get MMS IDs from Alma set
            mms_ids = self._get_mms_ids(set_id_override)
            
            if not mms_ids:
                raise RuntimeError("No MMS IDs retrieved from the set")
            
            # Step 3: Create output directory
            output_dir = self._create_output_directory()
            
            # Step 4: Generate and write TSV file
            tsv_path = self._write_tsv_file(mms_ids, output_dir)
            
            # Step 5: Validate the created file
            self._validate_tsv_file(tsv_path)
            
            print(f"\n=== TSV Generation Completed Successfully ===")
            print(f"Output file: {tsv_path}")
            
            return tsv_path
            
        except Exception as e:
            print(f"\n✗ TSV Generation Failed: {e}")
            raise
    
    def preview_config(self) -> None:
        """Print a preview of the current configuration."""
        print(f"\n=== Configuration Preview ===")
        print(f"Config file: {self.config_path}")
        print(f"Alma Set ID: {self.config['input']['alma_set_id']}")
        print(f"Environment: {self.config['input']['environment']}")
        print(f"Number of columns: {len(self.config['columns'])}")
        
        print(f"\nColumns:")
        for i, col in enumerate(self.config['columns'], 1):
            name = col.get('name', f'Column_{i}')
            source = col.get('source', 'default_value')
            default = col.get('default_value', '')
            if source == 'alma_set':
                print(f"  {i}. {name}: [MMS IDs from Alma set]")
            else:
                print(f"  {i}. {name}: '{default}'")
        
        output_settings = self.config['output_settings']
        print(f"\nOutput Settings:")
        print(f"  Directory: {output_settings.get('output_directory', './output')}")
        print(f"  File prefix: {output_settings.get('file_prefix', 'alma_output')}")
        print(f"  Include headers: {output_settings.get('include_headers', False)}")


# Convenience functions for easy usage
def create_tsv_from_config(config_path: str, set_id_override: str = None, 
                          environment_override: str = None) -> str:
    """
    Create TSV file from configuration file.
    
    Args:
        config_path: Path to JSON configuration file
        set_id_override: Optional override for Alma set ID
        environment_override: Optional override for environment
        
    Returns:
        Path to created TSV file
    """
    generator = TSVGenerator(config_path)
    return generator.generate_tsv(set_id_override, environment_override)


def preview_config(config_path: str) -> None:
    """
    Preview configuration without generating files.
    
    Args:
        config_path: Path to JSON configuration file
    """
    generator = TSVGenerator(config_path)
    generator.preview_config()


def create_sample_config(output_path: str = "alma_tsv_config.json") -> str:
    """
    Create a sample configuration file.
    
    Args:
        output_path: Where to save the sample config
        
    Returns:
        Path to created config file
    """
    sample_config = {
        "input": {
            "alma_set_id": "25793308630004146",
            "environment": "SANDBOX"
        },
        "columns": [
            {
                "name": "MMS_ID",
                "source": "alma_set"
            },
            {
                "name": "Library_Code",
                "default_value": "LGBTQ"
            },
            {
                "name": "Access_Rights_Code",
                "default_value": ""
            },
            {
                "name": "Access_Rights_Description",
                "default_value": ""
            }
        ],
        "output_settings": {
            "file_prefix": "alma_input",
            "include_headers": False,
            "output_directory": "./output"
        }
    }
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(sample_config, f, indent=2)
        
        print(f"✓ Sample configuration created: {output_path}")
        return output_path
        
    except Exception as e:
        raise RuntimeError(f"Failed to create sample config: {e}")


# Usage examples and testing
if __name__ == "__main__":
    """
    Example usage of the TSV Generator.
    """
    try:
        print("=== TSV Generator Test ===")
        
        # Create sample config if it doesn't exist
        config_file = "alma_tsv_config.json"
        if not os.path.exists(config_file):
            print("Creating sample configuration...")
            create_sample_config(config_file)
        
        # Preview configuration
        print("\nPreviewing configuration...")
        preview_config(config_file)
        
        # Ask user if they want to proceed
        proceed = input("\nGenerate TSV file with this configuration? (y/n): ").strip().lower()
        
        if proceed == 'y':
            # Generate TSV file
            try:
                tsv_path = create_tsv_from_config(config_file)
                print(f"\n✓ TSV file generated successfully!")
                print(f"File location: {tsv_path}")
                
                # Show first few lines of the file
                print(f"\nFirst 5 lines of the TSV file:")
                with open(tsv_path, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f):
                        if i >= 5:
                            break
                        print(f"  {i+1}: {line.rstrip()}")
                
            except Exception as e:
                print(f"✗ TSV generation failed: {e}")
        else:
            print("TSV generation cancelled.")
        
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure you have set the required environment variables:")
        print("export ALMA_SB_API_KEY='your_sandbox_api_key'")
        print("export ALMA_PROD_API_KEY='your_production_api_key'")