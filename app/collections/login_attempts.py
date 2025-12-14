from pymongo.database import Database
from pymongo.collection import Collection

def get_login_attempts_collection(db: Database) -> Collection:
    """
    Get login attempts collection for tracking failed login attempts
    """
    collection = db["login_attempts"]
    
    # Create index on email for fast lookups
    collection.create_index("email")
    
    # Create TTL index to auto-expire records after 30 minutes
    collection.create_index("expires_at", expireAfterSeconds=0)
    
    return collection
