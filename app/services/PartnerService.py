from .common.BaseCRUDService import BaseCRUDService
from ..utils.db import str_to_objectid, serialize_mongo_doc
from pymongo.collection import Collection
from flask_restx import abort
from datetime import datetime
import secrets
import os
import threading


class PartnerService(BaseCRUDService):
    """
    Service for managing Partner connections.
    Handles CRUD operations and publishes events to A09b queue.
    """
    
    def __init__(self, collection: Collection, mq_service=None):
        super().__init__(collection, enable_timing=True)
        self.mq_service = mq_service
        self.mq_lock = threading.Lock()
        self.a09b_events_queue = os.getenv('A09B_EVENTS_QUEUE', 'telcenter_a09b_events')
    
    def set_mq_service(self, mq_service):
        """Set the MessageQueueService for publishing events."""
        self.mq_service = mq_service
    
    def _generate_api_key(self) -> str:
        """Generate a secure API key for partner authentication."""
        return secrets.token_urlsafe(32)
    
    def _publish_event(self, event: str, params: dict):
        """Publish an event to A09b queue (S07 -> S16)."""
        if self.mq_service is None:
            return
        
        message = {
            "event": event,
            "params": params
        }
        
        try:
            with self.mq_lock:
                mq = self.mq_service.clone()
            mq.declare_queue(self.a09b_events_queue)
            mq.publish_message(self.a09b_events_queue, message)
        except Exception as e:
            print(f"[PartnerService] Failed to publish event {event}: {e}")
    
    def get_all_partners(self):
        """
        Get all partners (for RabbitMQ APIs: A07, A09a, A37).
        Returns list of all partners without pagination.
        """
        partners = list(self.collection.find({}))
        return [serialize_mongo_doc(p) for p in partners]
    
    def get_partners_with_names(self):
        """
        Get partners with partner_id and name for A07 and A37 APIs.
        """
        partners = self.get_all_partners()
        return [
            {"partner_id": p["id"], "name": p["name"]}
            for p in partners
        ]
    
    def get_partners_with_base_urls(self):
        """
        Get partners with partner_id and base_url for A09a API.
        """
        partners = self.get_all_partners()
        return [
            {"partner_id": p["id"], "base_url": p["base_url"]}
            for p in partners
        ]
    
    def create_partner(self, data: dict):
        """
        Create a new partner connection (H24 POST).
        Generates API key and publishes partner_create event.
        """
        name = data.get("name")
        base_url = data.get("base_url")
        
        if not name or not base_url:
            abort(400, "Name and base_url are required")
        
        # Check if partner with same name or URL already exists
        existing = self.collection.find_one({
            "$or": [
                {"name": name},
                {"base_url": base_url}
            ]
        })
        
        if existing:
            abort(400, "Partner already exists")
        
        # Generate API key
        api_key = self._generate_api_key()
        
        # Create partner document
        partner_doc = {
            "name": name,
            "base_url": base_url,
            "api_key": api_key,
        }
        
        # Insert into database
        result = self.post_item(partner_doc)
        serialized = serialize_mongo_doc(result)
        
        # Publish partner_create event (A09b)
        self._publish_event("partner_create", {
            "partner_id": serialized["id"],
            "name": serialized["name"],
            "api_key": serialized["api_key"],
            "base_url": serialized["base_url"]
        })
        
        return serialized
    
    def update_partner(self, partner_id: str, data: dict):
        """
        Update an existing partner connection (H24 PATCH).
        Publishes partner_update event.
        """
        # Build update document with only provided fields
        update_doc = {}
        if "name" in data and data["name"]:
            update_doc["name"] = data["name"]
        if "base_url" in data and data["base_url"]:
            update_doc["base_url"] = data["base_url"]
        if "api_key" in data and data["api_key"]:
            update_doc["api_key"] = data["api_key"]
        
        if not update_doc:
            # No fields to update, just return current partner
            return serialize_mongo_doc(self.get_item_by_id(partner_id))
        
        # Check for duplicate name or URL (excluding current partner)
        object_id = str_to_objectid(partner_id)
        if "name" in update_doc or "base_url" in update_doc:
            conditions = []
            if "name" in update_doc:
                conditions.append({"name": update_doc["name"]})
            if "base_url" in update_doc:
                conditions.append({"base_url": update_doc["base_url"]})
            
            existing = self.collection.find_one({
                "_id": {"$ne": object_id},
                "$or": conditions
            })
            
            if existing:
                abort(400, "Partner with this name or URL already exists")
        
        # Update the partner
        result = self.patch_item_by_id(partner_id, update_doc)
        serialized = serialize_mongo_doc(result)
        
        # Publish partner_update event (A09b)
        self._publish_event("partner_update", {
            "partner_id": serialized["id"],
            "name": serialized["name"],
            "api_key": serialized["api_key"],
            "base_url": serialized["base_url"]
        })
        
        return serialized
    
    def delete_partner(self, partner_id: str):
        """
        Delete a partner connection (H24 DELETE).
        Publishes partner_delete event.
        """
        # Verify partner exists
        self.get_item_by_id(partner_id)
        
        # Delete the partner
        self.delete_item_by_id(partner_id)
        
        # Publish partner_delete event (A09b)
        self._publish_event("partner_delete", {
            "partner_id": partner_id
        })
    
    def verify_partner_connection(self, partner_id: str, api_key: str):
        """
        Verify partner connection using API key (H11).
        Returns partner_id if verification successful.
        """
        partner = self.get_item_by_id(partner_id)
        
        if partner.get("api_key") != api_key:
            abort(401, "Invalid API key")
        
        return {"partner_id": partner_id}
    
    def get_partner_by_id(self, partner_id: str):
        """
        Get a partner by ID.
        """
        result = self.get_item_by_id(partner_id)
        return serialize_mongo_doc(result)
