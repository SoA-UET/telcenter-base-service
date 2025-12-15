"""
Database utilities for S11 Local Knowledge Service
Uses MongoDB for storing packages and FAQs
"""
from pymongo import MongoClient, ASCENDING
from typing import Optional, List, Dict, Any
import os


class MongoDBClient:
    """MongoDB client for S11 service"""
    
    def __init__(self, connection_string: Optional[str] = None, database_name: Optional[str] = None):
        if not connection_string:
            connection_string = os.getenv("MONGODB_CONNECTION_STRING", "mongodb://localhost:27017/")
        if not database_name:
            database_name = os.getenv("S11_DATABASE_NAME", "telcenter_partner_knowledge")
        
        self.client = MongoClient(connection_string)
        self.db = self.client[database_name]
        self.packages = self.db["packages"]
        self.faqs = self.db["faqs"]
        
        # Create indexes
        self._create_indexes()
    
    def _create_indexes(self):
        """Create necessary indexes for performance"""
        # Index on code for packages
        self.packages.create_index([("code", ASCENDING)])
        self.packages.create_index([("partner_id", ASCENDING)])
        
        # Index for FAQs
        self.faqs.create_index([("partner_id", ASCENDING)])
        self.faqs.create_index([("category", ASCENDING)])
    
    def get_next_package_id(self) -> int:
        """Get next available ID for package"""
        result = self.packages.find_one(sort=[("id", -1)])
        if result:
            return result["id"] + 1
        return 1
    
    def get_next_faq_id(self) -> int:
        """Get next available ID for FAQ"""
        result = self.faqs.find_one(sort=[("id", -1)])
        if result:
            return result["id"] + 1
        return 1
    
    def close(self):
        """Close database connection"""
        self.client.close()
