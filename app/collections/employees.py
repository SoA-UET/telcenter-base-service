from pymongo.database import Database
from pymongo.collection import Collection

def get_employees_collection(db: Database) -> Collection:
    """
    Get employees collection with indexes
    """
    collection = db["employees"]
    
    # Create unique index on email
    collection.create_index("email", unique=True)
    
    return collection
