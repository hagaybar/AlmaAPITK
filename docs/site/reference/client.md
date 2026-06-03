# Client & Response

## AlmaAPIClient

The main HTTP client for the Alma REST API. Construct it for a given
environment, then hand it to a domain class.

::: almaapitk.client.AlmaAPIClient.AlmaAPIClient

## AlmaResponse

The wrapper returned by most calls. Use `.data` / `.json()` for the parsed
body and `.success` to check the outcome.

::: almaapitk.client.AlmaAPIClient.AlmaResponse
