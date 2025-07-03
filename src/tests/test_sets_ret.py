from src.client.AlmaAPIClient import AlmaAPIClient
from src.domains.admin import Admin

# Initialize
client = AlmaAPIClient('SANDBOX')  # or 'PRODUCTION'
admin = Admin(client)

# Get all MMS IDs from a set
mms_ids = admin.get_set_members('34143075950004146')
print(f"Retrieved {len(mms_ids)} MMS IDs")