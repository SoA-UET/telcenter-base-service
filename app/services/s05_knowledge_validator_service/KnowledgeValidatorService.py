import os
import json
import requests
from datetime import datetime
from typing import Optional, Dict, List
from pymongo import MongoClient
from pymongo.collection import Collection
from bson import ObjectId
from threading import Thread, Lock
from app.services.MessageQueueService import MessageQueueService
from app.utils.db import serialize_mongo_doc


class KnowledgeValidatorService:
    """
    S05 Knowledge Validator Service
    
    Handles validation of knowledge updates from partners and Core Portal.
    Emits validated knowledge to S03 via A08 API.
    """
    
    def __init__(self):
        # MongoDB setup
        mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017/")
        db_name = os.getenv("S05_DB_NAME", "telcenter_core_s05")
        
        self.mongo_client = MongoClient(mongo_url)
        self.db = self.mongo_client[db_name]
        self.validation_tasks: Collection = self.db["validation_tasks"]
        
        # Create indexes
        self.validation_tasks.create_index("status")
        self.validation_tasks.create_index("partner_id")
        self.validation_tasks.create_index("created_at")
        
        # RabbitMQ setup for A08 (sending to S03)
        self.mq_service = MessageQueueService()
        self.knowledge_store_event_queue = os.getenv(
            "KNOWLEDGE_STORE_EVENT_QUEUE",
            "knowledge_store_events"
        )
        self.mq_service.declare_queue(self.knowledge_store_event_queue)
        
        # SeaweedFS configuration
        self.seaweedfs_url = os.getenv("SEAWEEDFS_URL", "http://localhost:8080")
        
        # Lock for thread-safe operations
        self.lock = Lock()
        
        print(f"[S05 KnowledgeValidatorService] Initialized")
        print(f"[S05 KnowledgeValidatorService] MongoDB: {mongo_url}/{db_name}")
        print(f"[S05 KnowledgeValidatorService] A08 Event Queue: {self.knowledge_store_event_queue}")
    
    def create_validation_task(
        self, 
        seaweed_file_id: str,
        partner_id: Optional[str] = None,
        validator_id: Optional[str] = None
    ) -> str:
        """
        Create a new validation task
        
        Args:
            seaweed_file_id: ID of the JSON file in SeaweedFS
            partner_id: ID of the partner who submitted the update
            validator_id: ID of the validator (if known)
        
        Returns:
            Task ID as string
        """
        with self.lock:
            task = {
                "seaweed_file_id": seaweed_file_id,
                "partner_id": partner_id,
                "status": "pending",
                "validator_id": validator_id,
                "created_at": datetime.utcnow(),
                "validated_at": None
            }
            
            result = self.validation_tasks.insert_one(task)
            task_id = str(result.inserted_id)
            
            print(f"[S05] Created validation task: {task_id}")
            return task_id
    
    def get_validation_tasks(
        self,
        status: Optional[str] = None,
        partner_id: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> Dict:
        """
        Get list of validation tasks with pagination
        
        Args:
            status: Filter by status (pending/approved/rejected)
            partner_id: Filter by partner_id
            page: Page number (1-indexed)
            limit: Items per page
        
        Returns:
            Dict with tasks, pagination info, and summary
        """
        # Build query filter
        query_filter = {}
        if status:
            query_filter["status"] = status
        if partner_id:
            query_filter["partner_id"] = partner_id
        
        # Get total count
        total_count = self.validation_tasks.count_documents(query_filter)
        
        # Get summary statistics
        summary = {
            "total": self.validation_tasks.count_documents({}),
            "pending": self.validation_tasks.count_documents({"status": "pending"}),
            "approved": self.validation_tasks.count_documents({"status": "approved"}),
            "rejected": self.validation_tasks.count_documents({"status": "rejected"})
        }
        
        # Calculate pagination
        skip = (page - 1) * limit
        total_pages = (total_count + limit - 1) // limit
        
        # Get tasks
        cursor = self.validation_tasks.find(query_filter).sort("created_at", -1).skip(skip).limit(limit)
        tasks = [serialize_mongo_doc(task) for task in cursor]
        
        # Convert status to match H22 spec format
        for task in tasks:
            if task.get("status") == "approved":
                task["status"] = "approved"
            elif task.get("status") == "rejected":
                task["status"] = "rejected"
            else:
                task["status"] = "pending"
        
        return {
            "status": "success",
            "total_count": total_count,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "updates": tasks,
            "summary": summary
        }
    
    def get_validation_task_by_id(self, task_id: str) -> Optional[Dict]:
        """
        Get a single validation task by ID and load its content from SeaweedFS
        
        Args:
            task_id: Task ID
        
        Returns:
            Task dict with knowledge content, or None if not found
        """
        try:
            obj_id = ObjectId(task_id)
        except:
            return None
        
        task = self.validation_tasks.find_one({"_id": obj_id})
        if not task:
            return None
        
        # Serialize the task
        task_dict = serialize_mongo_doc(task)
        
        # Fetch content from SeaweedFS
        seaweed_file_id = task.get("seaweed_file_id")
        if seaweed_file_id:
            content = self._fetch_from_seaweedfs(seaweed_file_id)
            if content:
                task_dict["faqs"] = content.get("faqs", [])
                task_dict["packages"] = content.get("packages", [])
        
        return task_dict
    
    def approve_validation_task(self, task_id: str, validator_id: str) -> Optional[Dict]:
        """
        Approve a validation task and send to S03 via A08
        
        Args:
            task_id: Task ID to approve
            validator_id: ID of the validator approving this task
        
        Returns:
            Updated task dict, or None if failed
        """
        try:
            obj_id = ObjectId(task_id)
        except:
            return None
        
        # Get the task
        task = self.validation_tasks.find_one({"_id": obj_id})
        if not task:
            return None
        
        # Check if already processed
        if task.get("status") != "pending":
            return None
        
        # Update status to approved
        with self.lock:
            update_result = self.validation_tasks.update_one(
                {"_id": obj_id, "status": "pending"},
                {
                    "$set": {
                        "status": "approved",
                        "validator_id": validator_id,
                        "validated_at": datetime.utcnow()
                    }
                }
            )
            
            if update_result.modified_count == 0:
                return None
        
        # Send to S03 via A08 in a separate thread
        seaweed_file_id = task.get("seaweed_file_id")
        partner_id = task.get("partner_id")
        
        def send_to_s03():
            try:
                # Emit A08 event
                event = {
                    "event": "store_validated_knowledge",
                    "data": {
                        "partner_id": partner_id,
                        "seaweed_file_id": seaweed_file_id,
                        "validated_at": datetime.utcnow().isoformat()
                    }
                }
                
                self.mq_service.publish_message(
                    self.knowledge_store_event_queue,
                    event
                )
                
                print(f"[S05] Sent A08 event to S03 for task {task_id}")
            except Exception as e:
                print(f"[S05] Error sending to S03: {e}")
        
        # Start thread to send to S03
        thread = Thread(target=send_to_s03)
        thread.daemon = True
        thread.start()
        
        # Get updated task
        updated_task = self.validation_tasks.find_one({"_id": obj_id})
        return serialize_mongo_doc(updated_task)
    
    def reject_validation_task(self, task_id: str, validator_id: str) -> Optional[Dict]:
        """
        Reject a validation task
        
        Args:
            task_id: Task ID to reject
            validator_id: ID of the validator rejecting this task
        
        Returns:
            Updated task dict, or None if failed
        """
        try:
            obj_id = ObjectId(task_id)
        except:
            return None
        
        # Get the task
        task = self.validation_tasks.find_one({"_id": obj_id})
        if not task:
            return None
        
        # Check if already processed
        if task.get("status") != "pending":
            return None
        
        # Update status to rejected
        with self.lock:
            update_result = self.validation_tasks.update_one(
                {"_id": obj_id, "status": "pending"},
                {
                    "$set": {
                        "status": "rejected",
                        "validator_id": validator_id,
                        "validated_at": datetime.utcnow()
                    }
                }
            )
            
            if update_result.modified_count == 0:
                return None
        
        print(f"[S05] Rejected validation task {task_id}")
        
        # Get updated task
        updated_task = self.validation_tasks.find_one({"_id": obj_id})
        return serialize_mongo_doc(updated_task)
    
    def _fetch_from_seaweedfs(self, file_id: str) -> Optional[Dict]:
        """
        Fetch JSON content from SeaweedFS
        
        Args:
            file_id: SeaweedFS file ID
        
        Returns:
            Parsed JSON content, or None if failed
        """
        try:
            url = f"{self.seaweedfs_url}/{file_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"[S05] Failed to fetch from SeaweedFS: {response.status_code}")
                return None
        except Exception as e:
            print(f"[S05] Error fetching from SeaweedFS: {e}")
            return None
    
    def close(self):
        """Clean up resources"""
        if self.mq_service:
            self.mq_service.connection.close()
        if self.mongo_client:
            self.mongo_client.close()
        print("[S05 KnowledgeValidatorService] Closed")
