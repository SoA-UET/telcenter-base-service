"""
S11 Local Knowledge Service - Main service class
Handles CRUD operations for packages/FAQs, snapshot generation, and file import coordination
"""
import os
import json
import tempfile
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
from threading import Thread, Lock
from .database import MongoDBClient
from .models import Package, FAQ
from ..MessageQueueService import MessageQueueService


class LocalKnowledgeService:
    """
    S11 Partner Local Knowledge Service
    Manages local telecom knowledge (packages and FAQs) for a partner
    """
    
    def __init__(self):
        # Database
        self.db = MongoDBClient()
        
        # Partner ID from environment
        self.partner_id = int(os.getenv("PARTNER_ID", "1"))
        
        # SeaweedFS configuration
        self.seaweed_master_url = os.getenv("SEAWEED_MASTER_URL", "http://localhost:9333")
        self.seaweed_public_url = os.getenv("SEAWEED_PUBLIC_URL", self.seaweed_master_url)
        
        # RabbitMQ for A32 (to S15) and A33 (from S12)
        self.mq_service = MessageQueueService()
        
        # A32 queue names (to S15 File Importing AI Agent)
        self.file_import_request_queue = os.getenv("FILE_IMPORT_REQUEST_QUEUE", "file_import_requests")
        self.file_import_response_queue = os.getenv("FILE_IMPORT_RESPONSE_QUEUE", "file_import_responses")
        
        # A33 queue names (from S12 Partner Knowledge Update Service)
        self.snapshot_requests_queue = os.getenv("SNAPSHOT_REQUESTS_QUEUE_NAME", "snapshot_requests")
        self.snapshot_responses_queue = os.getenv("SNAPSHOT_RESPONSES_QUEUE_NAME", "snapshot_responses")
        
        # Declare queues
        self.mq_service.declare_queue(self.file_import_request_queue)
        self.mq_service.declare_queue(self.file_import_response_queue)
        self.mq_service.declare_queue(self.snapshot_requests_queue)
        self.mq_service.declare_queue(self.snapshot_responses_queue)
        
        # Lock for thread safety
        self.lock = Lock()
        
        # Pending file import requests (for tracking responses)
        self.pending_imports: Dict[str, Dict] = {}
    
    # ========== Package CRUD Operations ==========
    
    def list_packages(self, filters: Optional[Dict] = None) -> List[Dict]:
        """List packages with optional filtering and pagination"""
        query = {"partner_id": self.partner_id}
        
        if filters:
            # Add any additional filters
            if "code" in filters:
                query["code"] = filters["code"]
        
        # Pagination
        page = filters.get("page", 1) if filters else 1
        limit = filters.get("limit", 10) if filters else 10
        skip = (page - 1) * limit
        
        cursor = self.db.packages.find(query).skip(skip).limit(limit)
        
        packages = []
        for doc in cursor:
            pkg = Package.from_dict(doc)
            packages.append(pkg.to_dict())
        
        return packages
    
    def create_package(self, data: Dict) -> Dict:
        """Create a new package"""
        # Check for duplicate code
        existing = self.db.packages.find_one({
            "partner_id": self.partner_id,
            "code": data.get("code")
        })
        
        if existing:
            raise ValueError(f"Duplicate package code: {data.get('code')}")
        
        # Create package
        pkg = Package(
            partner_id=self.partner_id,
            code=data.get("code"),
            meta_data=data
        )
        
        pkg.id = self.db.get_next_package_id()
        
        # Insert into database
        self.db.packages.insert_one(pkg.to_dict())
        
        return {"id": pkg.id, "message": "Package created successfully"}
    
    def update_package(self, data: Dict) -> Dict:
        """Update an existing package"""
        if "id" not in data:
            raise ValueError("Missing required field: id")
        
        pkg_id = data.get("id")
        
        # Find existing package
        existing = self.db.packages.find_one({
            "id": pkg_id,
            "partner_id": self.partner_id
        })
        
        if not existing:
            raise ValueError(f"Package not found: {pkg_id}")
        
        # Update fields
        update_data = {}
        if "code" in data:
            # Check for duplicate code
            duplicate = self.db.packages.find_one({
                "partner_id": self.partner_id,
                "code": data["code"],
                "id": {"$ne": pkg_id}
            })
            if duplicate:
                raise ValueError(f"Duplicate package code: {data['code']}")
            update_data["code"] = data["code"]
        
        # Update meta_data
        meta_data = Package.from_dict(existing).meta_data
        for key in data:
            if key not in ["id", "partner_id", "code"]:
                meta_data[key] = data[key]
        
        update_data["meta_data"] = json.dumps(meta_data, ensure_ascii=False)
        
        # Perform update
        self.db.packages.update_one(
            {"id": pkg_id, "partner_id": self.partner_id},
            {"$set": update_data}
        )
        
        return {"id": pkg_id, "message": "Package updated successfully"}
    
    def delete_package(self, data: Dict) -> Dict:
        """Delete a package"""
        if "id" not in data:
            raise ValueError("Missing required field: id")
        
        pkg_id = data.get("id")
        
        # Delete package
        result = self.db.packages.delete_one({
            "id": pkg_id,
            "partner_id": self.partner_id
        })
        
        if result.deleted_count == 0:
            raise ValueError(f"Package not found: {pkg_id}")
        
        return {"id": pkg_id, "message": "Package deleted successfully"}
    
    # ========== FAQ CRUD Operations ==========
    
    def list_faqs(self, filters: Optional[Dict] = None) -> List[Dict]:
        """List FAQs with optional filtering and pagination"""
        query = {"partner_id": self.partner_id}
        
        if filters:
            # Add any additional filters
            if "category" in filters:
                query["category"] = filters["category"]
        
        # Pagination
        page = filters.get("page", 1) if filters else 1
        limit = filters.get("limit", 10) if filters else 10
        skip = (page - 1) * limit
        
        cursor = self.db.faqs.find(query).skip(skip).limit(limit)
        
        faqs = []
        for doc in cursor:
            faq = FAQ.from_dict(doc)
            faqs.append(faq.to_dict())
        
        return faqs
    
    def create_faq(self, data: Dict) -> Dict:
        """Create a new FAQ"""
        # Check for duplicate question
        existing = self.db.faqs.find_one({
            "partner_id": self.partner_id,
            "question": data.get("question")
        })
        
        if existing:
            raise ValueError("Duplicate FAQ question")
        
        # Create FAQ
        faq = FAQ(
            partner_id=self.partner_id,
            question=data.get("question"),
            answer=data.get("answer"),
            category=data.get("category")
        )
        
        faq.id = self.db.get_next_faq_id()
        
        # Insert into database
        self.db.faqs.insert_one(faq.to_dict())
        
        return {"id": faq.id, "message": "FAQ created successfully"}
    
    def update_faq(self, data: Dict) -> Dict:
        """Update an existing FAQ"""
        if "id" not in data:
            raise ValueError("Missing required field: id")
        
        faq_id = data.get("id")
        
        # Find existing FAQ
        existing = self.db.faqs.find_one({
            "id": faq_id,
            "partner_id": self.partner_id
        })
        
        if not existing:
            raise ValueError(f"FAQ not found: {faq_id}")
        
        # Update fields
        update_data = {}
        
        if "question" in data:
            # Check for duplicate question
            duplicate = self.db.faqs.find_one({
                "partner_id": self.partner_id,
                "question": data["question"],
                "id": {"$ne": faq_id}
            })
            if duplicate:
                raise ValueError("Duplicate FAQ question")
            update_data["question"] = data["question"]
        
        if "answer" in data:
            update_data["answer"] = data["answer"]
        
        if "category" in data:
            update_data["category"] = data["category"]
        
        # Perform update
        self.db.faqs.update_one(
            {"id": faq_id, "partner_id": self.partner_id},
            {"$set": update_data}
        )
        
        return {"id": faq_id, "message": "FAQ updated successfully"}
    
    def delete_faq(self, data: Dict) -> Dict:
        """Delete a FAQ"""
        if "id" not in data:
            raise ValueError("Missing required field: id")
        
        faq_id = data.get("id")
        
        # Delete FAQ
        result = self.db.faqs.delete_one({
            "id": faq_id,
            "partner_id": self.partner_id
        })
        
        if result.deleted_count == 0:
            raise ValueError(f"FAQ not found: {faq_id}")
        
        return {"id": faq_id, "message": "FAQ deleted successfully"}
    
    # ========== File Import Operations (A32 to S15) ==========
    
    def upload_file_to_seaweed(self, file_content: bytes, filename: str) -> str:
        """
        Upload a file to SeaweedFS and return the file_id
        """
        # Get file assignment
        assign_url = f"{self.seaweed_master_url}/dir/assign"
        response = requests.get(assign_url)
        response.raise_for_status()
        
        assign_data = response.json()
        fid = assign_data["fid"]
        upload_url = f"http://{assign_data['url']}/{fid}"
        
        # Upload file
        files = {"file": (filename, file_content)}
        upload_response = requests.post(upload_url, files=files)
        upload_response.raise_for_status()
        
        return fid
    
    def download_file_from_seaweed(self, file_id: str) -> bytes:
        """
        Download a file from SeaweedFS using file_id
        """
        download_url = f"{self.seaweed_public_url}/{file_id}"
        response = requests.get(download_url)
        response.raise_for_status()
        return response.content
    
    def import_file(self, file_content: bytes, filename: str, metadata: Optional[Dict] = None) -> Dict:
        """
        Handle file import: Upload to SeaweedFS, then send to S15 for processing via A32
        Returns import_id and seaweed_file_id
        """
        # Upload file to SeaweedFS
        try:
            seaweed_file_id = self.upload_file_to_seaweed(file_content, filename)
        except Exception as e:
            raise ValueError(f"Failed to upload file to storage: {str(e)}")
        
        # Generate import ID
        import_id = f"import_{self.partner_id}_{int(datetime.now().timestamp() * 1000)}"
        
        # Send request to S15 via A32
        request_message = {
            "method": "import_file",
            "params": {
                "seaweed_file_id": seaweed_file_id,
            },
            "id": import_id
        }
        
        # Store pending import request
        with self.lock:
            self.pending_imports[import_id] = {
                "seaweed_file_id": seaweed_file_id,
                "filename": filename,
                "metadata": metadata or {},
                "status": "pending",
                "created_at": datetime.now().isoformat()
            }
        
        # Publish to S15
        self.mq_service.publish_message(self.file_import_request_queue, request_message)
        
        return {
            "import_id": import_id,
            "seaweed_file_id": seaweed_file_id
        }
    
    def handle_file_import_response(self, response: Dict):
        """
        Handle A32 response from S15 (file import result)
        This is called by the RabbitMQ consumer thread
        """
        import_id = response.get("id")
        result = response.get("result", {})
        
        with self.lock:
            if import_id in self.pending_imports:
                self.pending_imports[import_id]["status"] = result.get("status", "error")
                self.pending_imports[import_id]["result"] = result
                self.pending_imports[import_id]["completed_at"] = datetime.now().isoformat()
                
                # TODO: If successful, process the extracted packages
                # For now, we just store the result
                print(f"[S11] File import {import_id} completed with status: {result.get('status')}")
    
    # ========== Snapshot Operations (A33 from S12) ==========
    
    def generate_snapshot(self) -> str:
        """
        Generate a snapshot of current packages and FAQs
        Returns SeaweedFS file_id of the JSON snapshot
        """
        # Get all packages
        packages = list(self.db.packages.find({"partner_id": self.partner_id}))
        
        # Get all FAQs
        faqs = list(self.db.faqs.find({"partner_id": self.partner_id}))
        
        # Convert ObjectId to string for JSON serialization
        for pkg in packages:
            pkg["_id"] = str(pkg["_id"])
        
        for faq in faqs:
            faq["_id"] = str(faq["_id"])
        
        # Create snapshot data
        snapshot_data = {
            "partner_id": self.partner_id,
            "timestamp": datetime.now().isoformat(),
            "packages": packages,
            "faqs": faqs
        }
        
        # Convert to JSON
        snapshot_json = json.dumps(snapshot_data, ensure_ascii=False, indent=2)
        snapshot_bytes = snapshot_json.encode("utf-8")
        
        # Upload to SeaweedFS
        filename = f"snapshot_partner_{self.partner_id}_{int(datetime.now().timestamp())}.json"
        seaweed_file_id = self.upload_file_to_seaweed(snapshot_bytes, filename)
        
        return seaweed_file_id
    
    def handle_snapshot_request(self, request: Dict):
        """
        Handle A33 snapshot request from S12
        This is called by the RabbitMQ consumer thread
        """
        request_id = request.get("id")
        
        try:
            # Generate snapshot
            seaweed_file_id = self.generate_snapshot()
            
            # Prepare response
            response = {
                "id": request_id,
                "result": {
                    "status": "success",
                    "content": {
                        "seaweed_file_id": seaweed_file_id
                    }
                }
            }
        except Exception as e:
            # Error response
            response = {
                "id": request_id,
                "result": {
                    "status": "error",
                    "content": str(e)
                }
            }
        
        # Send response back to S12
        self.mq_service.publish_message(self.snapshot_responses_queue, response)
    
    # ========== RabbitMQ Listeners ==========
    
    def start_mq_listeners(self):
        """
        Start RabbitMQ listeners in separate threads
        """
        # A32 response listener (from S15)
        def a32_response_listener():
            mq = self.mq_service.clone()
            mq.register_callback(self.file_import_response_queue, self.handle_file_import_response)
            mq.start_consuming()
        
        # A33 request listener (from S12)
        def a33_request_listener():
            mq = self.mq_service.clone()
            mq.register_callback(self.snapshot_requests_queue, self.handle_snapshot_request)
            mq.start_consuming()
        
        # Start threads
        Thread(target=a32_response_listener, daemon=True).start()
        Thread(target=a33_request_listener, daemon=True).start()
        
        print("[S11] RabbitMQ listeners started for A32 and A33")
