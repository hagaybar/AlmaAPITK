import os
from typing import Optional, Dict

class ConfigManager:
    """
    ConfigManager handles the configuration settings and environment variables
    needed for the ETL process in Alma Digital.
    """
    
    REQUIRED_ENV_VARS = [
        'ALMA_SB_API_KEY',
        'ALMA_PROD_API_KEY',
        'AWS_ACCESS_KEY',
        'AWS_SECRET',
        'ALMA_SB_BUCKET_NAME',
        'ALMA_PROD_BUCKET_NAME'
    ]
    
    def __init__(self, env: Optional[Dict[str, str]] = None) -> None:
        self.env = env or os.environ
        self.current_environment: Optional[str] = None
        self.api_key_sb: Optional[str] = None
        self.api_key_prod: Optional[str] = None
        self.aws_access_key: Optional[str] = None
        self.aws_secret_key: Optional[str] = None
        self.sb_bucket_name: Optional[str] = None
        self.prod_bucket_name: Optional[str] = None
        self.inst_code: str = "972TAU_INST"
        self.base_url: str = 'https://api-eu.hosted.exlibrisgroup.com'
        self.headers: Optional[Dict[str, str]] = None
        self.load_env_variables()

    def load_env_variables(self) -> None:
        """
        Load environment variables for Alma API keys and AWS credentials.
        Raise an error if any required environment variable is missing.
        """
        missing_vars = [var for var in self.REQUIRED_ENV_VARS if var not in self.env]
        if missing_vars:
            raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_vars)}")

        self.api_key_sb = self.env.get('ALMA_SB_API_KEY')
        self.api_key_prod = self.env.get('ALMA_PROD_API_KEY')
        self.aws_access_key = self.env.get('AWS_ACCESS_KEY')
        self.aws_secret_key = self.env.get('AWS_SECRET')
        self.sb_bucket_name = self.env.get('ALMA_SB_BUCKET_NAME')
        self.prod_bucket_name = self.env.get('ALMA_PROD_BUCKET_NAME')
        if self.current_environment:
            self.set_headers(self.current_environment)

    def set_environment(self, environment: str) -> None:
        """
        Set the current environment and update headers accordingly.

        Args:
            environment (str): The current environment ('SB' or 'PROD').
        """
        self.current_environment = environment.upper()
        self.set_headers(self.current_environment)
    
    def set_headers(self, environment: str) -> None:
        """
        Set headers based on the current environment.

        Args:
            environment (str): The current environment ('SB' or 'PROD').
        """
        if environment == 'SB':
            self.headers = {
                'authorization': f"apikey {self.api_key_sb}",
                'accept': 'application/json',
                'content-type': 'application/json; charset=utf-8'
            }
        elif environment == 'PROD':
            self.headers = {
                'authorization': f"apikey {self.api_key_prod}",
                'accept': 'application/json',
                'content-type': 'application/json; charset=utf-8'
            }
        else:
            raise ValueError(f"Invalid environment: {environment}")
        
    def get_api_key_sb(self) -> Optional[str]:
        """
        Get the Sandbox API key.

        Returns:
            Optional[str]: Sandbox API key or None if not set.
        """
        return self.api_key_sb

    def get_api_key_prod(self) -> Optional[str]:
        """
        Get the Production API key.

        Returns:
            Optional[str]: Production API key or None if not set.
        """
        return self.api_key_prod

    def get_api_key(self) -> Optional[str]:
        """
        Get the API key for the current environment.

        Returns:
            Optional[str]: API key or None if not set.
        """
        if self.current_environment == 'SB':
            return self.api_key_sb
        elif self.current_environment == 'PROD':
            return self.api_key_prod
        return None

    def get_aws_access_key(self) -> Optional[str]:
        """
        Get the AWS access key.

        Returns:
            Optional[str]: AWS access key or None if not set.
        """
        return self.aws_access_key

    def get_aws_secret_key(self) -> Optional[str]:
        """
        Get the AWS secret key.

        Returns:
            Optional[str]: AWS secret key or None if not set.
        """
        return self.aws_secret_key

    def get_sb_bucket_name(self) -> Optional[str]:
        """
        Get the Sandbox bucket name.

        Returns:
            Optional[str]: Sandbox bucket name or None if not set.
        """
        return self.sb_bucket_name

    def get_prod_bucket_name(self) -> Optional[str]:
        """
        Get the Production bucket name.

        Returns:
            Optional[str]: Production bucket name or None if not set.
        """
        return self.prod_bucket_name

    def get_inst_code(self) -> str:
        """
        Get the institution code.

        Returns:
            str: Institution code.
        """
        return self.inst_code

    def get_base_url(self) -> str:
        """
        Get the base URL for Alma API.

        Returns:
            str: Base URL for Alma API.
        """
        return self.base_url

    def get_headers(self) -> Optional[Dict[str, str]]:
        """
        Get the headers for API requests.

        Returns:
            Optional[Dict[str, str]]: Headers for API requests or None if not set.
        """
        return self.headers
    
    def get_bucket_name(self) -> Optional[str]:
        """
        Get the bucket name for the current environment.

        Returns:
            Optional[str]: Bucket name or None if not set.
        """
        if self.current_environment == 'SB':
            return self.sb_bucket_name
        elif self.current_environment == 'PROD':
            return self.prod_bucket_name
        return None
    
    def show_config(self) -> None:
        """
        Print the configuration settings for the ETL process in Alma Digital.

        This function prints the following configuration details:
        - Sandbox API key
        - Production API key
        - AWS access key
        - AWS secret key
        - Institution code
        - AWS S3 Sandbox bucket name
        - AWS S3 Production bucket name
        - Base URL for Alma API
        - Headers for API requests

        Parameters:
        None

        Returns:
        None
        """
        print(f"Sandbox API key: {self.get_api_key_sb()}")
        print(f"Production API key: {self.get_api_key_prod()}")
        print(f"AWS access key: {self.get_aws_access_key()}")
        print(f"AWS secret key: {self.get_aws_secret_key()}")
        print(f"Institution code: {self.get_inst_code()}")
        print(f"AWS S3 SB bucket name: {self.get_sb_bucket_name()}")
        print(f"AWS S3 PROD bucket name: {self.get_prod_bucket_name()}")
        print(f"Base URL for Alma API: {self.get_base_url()}")
        print(f"Current API key: {self.get_api_key()}")
        print(f"Current bucket name: {self.get_bucket_name()}")
        print(f"Headers for API requests: {self.get_headers()}")


if __name__ == "__main__":
    def main():
        print("================================================")
        my_config = ConfigManager()
        my_config.show_config()
        my_config.set_environment('PROD')
        my_config.show_config()


    main()