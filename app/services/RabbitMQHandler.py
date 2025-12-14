import os
import threading
from ..services.MessageQueueService import MessageQueueService
from ..services.CustomerIdentityService import CustomerIdentityService
from ..services.LoggingService import LoggingService

class RabbitMQHandler:
    """
    Handler for RabbitMQ communications.
    Manages A04a Event (customer_registered) and A04b Method (get_customers_count).
    """
    
    def __init__(self, customer_service: CustomerIdentityService, 
                 logging_service: LoggingService):
        self.customer_service = customer_service
        self.logging_service = logging_service
        
        # Queue names from environment
        self.events_queue = os.getenv("S04_EVENTS_QUEUE", "s04_events_queue")
        self.requests_queue = os.getenv("S08_S04_REQUESTS_QUEUE", "s08_s04_requests_queue")
        self.responses_queue = os.getenv("S08_S04_RESPONSES_QUEUE", "s08_s04_responses_queue")
        
        # MessageQueueService instances (one per thread)
        self.mq_service = MessageQueueService()
        
        # Declare queues
        self.mq_service.declare_queue(self.events_queue)
        self.mq_service.declare_queue(self.requests_queue)
        self.mq_service.declare_queue(self.responses_queue)
        
        self.logging_service.log_info("RabbitMQ queues declared", {
            "events_queue": self.events_queue,
            "requests_queue": self.requests_queue,
            "responses_queue": self.responses_queue
        })
    
    def publish_customer_registered_event(self, customer_id: str):
        """
        Publish A04a Event: customer_registered to S08 Metrics Service.
        
        Args:
            customer_id: The ID of the newly registered customer
        """
        try:
            event_data = {
                "event_type": "customer_registered",
                "params": {
                    "customer_id": customer_id
                },
                "id": customer_id  # Using customer_id as event id for uniqueness
            }
            
            self.mq_service.publish_message(self.events_queue, event_data)
            
            self.logging_service.log_info(
                "Published customer_registered event",
                {"customer_id": customer_id, "queue": self.events_queue}
            )
            
        except Exception as e:
            self.logging_service.log_error(
                "Error publishing customer_registered event",
                {"error": str(e), "customer_id": customer_id}
            )
    
    def handle_method_request(self, message: dict):
        """
        Handle A04b Method requests from S08 Metrics Service.
        Currently supports: get_customers_count
        
        Args:
            message: Request message with 'method' and 'id' fields
        """
        try:
            method = message.get("method")
            request_id = message.get("id")
            
            self.logging_service.log_info(
                "Received method request",
                {"method": method, "id": request_id}
            )
            
            if method == "get_customers_count":
                # Get customers count
                try:
                    count = self.customer_service.get_customers_count()
                    
                    response = {
                        "id": request_id,
                        "result": {
                            "status": "success",
                            "content": count
                        }
                    }
                    
                except Exception as e:
                    response = {
                        "id": request_id,
                        "result": {
                            "status": "error",
                            "content": str(e)
                        }
                    }
                    
                    self.logging_service.log_error(
                        "Error processing get_customers_count",
                        {"error": str(e)}
                    )
                
                # Send response
                self.mq_service.publish_message(self.responses_queue, response)
                
                self.logging_service.log_info(
                    "Sent method response",
                    {"method": method, "id": request_id, "status": response["result"]["status"]}
                )
            else:
                # Unknown method
                response = {
                    "id": request_id,
                    "result": {
                        "status": "error",
                        "content": f"Unknown method: {method}"
                    }
                }
                
                self.mq_service.publish_message(self.responses_queue, response)
                
                self.logging_service.log_warning(
                    "Unknown method requested",
                    {"method": method, "id": request_id}
                )
                
        except Exception as e:
            self.logging_service.log_error(
                "Error handling method request",
                {"error": str(e), "message": str(message)}
            )
    
    def start_consuming_requests(self):
        """
        Start consuming method requests from S08.
        This should be run in a separate thread.
        """
        try:
            # Create new MessageQueueService for this thread
            mq = MessageQueueService()
            mq.declare_queue(self.requests_queue)
            
            # Register callback
            mq.register_callback(self.requests_queue, self.handle_method_request)
            
            self.logging_service.log_info(
                "Started consuming method requests",
                {"queue": self.requests_queue}
            )
            
            # Start consuming (blocking)
            mq.start_consuming()
            
        except Exception as e:
            self.logging_service.log_error(
                "Error in request consumer thread",
                {"error": str(e)}
            )
    
    def start_request_consumer_thread(self):
        """
        Start the request consumer in a background thread.
        """
        consumer_thread = threading.Thread(
            target=self.start_consuming_requests,
            daemon=True,
            name="RabbitMQ-Request-Consumer"
        )
        consumer_thread.start()
        
        self.logging_service.log_info("RabbitMQ request consumer thread started")
        
        return consumer_thread
