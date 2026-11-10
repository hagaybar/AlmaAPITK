"""Per-operation hints that the catalog cannot derive from the source.

Keys per qualname:
- ``verbs``: HTTP verbs the method sends, when the source scan cannot tell.
  An empty list means the method makes no request.
- ``multi_write``: override the "writes more than once" flag.
- ``choices``: parameter name → allowed values (shown as a dropdown).
- ``incomplete_reason``: requests this method makes outside the client, which
  the lab cannot capture; its evidence is marked incomplete.
"""

HINTS: dict[str, dict] = {
    # Local helpers: they parse data the caller passes in and send nothing.
    "Acquisitions.extract_items_from_pol_data": {"verbs": []},
    "ResourceSharing.get_request_summary": {"verbs": []},
    "Users.get_user_expiry_date": {"verbs": []},
    "Users.parse_expiry_date": {"verbs": []},
    "Users.validate_email": {"verbs": []},
    "ResourceSharing.create_lending_request_from_citation": {
        "incomplete_reason": (
            "The PubMed / Crossref metadata lookup is made outside the Alma "
            "client and is not captured."
        ),
    },
}
