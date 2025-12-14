from pymongo.database import Database
from pymongo.collection import Collection

def get_keys_collection(db: Database) -> Collection:
    """
    Get keys collection for storing RSA key pairs for JWT signing
    """
    collection = db["keys"]
    
    # Create unique index on kid (key ID)
    collection.create_index("kid", unique=True)
    
    return collection
