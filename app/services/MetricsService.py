"""
S08 Metrics Service - Core metrics aggregation service.

This service aggregates and provides 5 main types of metrics:
1. Total Customers
2. Number of active conversations
3. Customer Satisfaction Rate
4. Overall Offload Rate
5. Per-Partner Offload Rate

It operates in two modes:
- Real-time metrics collection via RabbitMQ events (background processing)
- Responding to HTTP requests (on-demand queries)
"""

import json
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Callable, Optional
from dataclasses import dataclass, field

from .MessageQueueService import MessageQueueService


@dataclass
class MetricsState:
    """In-memory state for metrics counters"""
    # Customer metrics
    total_customers: int = 0
    
    # Conversation metrics
    total_conversations: int = 0
    texting_conversations: int = 0
    calling_conversations: int = 0
    forwarding_conversations: int = 0
    ai_failed_conversations: int = 0
    offloaded_conversations: int = 0
    
    # Satisfaction metrics
    satisfaction_1: int = 0
    satisfaction_2: int = 0
    satisfaction_3: int = 0
    satisfaction_4: int = 0
    satisfaction_5: int = 0
    total_ratings: int = 0
    
    # Partner-specific metrics: partner_id -> counters
    partner_conversations: dict = field(default_factory=dict)
    partner_satisfaction: dict = field(default_factory=dict)
    
    # Partner cache from S07
    partner_cache: dict = field(default_factory=dict)  # partner_id -> partner_name
    partner_cache_timestamp: float = 0
    
    # Service health
    is_healthy: bool = True
    invalid_events_counter: int = 0


