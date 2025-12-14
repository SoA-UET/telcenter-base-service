from pymongo import MongoClient
from pymongo.collection import Collection
from datetime import datetime
import os

class CustomersCollection:
    """
    Wrapper for the MongoDB 'customers' collection.
    
    Schema:
    {
        "_id": ObjectId,
        "email": String (unique),
        "password_hash": String,
        "full_name": String,
        "address": String,
        "created_at": Date,
        "status": String
    }
    """
    
    def __init__(self):
        mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017/telcenter_customer_identity")
        self.client = MongoClient(mongo_url)
        
        # Extract database name from URL
        db_name = mongo_url.split('/')[-1] or "telcenter_customer_identity"
        self.db = self.client[db_name]
        
        self.collection: Collection = self.db["customers"]
        
        # Create unique index on email
        self.collection.create_index("email", unique=True)
    
    def get_collection(self) -> Collection:
        """Get the MongoDB collection"""
        return self.collection
    
    def find_by_email(self, email: str):
        """Find a customer by email"""
        return self.collection.find_one({"email": email})
    
    def find_by_id(self, customer_id):
        """Find a customer by ID"""
        return self.collection.find_one({"_id": customer_id})
    
    def email_exists(self, email: str) -> bool:
        """Check if an email already exists"""
        return self.collection.count_documents({"email": email}) > 0
    
    def create_customer(self, email: str, password_hash: str, 
                       full_name: str, address: str, 
                       status: str = "ACTIVE"):
        """Create a new customer"""
        customer_doc = {
            "email": email,
            "password_hash": password_hash,
            "full_name": full_name,
            "address": address,
            "created_at": datetime.now(),
            "status": status
        }
        
        result = self.collection.insert_one(customer_doc)
        return {
            "_id": result.inserted_id,
            **customer_doc
        }
    
    def update_customer(self, customer_id, update_data: dict):
        """Update customer data"""
        return self.collection.update_one(
            {"_id": customer_id},
            {"$set": update_data}
        )
    
    def count_customers(self) -> int:
        """Count total number of customers"""
        return self.collection.count_documents({})
    
    def close(self):
        """Close the MongoDB connection"""
        self.client.close()
