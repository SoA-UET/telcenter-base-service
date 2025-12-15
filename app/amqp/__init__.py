"""
RabbitMQ Handlers for S07 Partner Management Service.

AMQP APIs:
- A07: S08 (Metrics Service) -> S07 - get_partners (returns partner_id, name)
- A09a: S16 (Authorized Partner Gateway) -> S07 - get_partners (returns partner_id, base_url)
- A37: S18 (Forwarded Partner Selection) -> S07 - get_partners (returns partner_id, name)

Each API uses request/response queues pattern.
"""

import os
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..services.PartnerService import PartnerService
    from ..services.MessageQueueService import MessageQueueService


class PartnerRPCHandler:
    """
    Handles RPC-style messages for Partner Management Service.
    Routes method calls to PartnerService based on the 'method' field.
    """
    
    def __init__(self, partner_service: 'PartnerService', mq: 'MessageQueueService', response_queue_name: str, api_type: str):
        """
        Args:
            partner_service: The PartnerService instance
            mq: MessageQueueService instance for publishing responses
            response_queue_name: Queue name to publish responses to
            api_type: API type ('A07', 'A09a', 'A37') to determine response format
        """
        self.partner_service = partner_service
        self.mq = mq
        self.response_queue_name = response_queue_name
        self.api_type = api_type
        
        # Method routing map
        self.method_map = {
            "get_partners": self._handle_get_partners,
        }
    
    def handle_message(self, message: dict):
        """
        Process incoming RPC message and publish response.
        
        Message format:
        {
            "method": "get_partners",
            "id": "request-id"
        }
        """
        request_id = message.get("id")
        
        if request_id is None or not isinstance(request_id, str):
            print(f"[PartnerRPCHandler] Ignoring message without valid id: {message}")
            return
        
        result_status = "success"
        result_content = None
        
        try:
            result_content = self._dispatch_method(message)
        except Exception as e:
            result_status = "error"
            result_content = str(e)
            print(f"[PartnerRPCHandler] Error handling message: {e}")
        
        # Build and publish response
        response = {
            "id": request_id,
            "result": {
                "status": result_status,
                "content": result_content,
            }
        }
        
        self.mq.publish_message(self.response_queue_name, response)
    
    def _dispatch_method(self, message: dict):
        """Dispatch to appropriate method handler."""
        method_name = message.get("method", "")
        
        if not method_name:
            raise ValueError("Message missing 'method' field")
        
        handler = self.method_map.get(method_name)
        
        if handler is None:
            raise ValueError(f"Unknown method: {method_name}")
        
        return handler(message)
    
    def _handle_get_partners(self, message: dict):
        """
        Handle get_partners method.
        
        Returns different formats based on API type:
        - A07 & A37: [{"partner_id": "...", "name": "..."}]
        - A09a: [{"partner_id": "...", "base_url": "..."}]
        """
        if self.api_type == 'A09a':
            return self.partner_service.get_partners_with_base_urls()
        else:
            # A07 and A37 return same format
            return self.partner_service.get_partners_with_names()


class AMQPServer:
    """
    Server for handling RabbitMQ-based APIs.
    
    Manages multiple consumer threads for:
    - A07 (S08 -> S07)
    - A09a (S16 -> S07)
    - A37 (S18 -> S07)
    """
    
    def __init__(self, partner_service: 'PartnerService'):
        from ..services.MessageQueueService import MessageQueueService
        
        self.partner_service = partner_service
        self.mq_service = MessageQueueService()
        self.mq_lock = threading.Lock()
        self.threads: list[threading.Thread] = []
        self.num_threads = int(os.getenv('MQ_CONSUMER_THREADS', '4'))
        
        # Queue configurations from environment
        self.queue_configs = {
            'A07': {
                'request_queue': os.getenv('A07_REQUESTS_QUEUE', 'telcenter_a07_requests'),
                'response_queue': os.getenv('A07_RESPONSES_QUEUE', 'telcenter_a07_responses'),
            },
            'A09a': {
                'request_queue': os.getenv('A09A_REQUESTS_QUEUE', 'telcenter_a09a_requests'),
                'response_queue': os.getenv('A09A_RESPONSES_QUEUE', 'telcenter_a09a_responses'),
            },
            'A37': {
                'request_queue': os.getenv('A37_REQUESTS_QUEUE', 'telcenter_a37_requests'),
                'response_queue': os.getenv('A37_RESPONSES_QUEUE', 'telcenter_a37_responses'),
            },
        }
    
    def start(self):
        """Start consumer threads for all APIs."""
        print("[AMQPServer] Starting RabbitMQ consumers...")
        
        # Create threads for each API type, distributed by num_threads
        for api_type, config in self.queue_configs.items():
            # Each API gets at least 1 thread, or proportional to total threads
            threads_per_api = max(1, self.num_threads // len(self.queue_configs))
            
            for i in range(threads_per_api):
                thread = threading.Thread(
                    target=self._consume_api,
                    args=(api_type, config),
                    daemon=True,
                    name=f"AMQPConsumer-{api_type}-{i}"
                )
                self.threads.append(thread)
                thread.start()
                print(f"[AMQPServer] Started consumer thread {thread.name}")
        
        print(f"[AMQPServer] Started {len(self.threads)} consumer threads")
    
    def _consume_api(self, api_type: str, config: dict):
        """Consumer thread function for a specific API."""
        request_queue = config['request_queue']
        response_queue = config['response_queue']
        
        # Clone MQ connection for this thread
        with self.mq_lock:
            mq = self.mq_service.clone()
        
        # Declare queues
        mq.declare_queue(request_queue)
        mq.declare_queue(response_queue)
        
        # Create handler
        handler = PartnerRPCHandler(
            partner_service=self.partner_service,
            mq=mq,
            response_queue_name=response_queue,
            api_type=api_type
        )
        
        # Register callback and start consuming
        mq.register_callback(request_queue, handler.handle_message)
        
        print(f"[AMQPServer] {api_type} consumer ready on queue: {request_queue}")
        
        try:
            mq.start_consuming()
        except Exception as e:
            print(f"[AMQPServer] Consumer error for {api_type}: {e}")
    
    def wait(self):
        """Wait for all threads to complete."""
        for thread in self.threads:
            thread.join()
