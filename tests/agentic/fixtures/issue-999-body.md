Domain: Users
Priority: medium
Effort: S

## API endpoints touched
- GET /almaws/v1/users/{user_id}

## Methods to add
```python
class Users:
    def get_user(self, user_id: str) -> AlmaResponse: ...
```

## Files to touch
- src/almaapitk/domains/users.py
- tests/unit/domains/test_users.py

## References
- https://developers.exlibrisgroup.com/alma/apis/users/

## Prerequisites
- Hard: #3 (persistent Session)
- Soft: #14 (logger)

## Acceptance criteria
- [ ] AC-1: get_user returns AlmaResponse with .success == True for a valid user_id
- [ ] AC-2: get_user raises AlmaValidationError when user_id is empty

## Notes for the implementing agent
- Mirror Acquisitions.get_invoice as the pattern source.