class MetricsService:
    """
    Main metrics service that handles:
    - Consuming events from S01 (A03a) and S04 (A04a)
    - Calling methods on S01 (A03b), S04 (A04b), S07 (A07)
    - Publishing events to S14 (A17a)
    - Responding to method calls from S14 (A17b)
    """
    
    # Status categories mapping
    STATUS_CATEGORIES = {
        "AI_AGENT_TEXTING": "texting",
        "AI_AGENT_CALLING": "calling",
        "FORWARDING": "forwarding",
        "HUMAN_AGENT_TEXTING": "texting",
        "HUMAN_AGENT_CALLING": "calling",
    }
    
    # AI failed statuses (conversations requiring human intervention)
    AI_FAILED_STATUSES = {"FORWARDING", "HUMAN_AGENT_TEXTING", "HUMAN_AGENT_CALLING"}
    
    PARTNER_CACHE_TTL = 3600  # 1 hour
    MAX_RETRY_ATTEMPTS = 2  # Reduced for faster startup when peers unavailable
    RETRY_DELAYS = [1, 2, 4]  # exponential backoff, reduced delays
    RPC_TIMEOUT = 5.0  # RPC timeout in seconds
    
    def __init__(
        self,
        rabbitmq_url: str | None = None,
        # Queue names - configurable
        s01_events_queue: str = "s01_events_queue",
        s04_events_queue: str = "s04_events_queue",
        s08_events_queue: str = "s08_events_queue",  # A17a - publish to S14
        s08_s01_requests_queue: str = "s08_s01_requests_queue",
        s08_s01_responses_queue: str = "s08_s01_responses_queue",
        s08_s04_requests_queue: str = "s08_s04_requests_queue",
        s08_s04_responses_queue: str = "s08_s04_responses_queue",
        s08_s07_requests_queue: str = "s08_s07_requests_queue",
        s08_s07_responses_queue: str = "s08_s07_responses_queue",
        s14_s08_requests_queue: str = "s14_s08_requests_queue",  # A17b - receive from S14
        s14_s08_responses_queue: str = "s14_s08_responses_queue",
    ):
        self.rabbitmq_url = rabbitmq_url
        
        # Queue names
        self.s01_events_queue = s01_events_queue
        self.s04_events_queue = s04_events_queue
        self.s08_events_queue = s08_events_queue
        self.s08_s01_requests_queue = s08_s01_requests_queue
        self.s08_s01_responses_queue = s08_s01_responses_queue
        self.s08_s04_requests_queue = s08_s04_requests_queue
        self.s08_s04_responses_queue = s08_s04_responses_queue
        self.s08_s07_requests_queue = s08_s07_requests_queue
        self.s08_s07_responses_queue = s08_s07_responses_queue
        self.s14_s08_requests_queue = s14_s08_requests_queue
        self.s14_s08_responses_queue = s14_s08_responses_queue
        
        # State
        self.state = MetricsState()
        self.state_lock = threading.RLock()
        
        # Pending responses for RPC calls
        self.pending_responses: dict[str, dict] = {}
        self.pending_responses_lock = threading.Lock()
        self.response_events: dict[str, threading.Event] = {}
        
        # MessageQueue service instances (will be created per-thread)
        self.mq_service: MessageQueueService | None = None
        self.mq_lock = threading.Lock()
        
        # Threads
        self.threads: list[threading.Thread] = []
        self.running = False
        
    def _create_mq_service(self) -> MessageQueueService:
        """Create a new MessageQueueService instance"""
        return MessageQueueService(self.rabbitmq_url)
    
    def _get_or_create_mq_service(self) -> MessageQueueService:
        """Get or create the main MQ service"""
        with self.mq_lock:
            if self.mq_service is None:
                self.mq_service = self._create_mq_service()
            return self.mq_service
    
    # ==================== INITIAL DATA LOAD ====================
    
    def _initial_data_load(self):
        """Load initial data from peer services at startup"""
        print("[MetricsService] Starting initial data load...")
        print("[MetricsService] NOTE: If peer services (S01, S04, S07) are not running, initial load will be skipped.")
        
        # Load customer count from S04
        self._load_customer_count()
        
        # Load conversation statistics from S01
        self._load_conversation_statistics()
        
        # Load satisfaction distribution from S01
        self._load_satisfaction_distribution()
        
        # Load per-partner offload data from S01
        self._load_partner_offload_data()
        
        # Load partner list from S07
        self._load_partner_cache()
        
        print("[MetricsService] Initial data load completed")
    
    def _load_customer_count(self):
        """Load customer count from S04 via A04b"""
        for attempt in range(self.MAX_RETRY_ATTEMPTS):
            try:
                result = self._call_s04_method("get_customers_count", {})
                if result and result.get("status") == "success":
                    with self.state_lock:
                        self.state.total_customers = result.get("content", 0)
                    print(f"[MetricsService] Loaded customer count: {self.state.total_customers}")
                    return
                else:
                    print(f"[MetricsService] Failed to load customer count: {result}")
            except Exception as e:
                print(f"[MetricsService] Error loading customer count (attempt {attempt + 1}): {e}")
            time.sleep(self.RETRY_DELAYS[min(attempt, len(self.RETRY_DELAYS) - 1)])
        
        print("[MetricsService] WARNING: Failed to load customer count - S04 service may not be running")
        print("[MetricsService] Service will continue with initial count = 0")
    
    def _load_conversation_statistics(self):
        """Load conversation statistics from S01 via A03b"""
        for attempt in range(self.MAX_RETRY_ATTEMPTS):
            try:
                result = self._call_s01_method("get_conversation_statistics", {})
                if result and result.get("status") == "success":
                    content = result.get("content", {})
                    with self.state_lock:
                        self.state.total_conversations = content.get("total_conversations", 0)
                        self.state.texting_conversations = content.get("texting_conversations", 0)
                        self.state.calling_conversations = content.get("calling_conversations", 0)
                        self.state.forwarding_conversations = content.get("forwarding_conversations", 0)
                        self.state.ai_failed_conversations = content.get("ai_failed_conversations", 0)
                        self.state.offloaded_conversations = content.get("offloaded_conversations", 0)
                    print(f"[MetricsService] Loaded conversation stats: total={self.state.total_conversations}")
                    return
                else:
                    print(f"[MetricsService] Failed to load conversation stats: {result}")
            except Exception as e:
                print(f"[MetricsService] Error loading conversation stats (attempt {attempt + 1}): {e}")
            time.sleep(self.RETRY_DELAYS[min(attempt, len(self.RETRY_DELAYS) - 1)])
        
        print("[MetricsService] WARNING: Failed to load conversation stats - S01 service may not be running")
        print("[MetricsService] Service will continue with initial stats = 0")
    
    def _load_satisfaction_distribution(self):
        """Load satisfaction distribution from S01 via A03b"""
        for attempt in range(self.MAX_RETRY_ATTEMPTS):
            try:
                result = self._call_s01_method("get_customer_satisfaction_distribution", {})
                if result and result.get("status") == "success":
                    content = result.get("content", {})
                    with self.state_lock:
                        self.state.satisfaction_1 = content.get("satisfaction_1", 0)
                        self.state.satisfaction_2 = content.get("satisfaction_2", 0)
                        self.state.satisfaction_3 = content.get("satisfaction_3", 0)
                        self.state.satisfaction_4 = content.get("satisfaction_4", 0)
                        self.state.satisfaction_5 = content.get("satisfaction_5", 0)
                        self.state.total_ratings = sum([
                            self.state.satisfaction_1,
                            self.state.satisfaction_2,
                            self.state.satisfaction_3,
                            self.state.satisfaction_4,
                            self.state.satisfaction_5,
                        ])
                    print(f"[MetricsService] Loaded satisfaction distribution: total_ratings={self.state.total_ratings}")
                    return
                elif result and result.get("status") == "error" and result.get("content") == "NO_DATA_FOUND":
                    # Initialize all counters to 0
                    print("[MetricsService] No satisfaction data found, initializing to 0")
                    return
                else:
                    print(f"[MetricsService] Failed to load satisfaction distribution: {result}")
            except Exception as e:
                print(f"[MetricsService] Error loading satisfaction distribution (attempt {attempt + 1}): {e}")
            time.sleep(self.RETRY_DELAYS[min(attempt, len(self.RETRY_DELAYS) - 1)])
        
        print("[MetricsService] Failed to load satisfaction distribution after retries, initializing to 0")
    
    def _load_partner_offload_data(self):
        """Load per-partner offload data from S01 via A03b"""
        for attempt in range(self.MAX_RETRY_ATTEMPTS):
            try:
                result = self._call_s01_method("get_offloaded_conversations_by_partner", {})
                if result and result.get("status") == "success":
                    content = result.get("content", {})
                    with self.state_lock:
                        for partner_id, offloaded_count in content.items():
                            if partner_id not in self.state.partner_conversations:
                                self.state.partner_conversations[partner_id] = {
                                    "total_conversations": 0,
                                    "texting_conversations": 0,
                                    "calling_conversations": 0,
                                    "forwarding_conversations": 0,
                                    "ai_failed_conversations": 0,
                                    "offloaded_conversations": offloaded_count,
                                }
                            else:
                                self.state.partner_conversations[partner_id]["offloaded_conversations"] = offloaded_count
                    print(f"[MetricsService] Loaded partner offload data for {len(content)} partners")
                    return
                elif result and result.get("status") == "error" and result.get("content") == "NO_DATA_FOUND":
                    print("[MetricsService] No partner offload data found")
                    return
                else:
                    print(f"[MetricsService] Failed to load partner offload data: {result}")
            except Exception as e:
                print(f"[MetricsService] Error loading partner offload data (attempt {attempt + 1}): {e}")
            time.sleep(self.RETRY_DELAYS[min(attempt, len(self.RETRY_DELAYS) - 1)])
        
        print("[MetricsService] Failed to load partner offload data after retries")
    
    def _load_partner_cache(self):
        """Load partner list from S07 via A07"""
        try:
            result = self._call_s07_method("get_partners", {})
            if result and result.get("status") == "success":
                content = result.get("content", [])
                with self.state_lock:
                    self.state.partner_cache = {
                        p["partner_id"]: p["name"] for p in content
                    }
                    self.state.partner_cache_timestamp = time.time()
                print(f"[MetricsService] Loaded partner cache: {len(self.state.partner_cache)} partners")
            else:
                print(f"[MetricsService] Warning: Failed to load partner cache: {result}")
        except Exception as e:
            print(f"[MetricsService] Warning: Error loading partner cache: {e}")
    
    # ==================== RPC METHOD CALLS ====================
    
    def _call_rpc_method(
        self,
        request_queue: str,
        response_queue: str,
        method: str,
        params: dict,
        timeout: float = 30.0
    ) -> dict | None:
        """Generic RPC method call over RabbitMQ"""
        request_id = str(uuid.uuid4())
        
        request = {
            "method": method,
            "params": params,
            "id": request_id,
        }
        
        # Setup response event
        response_event = threading.Event()
        with self.pending_responses_lock:
            self.response_events[request_id] = response_event
        
        try:
            # Publish request
            mq = self._get_or_create_mq_service()
            mq.declare_queue(request_queue)
            mq.publish_message(request_queue, request)
            
            # Wait for response
            if response_event.wait(timeout):
                with self.pending_responses_lock:
                    return self.pending_responses.pop(request_id, None)
            else:
                print(f"[MetricsService] RPC timeout for method {method}")
                return None
        finally:
            with self.pending_responses_lock:
                self.response_events.pop(request_id, None)
    
    def _call_s01_method(self, method: str, params: dict) -> dict | None:
        """Call S01 Consultation Service via A03b"""
        return self._call_rpc_method(
            self.s08_s01_requests_queue,
            self.s08_s01_responses_queue,
            method,
            params,
            timeout=self.RPC_TIMEOUT,
        )
    
    def _call_s04_method(self, method: str, params: dict) -> dict | None:
        """Call S04 Customer Identity Service via A04b"""
        return self._call_rpc_method(
            self.s08_s04_requests_queue,
            self.s08_s04_responses_queue,
            method,
            params,
            timeout=self.RPC_TIMEOUT,
        )
    
    def _call_s07_method(self, method: str, params: dict) -> dict | None:
        """Call S07 Partner Management Service via A07"""
        return self._call_rpc_method(
            self.s08_s07_requests_queue,
            self.s08_s07_responses_queue,
            method,
            params,
            timeout=self.RPC_TIMEOUT,
        )
    
    # ==================== EVENT HANDLERS ====================
    
    def _handle_s01_event(self, message: dict):
        """Handle events from S01 Consultation Service (A03a)"""
        event_type = message.get("event_type")
        params = message.get("params", {})
        event_id = message.get("id")
        
        print(f"[MetricsService] Received S01 event: {event_type} (id={event_id})")
        
        try:
            if event_type == "conversation_start":
                self._handle_conversation_start(params)
            elif event_type == "conversation_status_update":
                self._handle_conversation_status_update(params)
            elif event_type == "conversation_customer_satisfaction_changed":
                self._handle_satisfaction_changed(params)
            elif event_type == "conversation_forwarded":
                self._handle_conversation_forwarded(params)
            else:
                print(f"[MetricsService] Unknown S01 event type: {event_type}")
                with self.state_lock:
                    self.state.invalid_events_counter += 1
        except Exception as e:
            print(f"[MetricsService] Error handling S01 event: {e}")
            with self.state_lock:
                self.state.invalid_events_counter += 1
    
    def _handle_s04_event(self, message: dict):
        """Handle events from S04 Customer Identity Service (A04a)"""
        event_type = message.get("event_type")
        params = message.get("params", {})
        event_id = message.get("id")
        
        print(f"[MetricsService] Received S04 event: {event_type} (id={event_id})")
        
        try:
            if event_type == "customer_registered":
                self._handle_customer_registered(params)
            else:
                print(f"[MetricsService] Unknown S04 event type: {event_type}")
                with self.state_lock:
                    self.state.invalid_events_counter += 1
        except Exception as e:
            print(f"[MetricsService] Error handling S04 event: {e}")
            with self.state_lock:
                self.state.invalid_events_counter += 1
    
    def _handle_customer_registered(self, params: dict):
        """Handle customer_registered event from S04"""
        customer_id = params.get("customer_id")
        if not customer_id:
            print("[MetricsService] Invalid customer_registered event: missing customer_id")
            with self.state_lock:
                self.state.invalid_events_counter += 1
            return
        
        with self.state_lock:
            self.state.total_customers += 1
        
        print(f"[MetricsService] Customer registered: {customer_id}, total={self.state.total_customers}")
    
    def _handle_conversation_start(self, params: dict):
        """Handle conversation_start event from S01"""
        conversation_id = params.get("conversation_id")
        customer_id = params.get("customer_id")
        partner_id = params.get("partner_id")
        created_at = params.get("created_at")
        
        if not all([conversation_id, customer_id, partner_id, created_at]):
            print(f"[MetricsService] Invalid conversation_start event: missing fields")
            with self.state_lock:
                self.state.invalid_events_counter += 1
            return
        
        with self.state_lock:
            # Increment global counters
            self.state.total_conversations += 1
            self.state.texting_conversations += 1  # Default status is AI_AGENT_TEXTING
            self.state.offloaded_conversations += 1  # New conversation starts as offloaded (AI handling)
            
            # Initialize/update partner-specific counters
            if partner_id not in self.state.partner_conversations:
                self.state.partner_conversations[partner_id] = {
                    "total_conversations": 0,
                    "texting_conversations": 0,
                    "calling_conversations": 0,
                    "forwarding_conversations": 0,
                    "ai_failed_conversations": 0,
                    "offloaded_conversations": 0,
                }
            
            self.state.partner_conversations[partner_id]["total_conversations"] += 1
            self.state.partner_conversations[partner_id]["texting_conversations"] += 1
            self.state.partner_conversations[partner_id]["offloaded_conversations"] += 1
        
        # Publish event to S14 (A17a)
        self._publish_partner_event("conversation_start_by_partner", {
            "conversation_id": conversation_id,
            "partner_id": partner_id,
            "started_at": created_at,
        })
        
        print(f"[MetricsService] Conversation started: {conversation_id}")
    
    def _handle_conversation_status_update(self, params: dict):
        """Handle conversation_status_update event from S01"""
        conversation_id = params.get("conversation_id")
        partner_id = params.get("partner_id")
        old_status = params.get("old_status")
        new_status = params.get("new_status")
        updated_at = params.get("updated_at")
        
        if not all([conversation_id, partner_id, old_status, new_status, updated_at]):
            print(f"[MetricsService] Invalid conversation_status_update event: missing fields")
            with self.state_lock:
                self.state.invalid_events_counter += 1
            return
        
        old_category = self.STATUS_CATEGORIES.get(old_status)
        new_category = self.STATUS_CATEGORIES.get(new_status)
        
        if not old_category or not new_category:
            print(f"[MetricsService] Unknown status: old={old_status}, new={new_status}")
            with self.state_lock:
                self.state.invalid_events_counter += 1
            return
        
        with self.state_lock:
            # Update global counters
            if old_category == "texting":
                self.state.texting_conversations -= 1
            elif old_category == "calling":
                self.state.calling_conversations -= 1
            elif old_category == "forwarding":
                self.state.forwarding_conversations -= 1
            
            if new_category == "texting":
                self.state.texting_conversations += 1
            elif new_category == "calling":
                self.state.calling_conversations += 1
            elif new_category == "forwarding":
                self.state.forwarding_conversations += 1
            
            # Update ai_failed and offloaded based on status changes
            was_ai_failed = old_status in self.AI_FAILED_STATUSES
            is_ai_failed = new_status in self.AI_FAILED_STATUSES
            
            if not was_ai_failed and is_ai_failed:
                self.state.ai_failed_conversations += 1
                self.state.offloaded_conversations -= 1
            elif was_ai_failed and not is_ai_failed:
                self.state.ai_failed_conversations -= 1
                self.state.offloaded_conversations += 1
            
            # Update partner-specific counters
            if partner_id in self.state.partner_conversations:
                pc = self.state.partner_conversations[partner_id]
                
                if old_category == "texting":
                    pc["texting_conversations"] -= 1
                elif old_category == "calling":
                    pc["calling_conversations"] -= 1
                elif old_category == "forwarding":
                    pc["forwarding_conversations"] -= 1
                
                if new_category == "texting":
                    pc["texting_conversations"] += 1
                elif new_category == "calling":
                    pc["calling_conversations"] += 1
                elif new_category == "forwarding":
                    pc["forwarding_conversations"] += 1
                
                if not was_ai_failed and is_ai_failed:
                    pc["ai_failed_conversations"] += 1
                    pc["offloaded_conversations"] -= 1
                elif was_ai_failed and not is_ai_failed:
                    pc["ai_failed_conversations"] -= 1
                    pc["offloaded_conversations"] += 1
        
        # Publish event to S14 (A17a)
        self._publish_partner_event("conversation_changed_status_by_partner", {
            "conversation_id": conversation_id,
            "partner_id": partner_id,
            "old_status": old_status,
            "new_status": new_status,
            "updated_at": updated_at,
        })
        
        print(f"[MetricsService] Conversation status updated: {conversation_id} {old_status} -> {new_status}")
    
    def _handle_satisfaction_changed(self, params: dict):
        """Handle conversation_customer_satisfaction_changed event from S01"""
        conversation_id = params.get("conversation_id")
        partner_id = params.get("partner_id")
        old_satisfaction = params.get("old_satisfaction")
        new_satisfaction = params.get("new_satisfaction")
        updated_at = params.get("updated_at")
        
        if not all([conversation_id, partner_id, new_satisfaction, updated_at]):
            print(f"[MetricsService] Invalid satisfaction_changed event: missing fields")
            with self.state_lock:
                self.state.invalid_events_counter += 1
            return
        
        if new_satisfaction not in [1, 2, 3, 4, 5]:
            print(f"[MetricsService] Invalid satisfaction value: {new_satisfaction}")
            with self.state_lock:
                self.state.invalid_events_counter += 1
            return
        
        with self.state_lock:
            # Decrement old satisfaction if exists
            if old_satisfaction and old_satisfaction in [1, 2, 3, 4, 5]:
                old_attr = f"satisfaction_{old_satisfaction}"
                setattr(self.state, old_attr, getattr(self.state, old_attr) - 1)
            else:
                # New rating
                self.state.total_ratings += 1
            
            # Increment new satisfaction
            new_attr = f"satisfaction_{new_satisfaction}"
            setattr(self.state, new_attr, getattr(self.state, new_attr) + 1)
            
            # Update partner-specific satisfaction
            if partner_id not in self.state.partner_satisfaction:
                self.state.partner_satisfaction[partner_id] = {
                    "satisfaction_1": 0,
                    "satisfaction_2": 0,
                    "satisfaction_3": 0,
                    "satisfaction_4": 0,
                    "satisfaction_5": 0,
                }
            
            ps = self.state.partner_satisfaction[partner_id]
            if old_satisfaction and old_satisfaction in [1, 2, 3, 4, 5]:
                ps[f"satisfaction_{old_satisfaction}"] -= 1
            ps[f"satisfaction_{new_satisfaction}"] += 1
        
        # Publish event to S14 (A17a)
        self._publish_partner_event("conversation_satisfaction_change_by_partner", {
            "conversation_id": conversation_id,
            "partner_id": partner_id,
            "old_satisfaction": old_satisfaction,
            "new_satisfaction": new_satisfaction,
            "updated_at": updated_at,
        })
        
        print(f"[MetricsService] Satisfaction changed: {conversation_id} {old_satisfaction} -> {new_satisfaction}")
    
    def _handle_conversation_forwarded(self, params: dict):
        """Handle conversation_forwarded event from S01"""
        conversation_id = params.get("conversation_id")
        partner_id = params.get("partner_id")
        
        if not all([conversation_id, partner_id]):
            print(f"[MetricsService] Invalid conversation_forwarded event: missing fields")
            with self.state_lock:
                self.state.invalid_events_counter += 1
            return
        
        # Note: ai_failed_conversations is already incremented in status_update handler
        # when status changes to FORWARDING. This event is for additional tracking if needed.
        print(f"[MetricsService] Conversation forwarded: {conversation_id} to partner {partner_id}")
    
    # ==================== A17a EVENT PUBLISHING ====================
    
    def _publish_partner_event(self, event_type: str, params: dict):
        """Publish event to S14 via A17a"""
        try:
            mq = self._get_or_create_mq_service()
            mq.declare_queue(self.s08_events_queue)
            
            event = {
                "event_type": event_type,
                "params": params,
                "id": str(uuid.uuid4()),
            }
            
            mq.publish_message(self.s08_events_queue, event)
            print(f"[MetricsService] Published A17a event: {event_type}")
        except Exception as e:
            print(f"[MetricsService] Error publishing A17a event: {e}")
    
    # ==================== A17b METHOD HANDLERS ====================
    
    def _handle_s14_method_request(self, message: dict):
        """Handle method requests from S14 (A17b)"""
        request_id = message.get("id")
        method = message.get("method")
        params = message.get("params", {})
        
        print(f"[MetricsService] Received A17b method request: {method} (id={request_id})")
        
        result_status = "success"
        result_content = None
        
        try:
            if method == "get_partner_conversation_statistics":
                result_content = self._get_partner_conversation_statistics(params)
            elif method == "get_partner_satisfaction_distribution":
                result_content = self._get_partner_satisfaction_distribution(params)
            else:
                result_status = "error"
                result_content = f"Unknown method: {method}"
        except Exception as e:
            result_status = "error"
            result_content = str(e)
        
        # Send response
        response = {
            "id": request_id,
            "result": {
                "status": result_status,
                "content": result_content,
            }
        }
        
        try:
            mq = self._get_or_create_mq_service()
            mq.declare_queue(self.s14_s08_responses_queue)
            mq.publish_message(self.s14_s08_responses_queue, response)
        except Exception as e:
            print(f"[MetricsService] Error sending A17b response: {e}")
    
    def _get_partner_conversation_statistics(self, params: dict) -> dict:
        """Get conversation statistics for a specific partner (A17b)"""
        partner_id = params.get("partner_id")
        
        if not partner_id:
            raise ValueError("PARTNER_NOT_FOUND")
        
        with self.state_lock:
            if partner_id not in self.state.partner_conversations:
                raise ValueError("PARTNER_NOT_FOUND")
            
            pc = self.state.partner_conversations[partner_id]
            return {
                "partner_id": partner_id,
                "total_conversations": pc.get("total_conversations", 0),
                "forwarding_conversations": pc.get("forwarding_conversations", 0),
                "texting_conversations": pc.get("texting_conversations", 0),
                "calling_conversations": pc.get("calling_conversations", 0),
                "ai_failed_conversations": pc.get("ai_failed_conversations", 0),
                "offloaded_conversations": pc.get("offloaded_conversations", 0),
            }
    
    def _get_partner_satisfaction_distribution(self, params: dict) -> dict:
        """Get satisfaction distribution for a specific partner (A17b)"""
        partner_id = params.get("partner_id")
        
        if not partner_id:
            raise ValueError("PARTNER_NOT_FOUND")
        
        with self.state_lock:
            if partner_id not in self.state.partner_satisfaction:
                # Check if partner exists but has no ratings
                if partner_id in self.state.partner_conversations:
                    raise ValueError("NO_DATA_FOUND")
                raise ValueError("PARTNER_NOT_FOUND")
            
            ps = self.state.partner_satisfaction[partner_id]
            return {
                "partner_id": partner_id,
                "satisfaction_1": ps.get("satisfaction_1", 0),
                "satisfaction_2": ps.get("satisfaction_2", 0),
                "satisfaction_3": ps.get("satisfaction_3", 0),
                "satisfaction_4": ps.get("satisfaction_4", 0),
                "satisfaction_5": ps.get("satisfaction_5", 0),
            }
    
    # ==================== RESPONSE HANDLERS ====================
    
    def _handle_rpc_response(self, message: dict):
        """Handle RPC responses from peer services"""
        response_id = message.get("id")
        if not response_id:
            print("[MetricsService] Received response without id")
            return
        
        with self.pending_responses_lock:
            if response_id in self.response_events:
                self.pending_responses[response_id] = message.get("result", {})
                self.response_events[response_id].set()
    
    # ==================== PUBLIC API METHODS (for HTTP controllers) ====================
    
    def get_total_customers(self) -> dict:
        """Get total customers count (H21.1)"""
        # Query S04 for fresh data
        result = self._call_s04_method("get_customers_count", {})
        
        if result is None:
            raise ServiceUnavailableError("Customer Identity Service unavailable")
        
        if result.get("status") == "error":
            content = result.get("content", "")
            if content == "DB_TIMEOUT":
                raise DatabaseTimeoutError("Database timeout while counting customers")
            raise ServiceError(content)
        
        return {
            "status": "success",
            "total_customers": result.get("content", 0),
        }
    
    def get_conversation_summary(self) -> dict:
        """Get conversation summary (H21.2)"""
        # Query S01 for fresh data
        result = self._call_s01_method("get_conversation_statistics", {})
        
        if result is None:
            raise ServiceUnavailableError("Consultation Service unavailable")
        
        if result.get("status") == "error":
            content = result.get("content", "")
            if content == "DB_CONNECTION_ERROR":
                raise DatabaseConnectionError("Database connection error")
            raise ServiceError(content)
        
        content = result.get("content", {})
        return {
            "status": "success",
            "total_conversations": content.get("total_conversations", 0),
            "texting_conversations": content.get("texting_conversations", 0),
            "calling_conversations": content.get("calling_conversations", 0),
        }
    
    def get_satisfaction_distribution(self) -> dict:
        """Get satisfaction distribution (H21.3)"""
        # Query S01 for fresh data
        result = self._call_s01_method("get_customer_satisfaction_distribution", {})
        
        if result is None:
            raise ServiceUnavailableError("Consultation Service unavailable")
        
        if result.get("status") == "error":
            content = result.get("content", "")
            if content == "NO_DATA_FOUND":
                return {
                    "status": "success",
                    "total_conversations": 0,
                    "satisfaction_distribution": {
                        "satisfaction_1": 0,
                        "satisfaction_2": 0,
                        "satisfaction_3": 0,
                        "satisfaction_4": 0,
                        "satisfaction_5": 0,
                    },
                    "average_rating": 0,
                }
            raise ServiceError(content)
        
        content = result.get("content", {})
        s1 = content.get("satisfaction_1", 0)
        s2 = content.get("satisfaction_2", 0)
        s3 = content.get("satisfaction_3", 0)
        s4 = content.get("satisfaction_4", 0)
        s5 = content.get("satisfaction_5", 0)
        total = s1 + s2 + s3 + s4 + s5
        
        average_rating = 0
        if total > 0:
            average_rating = round((1*s1 + 2*s2 + 3*s3 + 4*s4 + 5*s5) / total, 2)
        
        return {
            "status": "success",
            "total_conversations": total,
            "satisfaction_distribution": {
                "satisfaction_1": s1,
                "satisfaction_2": s2,
                "satisfaction_3": s3,
                "satisfaction_4": s4,
                "satisfaction_5": s5,
            },
            "average_rating": average_rating,
        }
    
    def get_offload_rate(self) -> dict:
        """Get overall offload rate (H21.4)"""
        # Query S01 for fresh data
        result = self._call_s01_method("get_conversation_statistics", {})
        
        if result is None:
            raise ServiceUnavailableError("Consultation Service unavailable")
        
        if result.get("status") == "error":
            content = result.get("content", "")
            raise ServiceError(content)
        
        content = result.get("content", {})
        total = content.get("total_conversations", 0)
        ai_failed = content.get("ai_failed_conversations", 0)
        offloaded = content.get("offloaded_conversations", 0)
        
        offload_rate = 0
        if total > 0:
            offload_rate = round((offloaded / total) * 100, 2)
        
        return {
            "status": "success",
            "total_conversations": total,
            "ai_failed_conversation": ai_failed,
            "offloaded_conversations": offloaded,
            "offload_rate_percentage": offload_rate,
        }
    
    def get_offload_rate_by_partner(self, partner_id_filter: str | None = None) -> dict:
        """Get offload rate by partner (H21.5)"""
        # Query S01 for per-partner data
        result = self._call_s01_method("get_offloaded_conversations_by_partner", {})
        
        if result is None:
            raise ServiceUnavailableError("Consultation Service unavailable")
        
        if result.get("status") == "error":
            content = result.get("content", "")
            if content == "NO_DATA_FOUND":
                return {
                    "status": "success",
                    "total_consultations": 0,
                    "partners": [],
                    "overall_offload_rate_percentage": 0,
                }
            raise ServiceError(content)
        
        # Refresh partner cache if needed
        self._refresh_partner_cache_if_needed()
        
        content = result.get("content", {})  # partner_id -> offloaded_count
        
        # Get conversation statistics
        conv_result = self._call_s01_method("get_conversation_statistics", {})
        conv_content = {}
        if conv_result and conv_result.get("status") == "success":
            conv_content = conv_result.get("content", {})
        
        partners = []
        total_consultations = 0
        total_offloaded = 0
        
        for partner_id, offloaded_count in content.items():
            if partner_id_filter and partner_id != partner_id_filter:
                continue
            
            # Get partner-specific data from state
            with self.state_lock:
                pc = self.state.partner_conversations.get(partner_id, {})
                partner_total = pc.get("total_conversations", offloaded_count)
                partner_ai_failed = pc.get("ai_failed_conversations", 0)
            
            partner_name = self.state.partner_cache.get(partner_id, partner_id)
            
            offload_rate = 0
            if partner_total > 0:
                offload_rate = round((offloaded_count / partner_total) * 100, 2)
            
            partners.append({
                "partner_id": partner_id,
                "partner_name": partner_name,
                "total_conversations": partner_total,
                "offloaded_conversations": offloaded_count,
                "ai_failed_conversations": partner_ai_failed,
                "offload_rate_percentage": offload_rate,
            })
            
            total_consultations += partner_total
            total_offloaded += offloaded_count
        
        overall_rate = 0
        if total_consultations > 0:
            overall_rate = round((total_offloaded / total_consultations) * 100, 2)
        
        return {
            "status": "success",
            "total_consultations": total_consultations,
            "partners": partners,
            "overall_offload_rate_percentage": overall_rate,
        }
    
    def _refresh_partner_cache_if_needed(self):
        """Refresh partner cache if TTL expired"""
        with self.state_lock:
            if time.time() - self.state.partner_cache_timestamp > self.PARTNER_CACHE_TTL:
                pass  # Need to refresh
            else:
                return  # Cache is fresh
        
        self._load_partner_cache()
    
    def get_partner_name(self, partner_id: str) -> str:
        """Get partner name from cache, refresh if not found"""
        with self.state_lock:
            name = self.state.partner_cache.get(partner_id)
            if name:
                return name
        
        # Refresh cache and try again
        self._load_partner_cache()
        
        with self.state_lock:
            return self.state.partner_cache.get(partner_id, partner_id)
    
    def is_healthy(self) -> bool:
        """Check if service is healthy"""
        with self.state_lock:
            return self.state.is_healthy
    
    # ==================== SERVICE LIFECYCLE ====================
    
    def start(self):
        """Start the metrics service"""
        print("[MetricsService] Starting...")
        self.running = True
        
        # Start response consumer threads FIRST (needed for RPC calls)
        self.response_threads = [
            threading.Thread(target=self._consume_s01_responses, daemon=True, name="S01ResponseConsumer"),
            threading.Thread(target=self._consume_s04_responses, daemon=True, name="S04ResponseConsumer"),
            threading.Thread(target=self._consume_s07_responses, daemon=True, name="S07ResponseConsumer"),
        ]
        
        for t in self.response_threads:
            t.start()
        
        # Wait a moment for response consumers to be ready
        time.sleep(0.5)
        
        # Initial data load (requires response consumers to be running)
        self._initial_data_load()
        
        # Start event consumer threads
        self.threads = [
            threading.Thread(target=self._consume_s01_events, daemon=True, name="S01EventConsumer"),
            threading.Thread(target=self._consume_s04_events, daemon=True, name="S04EventConsumer"),
            threading.Thread(target=self._consume_s14_requests, daemon=True, name="S14RequestConsumer"),
        ]
        
        for t in self.threads:
            t.start()
        
        print("[MetricsService] Started")
    
    def stop(self):
        """Stop the metrics service"""
        print("[MetricsService] Stopping...")
        self.running = False
        print("[MetricsService] Stopped")
    
    def wait(self):
        """Wait for all threads to complete"""
        for t in self.threads:
            t.join()
    
    def _consume_s01_events(self):
        """Consumer thread for S01 events (A03a)"""
        try:
            mq = self._create_mq_service()
            mq.declare_queue(self.s01_events_queue)
            mq.register_callback(self.s01_events_queue, self._handle_s01_event)
            print(f"[MetricsService] Consuming S01 events from {self.s01_events_queue}")
            mq.start_consuming()
        except Exception as e:
            print(f"[MetricsService] Error consuming S01 events: {e}")
            with self.state_lock:
                self.state.is_healthy = False
    
    def _consume_s04_events(self):
        """Consumer thread for S04 events (A04a)"""
        try:
            mq = self._create_mq_service()
            mq.declare_queue(self.s04_events_queue)
            mq.register_callback(self.s04_events_queue, self._handle_s04_event)
            print(f"[MetricsService] Consuming S04 events from {self.s04_events_queue}")
            mq.start_consuming()
        except Exception as e:
            print(f"[MetricsService] Error consuming S04 events: {e}")
            with self.state_lock:
                self.state.is_healthy = False
    
    def _consume_s01_responses(self):
        """Consumer thread for S01 method responses (A03b)"""
        try:
            mq = self._create_mq_service()
            mq.declare_queue(self.s08_s01_responses_queue)
            mq.register_callback(self.s08_s01_responses_queue, self._handle_rpc_response)
            print(f"[MetricsService] Consuming S01 responses from {self.s08_s01_responses_queue}")
            mq.start_consuming()
        except Exception as e:
            print(f"[MetricsService] Error consuming S01 responses: {e}")
    
    def _consume_s04_responses(self):
        """Consumer thread for S04 method responses (A04b)"""
        try:
            mq = self._create_mq_service()
            mq.declare_queue(self.s08_s04_responses_queue)
            mq.register_callback(self.s08_s04_responses_queue, self._handle_rpc_response)
            print(f"[MetricsService] Consuming S04 responses from {self.s08_s04_responses_queue}")
            mq.start_consuming()
        except Exception as e:
            print(f"[MetricsService] Error consuming S04 responses: {e}")
    
    def _consume_s07_responses(self):
        """Consumer thread for S07 method responses (A07)"""
        try:
            mq = self._create_mq_service()
            mq.declare_queue(self.s08_s07_responses_queue)
            mq.register_callback(self.s08_s07_responses_queue, self._handle_rpc_response)
            print(f"[MetricsService] Consuming S07 responses from {self.s08_s07_responses_queue}")
            mq.start_consuming()
        except Exception as e:
            print(f"[MetricsService] Error consuming S07 responses: {e}")
    
    def _consume_s14_requests(self):
        """Consumer thread for S14 method requests (A17b)"""
        try:
            mq = self._create_mq_service()
            mq.declare_queue(self.s14_s08_requests_queue)
            mq.declare_queue(self.s14_s08_responses_queue)
            mq.register_callback(self.s14_s08_requests_queue, self._handle_s14_method_request)
            print(f"[MetricsService] Consuming S14 requests from {self.s14_s08_requests_queue}")
            mq.start_consuming()
        except Exception as e:
            print(f"[MetricsService] Error consuming S14 requests: {e}")


# ==================== CUSTOM EXCEPTIONS ====================

class ServiceError(Exception):
    """Base exception for service errors"""
    pass


class ServiceUnavailableError(ServiceError):
    """Exception when a peer service is unavailable"""
    pass


class DatabaseTimeoutError(ServiceError):
    """Exception when database operation times out"""
    pass


class DatabaseConnectionError(ServiceError):
    """Exception when database connection fails"""
    pass
