# Exceptions

All exceptions are importable from the top-level `almaapitk` package. Catch the
base `AlmaAPIError` to handle any API failure, or a specific subclass for
targeted handling. `AlmaValidationError` (and its subclass `CredentialError`)
derive from `ValueError`.

::: almaapitk.client.AlmaAPIClient.AlmaAPIError

::: almaapitk.client.AlmaAPIClient.AlmaValidationError

::: almaapitk.client.AlmaAPIClient.AlmaAuthenticationError

::: almaapitk.client.AlmaAPIClient.AlmaRateLimitError

::: almaapitk.client.AlmaAPIClient.AlmaServerError

::: almaapitk.client.AlmaAPIClient.AlmaResourceNotFoundError

::: almaapitk.client.AlmaAPIClient.AlmaDuplicateInvoiceError

::: almaapitk.client.AlmaAPIClient.AlmaInvalidPolModeError

::: almaapitk.client.AlmaAPIClient.CredentialError
