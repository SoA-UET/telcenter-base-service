from pymongo.database import Database
from pymongo.collection import Collection

def get_roles_collection(db: Database) -> Collection:
    """
    Get roles collection with indexes
    """
    collection = db["roles"]
    
    # Create unique index on name
    collection.create_index("name", unique=True)
    
    return collection
