"""
S14. Partner Metrics Service

This service aggregates and provides 3 main types of metrics for the Partner Portal:
1. Total Active Conversations with Partner Consultants
2. Customer Satisfaction Rate
3. Partner Offload Rate

The service operates in two modes:
- Real-time metrics collection via events from Core (background processing)
- Responding to HTTP requests (on-demand queries)
"""

import os
import json
import threading
import time
import uuid
from typing import Optional, Callable
from .MessageQueueService import MessageQueueService


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.
    After 5 consecutive failures: open circuit for 30 seconds.
    After 30s: attempt half-open (single request).
    Close circuit if request succeeds.
    """
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.lock = threading.Lock()
    
    def record_success(self):
        with self.lock:
            self.failure_count = 0
            self.state = "CLOSED"
    
    def record_failure(self):
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
    
    def can_execute(self) -> bool:
        with self.lock:
            if self.state == "CLOSED":
                return True
            elif self.state == "OPEN":
                if self.last_failure_time and (time.time() - self.last_failure_time) >= self.recovery_timeout:
                    self.state = "HALF_OPEN"
                    return True
                return False
            elif self.state == "HALF_OPEN":
                return True
            return False


class PartnerMetricsService:
    """
    Partner Metrics Service (S14) - aggregates metrics for Partner Portal.
    
    Background Processing:
    - Consumes events from S08 Core Metrics Service via A17a
    - Calls S08 methods via A17b for initial data and on-demand queries
    
    HTTP API:
    - H30.1: GET /api/v1/partner/metrics/conversations
    - H30.2: GET /api/v1/partner/metrics/satisfaction-rate
    - H30.3: GET /api/v1/partner/metrics/offload-rate
    """
    
    def __init__(self):
        # Configuration from environment
        self.partner_id = os.getenv("PARTNER_ID", "")
        self.events_queue = os.getenv("S08_EVENTS_QUEUE", "s08_events_queue")
        self.requests_queue = os.getenv("S14_S08_REQUESTS_QUEUE", "s14_s08_requests_queue")
        self.responses_queue = os.getenv("S14_S08_RESPONSES_QUEUE", "s14_s08_responses_queue")
        self.num_worker_threads = int(os.getenv("NUM_WORKER_THREADS", "4"))
        
        # Metrics counters (Flow 1 - Conversations)
        self.total_conversations = 0
        self.forwarding_conversations = 0
        self.texting_conversations = 0
        self.calling_conversations = 0
        
        # Metrics counters (Flow 2 - Satisfaction)
        self.satisfaction_1 = 0
        self.satisfaction_2 = 0
        self.satisfaction_3 = 0
        self.satisfaction_4 = 0
        self.satisfaction_5 = 0
        self.total_ratings = 0
        self.average_rating = 0.0
        
        # Metrics counters (Flow 3 - Offload)
        self.ai_failed_conversations = 0
        self.offloaded_conversations = 0
        
        # Thread safety locks
        self.conversations_lock = threading.Lock()
        self.satisfaction_lock = threading.Lock()
        self.offload_lock = threading.Lock()
        
        # Event buffer for handling disconnections
        self.event_buffer: list[dict] = []
        self.event_buffer_lock = threading.Lock()
        self.max_event_buffer_size = 5000
        
        # Invalid events counter
        self.invalid_events_counter = 0
        self.invalid_events_lock = threading.Lock()
        
        # Health status
        self.is_healthy = True
        self.health_lock = threading.Lock()
        
        # Circuit breaker for S08 calls
        self.circuit_breaker = CircuitBreaker()
        
        # MessageQueue service (will be initialized in start())
        self.mq_service: Optional[MessageQueueService] = None
        self.mq_lock = threading.Lock()
        
        # Worker threads
        self.worker_threads: list[threading.Thread] = []
        
        # Response handlers for RPC calls
        self.pending_requests: dict[str, dict] = {}
        self.pending_requests_lock = threading.Lock()
        self.response_events: dict[str, threading.Event] = {}
    
    def start(self):
        """
        Initialize the service:
        1. Connect to RabbitMQ
        2. Load initial data from S08
        3. Start event listener workers
        """
        print(f"[S14] Starting Partner Metrics Service for partner: {self.partner_id}")
        
        # Initialize MessageQueue service
        self.mq_service = MessageQueueService()
        
        # Declare queues
        self.mq_service.declare_queue(self.events_queue)
        self.mq_service.declare_queue(self.requests_queue)
        self.mq_service.declare_queue(self.responses_queue)
        
        # Load initial data from S08
        self._load_initial_data()
        
        # Start response listener thread (for RPC responses)
        response_listener_thread = threading.Thread(
            target=self._start_response_listener,
            daemon=True
        )
        response_listener_thread.start()
        
        # Start event listener worker threads
        for i in range(self.num_worker_threads):
            thread = threading.Thread(
                target=self._start_event_listener,
                daemon=True
            )
            self.worker_threads.append(thread)
            thread.start()
        
        print(f"[S14] Service started with {self.num_worker_threads} worker threads")
    
    def _load_initial_data(self):
        """
        Service Startup - Initial Data Load:
        - Call A17b Method APIs to get current partner statistics from S08
        - Initialize counters
        """
        print("[S14] Loading initial data from S08...")
        
        # Load conversation statistics (Flow 1 & 3)
        self._load_conversation_statistics()
        
        # Load satisfaction distribution (Flow 2)
        self._load_satisfaction_distribution()
    
    def _load_conversation_statistics(self, max_retries: int = 3):
        """
        Call get_partner_conversation_statistics method on S08.
        """
        for attempt in range(max_retries):
            try:
                response = self._call_s08_method(
                    method="get_partner_conversation_statistics",
                    params={"partner_id": self.partner_id}
                )
                
                if response and response.get("result", {}).get("status") == "success":
                    content = response["result"]["content"]
                    
                    with self.conversations_lock:
                        self.total_conversations = content.get("total_conversations", 0)
                        self.forwarding_conversations = content.get("forwarding_conversations", 0)
                        self.texting_conversations = content.get("texting_conversations", 0)
                        self.calling_conversations = content.get("calling_conversations", 0)
                    
                    with self.offload_lock:
                        self.ai_failed_conversations = content.get("ai_failed_conversations", 0)
                        self.offloaded_conversations = content.get("offloaded_conversations", 0)
                    
                    print(f"[S14] Loaded conversation statistics: total={self.total_conversations}")
                    return
                
                elif response and response.get("result", {}).get("status") == "error":
                    error_content = response["result"].get("content", "")
                    
                    if error_content == "PARTNER_NOT_FOUND":
                        print(f"[S14] Partner not found, initializing counters to 0")
                        self._reset_conversation_counters()
                        return
                    
                    elif error_content == "DB_CONNECTION_ERROR":
                        print(f"[S14] DB connection error, retrying... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    
                    else:
                        print(f"[S14] Error loading conversation statistics: {error_content}")
                        raise Exception(error_content)
                
            except Exception as e:
                print(f"[S14] Failed to load conversation statistics (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    self._set_unhealthy()
                    raise
    
    def _load_satisfaction_distribution(self, max_retries: int = 3):
        """
        Call get_partner_satisfaction_distribution method on S08.
        """
        for attempt in range(max_retries):
            try:
                response = self._call_s08_method(
                    method="get_partner_satisfaction_distribution",
                    params={"partner_id": self.partner_id}
                )
                
                if response and response.get("result", {}).get("status") == "success":
                    content = response["result"]["content"]
                    
                    with self.satisfaction_lock:
                        self.satisfaction_1 = content.get("satisfaction_1", 0)
                        self.satisfaction_2 = content.get("satisfaction_2", 0)
                        self.satisfaction_3 = content.get("satisfaction_3", 0)
                        self.satisfaction_4 = content.get("satisfaction_4", 0)
                        self.satisfaction_5 = content.get("satisfaction_5", 0)
                        self.total_ratings = (
                            self.satisfaction_1 + self.satisfaction_2 + 
                            self.satisfaction_3 + self.satisfaction_4 + self.satisfaction_5
                        )
                        self._recalculate_average_rating()
                    
                    print(f"[S14] Loaded satisfaction distribution: total_ratings={self.total_ratings}")
                    return
                
                elif response and response.get("result", {}).get("status") == "error":
                    error_content = response["result"].get("content", "")
                    
                    if error_content == "PARTNER_NOT_FOUND":
                        print(f"[S14] Partner not found, initializing satisfaction counters to 0")
                        self._reset_satisfaction_counters()
                        return
                    
                    elif error_content == "NO_DATA_FOUND":
                        print(f"[S14] No satisfaction data found, initializing counters to 0")
                        self._reset_satisfaction_counters()
                        return
                    
                    elif error_content == "DB_CONNECTION_ERROR":
                        print(f"[S14] DB connection error, retrying... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(2 ** attempt)
                        continue
                    
                    else:
                        print(f"[S14] Error loading satisfaction distribution: {error_content}")
                        raise Exception(error_content)
                
            except Exception as e:
                print(f"[S14] Failed to load satisfaction distribution (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    self._set_unhealthy()
                    raise
    
    def _call_s08_method(self, method: str, params: dict, timeout: float = 30.0) -> Optional[dict]:
        """
        Call a method on S08 via A17b (RabbitMQ RPC pattern).
        """
        if not self.circuit_breaker.can_execute():
            print(f"[S14] Circuit breaker is open, cannot call S08")
            return None
        
        request_id = str(uuid.uuid4())
        request_message = {
            "method": method,
            "params": params,
            "id": request_id
        }
        
        # Set up response event
        response_event = threading.Event()
        with self.pending_requests_lock:
            self.response_events[request_id] = response_event
            self.pending_requests[request_id] = {}
        
        try:
            # Publish request
            with self.mq_lock:
                if self.mq_service:
                    self.mq_service.publish_message(self.requests_queue, request_message)
            
            # Wait for response
            if response_event.wait(timeout=timeout):
                with self.pending_requests_lock:
                    response = self.pending_requests.get(request_id, {})
                    self.circuit_breaker.record_success()
                    return response
            else:
                print(f"[S14] Timeout waiting for S08 response for request {request_id}")
                self.circuit_breaker.record_failure()
                return None
                
        except Exception as e:
            print(f"[S14] Error calling S08 method {method}: {e}")
            self.circuit_breaker.record_failure()
            return None
        
        finally:
            # Cleanup
            with self.pending_requests_lock:
                self.response_events.pop(request_id, None)
                self.pending_requests.pop(request_id, None)
    
    def _start_response_listener(self):
        """
        Start a listener for RPC responses from S08.
        """
        try:
            with self.mq_lock:
                if self.mq_service:
                    mq = self.mq_service.clone()
            
            mq.declare_queue(self.responses_queue)
            mq.register_callback(self.responses_queue, self._handle_rpc_response)
            print(f"[S14] Response listener started on queue: {self.responses_queue}")
            mq.start_consuming()
            
        except Exception as e:
            print(f"[S14] Response listener error: {e}")
            self._handle_connection_lost()
    
    def _handle_rpc_response(self, message: dict):
        """
        Handle RPC response from S08.
        """
        request_id = message.get("id")
        if not request_id:
            return
        
        with self.pending_requests_lock:
            if request_id in self.pending_requests:
                self.pending_requests[request_id] = message
                event = self.response_events.get(request_id)
                if event:
                    event.set()
    
    def _start_event_listener(self):
        """
        Start an event listener worker for A17a events from S08.
        """
        try:
            with self.mq_lock:
                if self.mq_service:
                    mq = self.mq_service.clone()
            
            mq.declare_queue(self.events_queue)
            mq.register_callback(self.events_queue, self._handle_event)
            print(f"[S14] Event listener started on queue: {self.events_queue}")
            mq.start_consuming()
            
        except Exception as e:
            print(f"[S14] Event listener error: {e}")
            self._handle_connection_lost()
    
    def _handle_event(self, message: dict):
        """
        Handle incoming events from S08 (A17a).
        """
        try:
            event_type = message.get("event_type")
            params = message.get("params", {})
            event_id = message.get("id")
            
            # Validate event has required fields
            if not event_type or not params:
                self._record_invalid_event(message, "Missing event_type or params")
                return
            
            # Filter by partner_id
            partner_id = params.get("partner_id")
            if partner_id != self.partner_id:
                # Log warning but don't count as error
                print(f"[S14] Ignoring event for different partner: {partner_id}")
                return
            
            # Route to appropriate handler
            if event_type == "conversation_start_by_partner":
                self._handle_conversation_start(params)
            elif event_type == "conversation_changed_status_by_partner":
                self._handle_conversation_status_change(params)
            elif event_type == "conversation_satisfaction_change_by_partner":
                self._handle_satisfaction_change(params)
            else:
                self._record_invalid_event(message, f"Unknown event_type: {event_type}")
                
        except Exception as e:
            print(f"[S14] Error handling event: {e}")
            self._record_invalid_event(message, str(e))
    
    def _handle_conversation_start(self, params: dict):
        """
        Process conversation_start_by_partner event.
        """
        # Validate required fields
        required_fields = ["conversation_id", "partner_id", "started_at"]
        if not all(field in params for field in required_fields):
            self._record_invalid_event({"params": params}, "Missing required fields")
            return
        
        with self.conversations_lock:
            self.total_conversations += 1
            self.forwarding_conversations += 1
        
        with self.offload_lock:
            self.ai_failed_conversations += 1
        
        print(f"[S14] New conversation started: {params.get('conversation_id')}")
    
    def _handle_conversation_status_change(self, params: dict):
        """
        Process conversation_changed_status_by_partner event.
        """
        # Validate required fields
        required_fields = ["conversation_id", "partner_id", "old_status", "new_status", "updated_at"]
        if not all(field in params for field in required_fields):
            self._record_invalid_event({"params": params}, "Missing required fields")
            return
        
        old_status = params.get("old_status")
        new_status = params.get("new_status")
        
        status_counter_map = {
            "FORWARDING": "forwarding_conversations",
            "HUMAN_AGENT_TEXTING": "texting_conversations",
            "HUMAN_AGENT_CALLING": "calling_conversations"
        }
        
        if old_status not in status_counter_map or new_status not in status_counter_map:
            self._record_invalid_event({"params": params}, f"Invalid status: {old_status} -> {new_status}")
            return
        
        with self.conversations_lock:
            # Decrement old status counter
            old_counter = status_counter_map[old_status]
            current_value = getattr(self, old_counter)
            setattr(self, old_counter, max(0, current_value - 1))
            
            # Increment new status counter
            new_counter = status_counter_map[new_status]
            setattr(self, new_counter, getattr(self, new_counter) + 1)
        
        print(f"[S14] Conversation status changed: {params.get('conversation_id')} - {old_status} -> {new_status}")
    
    def _handle_satisfaction_change(self, params: dict):
        """
        Process conversation_satisfaction_change_by_partner event.
        """
        # Validate required fields
        required_fields = ["conversation_id", "partner_id", "new_satisfaction", "updated_at"]
        if not all(field in params for field in required_fields):
            self._record_invalid_event({"params": params}, "Missing required fields")
            return
        
        old_satisfaction = params.get("old_satisfaction")  # Can be None for new rating
        new_satisfaction = params.get("new_satisfaction")
        
        if not isinstance(new_satisfaction, int) or new_satisfaction < 1 or new_satisfaction > 5:
            self._record_invalid_event({"params": params}, f"Invalid new_satisfaction: {new_satisfaction}")
            return
        
        with self.satisfaction_lock:
            # Decrement old satisfaction counter if exists (rating changed)
            if old_satisfaction is not None:
                if isinstance(old_satisfaction, int) and 1 <= old_satisfaction <= 5:
                    old_counter = f"satisfaction_{old_satisfaction}"
                    current_value = getattr(self, old_counter)
                    setattr(self, old_counter, max(0, current_value - 1))
                else:
                    self.total_ratings += 1  # New rating
            else:
                self.total_ratings += 1  # New rating
            
            # Increment new satisfaction counter
            new_counter = f"satisfaction_{new_satisfaction}"
            setattr(self, new_counter, getattr(self, new_counter) + 1)
            
            # Recalculate average rating
            self._recalculate_average_rating()
        
        print(f"[S14] Satisfaction changed: {params.get('conversation_id')} - {old_satisfaction} -> {new_satisfaction}")
    
    def _recalculate_average_rating(self):
        """
        Recalculate average rating from satisfaction distribution.
        Must be called with satisfaction_lock held.
        """
        total = (
            self.satisfaction_1 + self.satisfaction_2 + 
            self.satisfaction_3 + self.satisfaction_4 + self.satisfaction_5
        )
        
        if total > 0:
            weighted_sum = (
                1 * self.satisfaction_1 +
                2 * self.satisfaction_2 +
                3 * self.satisfaction_3 +
                4 * self.satisfaction_4 +
                5 * self.satisfaction_5
            )
            self.average_rating = round(weighted_sum / total, 2)
            self.total_ratings = total
        else:
            self.average_rating = 0.0
            self.total_ratings = 0
    
    def _record_invalid_event(self, event: dict, reason: str):
        """
        Record an invalid event and increment counter.
        """
        print(f"[S14] Invalid event: {reason} - {json.dumps(event)}")
        
        with self.invalid_events_lock:
            self.invalid_events_counter += 1
            
            # Alert if threshold exceeded (50/hour would need tracking over time)
            if self.invalid_events_counter % 50 == 0:
                print(f"[S14] WARNING: Invalid events counter reached {self.invalid_events_counter}")
    
    def _reset_conversation_counters(self):
        """
        Reset all conversation counters to 0.
        """
        with self.conversations_lock:
            self.total_conversations = 0
            self.forwarding_conversations = 0
            self.texting_conversations = 0
            self.calling_conversations = 0
        
        with self.offload_lock:
            self.ai_failed_conversations = 0
            self.offloaded_conversations = 0
    
    def _reset_satisfaction_counters(self):
        """
        Reset all satisfaction counters to 0.
        """
        with self.satisfaction_lock:
            self.satisfaction_1 = 0
            self.satisfaction_2 = 0
            self.satisfaction_3 = 0
            self.satisfaction_4 = 0
            self.satisfaction_5 = 0
            self.total_ratings = 0
            self.average_rating = 0.0
    
    def _set_unhealthy(self):
        """
        Set service health status to unhealthy.
        """
        with self.health_lock:
            self.is_healthy = False
        print("[S14] Service marked as UNHEALTHY")
    
    def _set_healthy(self):
        """
        Set service health status to healthy.
        """
        with self.health_lock:
            self.is_healthy = True
        print("[S14] Service marked as HEALTHY")
    
    def _handle_connection_lost(self):
        """
        Handle RabbitMQ connection lost - attempt reconnection with exponential backoff.
        """
        self._set_unhealthy()
        
        backoff_times = [1, 2, 4, 8, 16, 32, 60]  # Max 60 seconds
        
        for attempt, backoff in enumerate(backoff_times):
            print(f"[S14] Attempting reconnection in {backoff} seconds (attempt {attempt + 1})")
            time.sleep(backoff)
            
            try:
                with self.mq_lock:
                    self.mq_service = MessageQueueService()
                    self.mq_service.declare_queue(self.events_queue)
                    self.mq_service.declare_queue(self.requests_queue)
                    self.mq_service.declare_queue(self.responses_queue)
                
                self._set_healthy()
                self._process_buffered_events()
                print("[S14] Reconnection successful")
                return
                
            except Exception as e:
                print(f"[S14] Reconnection failed: {e}")
        
        print("[S14] Max reconnection attempts reached")
    
    def _buffer_event(self, event: dict):
        """
        Buffer an event during disconnection.
        """
        with self.event_buffer_lock:
            if len(self.event_buffer) < self.max_event_buffer_size:
                self.event_buffer.append(event)
            else:
                print("[S14] Event buffer full, dropping event")
    
    def _process_buffered_events(self):
        """
        Process buffered events after reconnection.
        """
        with self.event_buffer_lock:
            events_to_process = self.event_buffer.copy()
            self.event_buffer.clear()
        
        for event in events_to_process:
            self._handle_event(event)
        
        print(f"[S14] Processed {len(events_to_process)} buffered events")
    
    # ========== HTTP API Methods (H30) ==========
    
    def get_conversations(self, from_date: Optional[str] = None, to_date: Optional[str] = None) -> dict:
        """
        H30.1: Get conversation statistics for this partner.
        """
        # If date filters specified, query S08 for filtered data
        if from_date or to_date:
            response = self._call_s08_method(
                method="get_partner_conversation_statistics",
                params={"partner_id": self.partner_id}
            )
            
            if response and response.get("result", {}).get("status") == "success":
                content = response["result"]["content"]
                return {
                    "status": "success",
                    "total_conversations": content.get("total_conversations", 0),
                    "texting_conversations": content.get("texting_conversations", 0),
                    "calling_conversations": content.get("calling_conversations", 0),
                    "from_date": from_date,
                    "to_date": to_date
                }
            
            elif response and response.get("result", {}).get("status") == "error":
                error_content = response["result"].get("content", "")
                return {"status": "error", "error_code": error_content}
            
            else:
                return {"status": "error", "error_code": "S08_UNAVAILABLE"}
        
        # Return cached data
        with self.conversations_lock:
            return {
                "status": "success",
                "total_conversations": self.total_conversations,
                "texting_conversations": self.texting_conversations,
                "calling_conversations": self.calling_conversations,
                "from_date": from_date,
                "to_date": to_date
            }
    
    def get_satisfaction_rate(self, from_date: Optional[str] = None, to_date: Optional[str] = None) -> dict:
        """
        H30.2: Get satisfaction distribution for this partner.
        """
        # If date filters specified, query S08 for filtered data
        if from_date or to_date:
            response = self._call_s08_method(
                method="get_partner_satisfaction_distribution",
                params={"partner_id": self.partner_id}
            )
            
            if response and response.get("result", {}).get("status") == "success":
                content = response["result"]["content"]
                
                sat_1 = content.get("satisfaction_1", 0)
                sat_2 = content.get("satisfaction_2", 0)
                sat_3 = content.get("satisfaction_3", 0)
                sat_4 = content.get("satisfaction_4", 0)
                sat_5 = content.get("satisfaction_5", 0)
                total = sat_1 + sat_2 + sat_3 + sat_4 + sat_5
                
                avg_rating = 0.0
                if total > 0:
                    avg_rating = round((1*sat_1 + 2*sat_2 + 3*sat_3 + 4*sat_4 + 5*sat_5) / total, 2)
                
                return {
                    "status": "success",
                    "total_conversations": total,
                    "satisfaction_distribution": {
                        "satisfaction_1": sat_1,
                        "satisfaction_2": sat_2,
                        "satisfaction_3": sat_3,
                        "satisfaction_4": sat_4,
                        "satisfaction_5": sat_5
                    },
                    "average_rating": avg_rating,
                    "from_date": from_date,
                    "to_date": to_date
                }
            
            elif response and response.get("result", {}).get("status") == "error":
                error_content = response["result"].get("content", "")
                
                if error_content == "NO_DATA_FOUND":
                    return {
                        "status": "success",
                        "total_conversations": 0,
                        "satisfaction_distribution": {
                            "satisfaction_1": 0,
                            "satisfaction_2": 0,
                            "satisfaction_3": 0,
                            "satisfaction_4": 0,
                            "satisfaction_5": 0
                        },
                        "average_rating": 0.0,
                        "from_date": from_date,
                        "to_date": to_date
                    }
                
                return {"status": "error", "error_code": error_content}
            
            else:
                return {"status": "error", "error_code": "S08_UNAVAILABLE"}
        
        # Return cached data
        with self.satisfaction_lock:
            return {
                "status": "success",
                "total_conversations": self.total_ratings,
                "satisfaction_distribution": {
                    "satisfaction_1": self.satisfaction_1,
                    "satisfaction_2": self.satisfaction_2,
                    "satisfaction_3": self.satisfaction_3,
                    "satisfaction_4": self.satisfaction_4,
                    "satisfaction_5": self.satisfaction_5
                },
                "average_rating": self.average_rating,
                "from_date": from_date,
                "to_date": to_date
            }
    
    def get_offload_rate(self, from_date: Optional[str] = None, to_date: Optional[str] = None) -> dict:
        """
        H30.3: Get offload rate for this partner.
        """
        # If date filters specified, query S08 for filtered data
        if from_date or to_date:
            response = self._call_s08_method(
                method="get_partner_conversation_statistics",
                params={"partner_id": self.partner_id}
            )
            
            if response and response.get("result", {}).get("status") == "success":
                content = response["result"]["content"]
                
                total = content.get("total_conversations", 0)
                ai_failed = content.get("ai_failed_conversations", 0)
                offloaded = content.get("offloaded_conversations", 0)
                
                offload_rate = 0.0
                if total > 0:
                    offload_rate = round((offloaded / total) * 100, 2)
                
                return {
                    "status": "success",
                    "total_conversations": total,
                    "ai_failed_conversation": ai_failed,
                    "offloaded_conversations": offloaded,
                    "offload_rate_percentage": offload_rate,
                    "from_date": from_date,
                    "to_date": to_date
                }
            
            elif response and response.get("result", {}).get("status") == "error":
                error_content = response["result"].get("content", "")
                return {"status": "error", "error_code": error_content}
            
            else:
                return {"status": "error", "error_code": "S08_UNAVAILABLE"}
        
        # Return cached data
        with self.conversations_lock:
            total = self.total_conversations
        
        with self.offload_lock:
            ai_failed = self.ai_failed_conversations
            offloaded = self.offloaded_conversations
        
        offload_rate = 0.0
        if total > 0:
            offload_rate = round((offloaded / total) * 100, 2)
        
        return {
            "status": "success",
            "total_conversations": total,
            "ai_failed_conversation": ai_failed,
            "offloaded_conversations": offloaded,
            "offload_rate_percentage": offload_rate,
            "from_date": from_date,
            "to_date": to_date
        }
    
    def get_health_status(self) -> dict:
        """
        Get service health status.
        """
        with self.health_lock:
            return {
                "status": "healthy" if self.is_healthy else "unhealthy",
                "partner_id": self.partner_id,
                "circuit_breaker_state": self.circuit_breaker.state
            }
