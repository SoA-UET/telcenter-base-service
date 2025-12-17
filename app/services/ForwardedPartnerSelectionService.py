import json
import os
import threading
import uuid
from typing import Any
import requests
import google.generativeai as genai
from dotenv import load_dotenv

from .MessageQueueService import MessageQueueService

# Load environment variables
load_dotenv()


class ForwardedPartnerSelectionService:
    """
    S18 - Forwarded Partner Selection Service
    
    This service listens for `need_forwarding` events from S01,
    queries S07 for available partners, uses Gemini LLM to select
    the best partner based on conversation summary, and notifies
    S01 with the selection result.
    """
    
    def __init__(self) -> None:
        # Load configuration from environment
        self.rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
        
        # A35a - S01 to S18 (incoming events)
        self.a35a_queue_name = os.getenv("A35A_QUEUE_NAME", "s01_s18_events")
        
        # A35b - S18 to S01 (outgoing events)
        self.a35b_queue_name = os.getenv("A35B_QUEUE_NAME", "s18_s01_events")
        
        # A37 - S18 to S07 (RabbitMQ method calls)
        self.a37_request_queue = os.getenv("A37_REQUEST_QUEUE", "s18_s07_requests")
        self.a37_response_queue = os.getenv("A37_RESPONSE_QUEUE", "s18_s07_responses")
        
        # Gemini API configuration
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY must be set in environment variables")
        genai.configure(api_key=gemini_api_key)
        self.gemini_model = genai.GenerativeModel("gemini-pro")
        
        # MessageQueue services
        self.mq_service = MessageQueueService(self.rabbitmq_url)
        self.mq_lock = threading.Lock()
        
        # Threading configuration
        self.num_threads = int(os.getenv("S18_NUM_THREADS", "4"))
        self.threads: list[threading.Thread] = []
        
        # Pending A37 responses (for request-response pattern)
        self.pending_a37_requests: dict[str, dict] = {}
        self.pending_a37_lock = threading.Lock()
    
    def start(self):
        """Start the service with multiple consumer threads"""
        print("[S18] Starting Forwarded Partner Selection Service...")
        
        # Start consumer threads for A35a events
        self.threads = [
            threading.Thread(target=self._consume_a35a_events, daemon=True)
            for _ in range(self.num_threads)
        ]
        
        # Start a single thread for A37 responses
        self.threads.append(
            threading.Thread(target=self._consume_a37_responses, daemon=True)
        )
        
        for t in self.threads:
            t.start()
        
        print(f"[S18] Service started with {self.num_threads} consumer threads")
    
    def wait(self):
        """Wait for all threads to complete"""
        for t in self.threads:
            t.join()
    
    def _consume_a35a_events(self):
        """Consumer thread for A35a events from S01"""
        with self.mq_lock:
            mq = self.mq_service.clone()
        
        mq.declare_queue(self.a35a_queue_name)
        mq.register_callback(self.a35a_queue_name, self._handle_a35a_event)
        mq.start_consuming()
    
    def _consume_a37_responses(self):
        """Consumer thread for A37 responses from S07"""
        with self.mq_lock:
            mq = self.mq_service.clone()
        
        mq.declare_queue(self.a37_response_queue)
        mq.register_callback(self.a37_response_queue, self._handle_a37_response)
        mq.start_consuming()
    
    def _handle_a35a_event(self, message: dict):
        """Handle incoming A35a events from S01"""
        try:
            event = message.get("event")
            
            if event == "need_forwarding":
                self._handle_need_forwarding_event(message)
            else:
                print(f"[S18] Unknown event type: {event}")
        except Exception as e:
            print(f"[S18] Error handling A35a event: {e}")
    
    def _handle_need_forwarding_event(self, message: dict):
        """
        Handle the need_forwarding event from S01.
        
        Logic flow:
        1. Extract conversation data
        2. Query S07 for available partners via A37
        3. Call Gemini LLM to select best partner
        4. Send result back to S01 via A35b
        """
        try:
            content = message.get("content", {})
            conversation = content.get("conversation", {})
            conversation_id = conversation.get("id")
            conversation_summary = conversation.get("summary", "")
            
            if not conversation_id:
                print("[S18] Missing conversation_id in need_forwarding event")
                return
            
            print(f"[S18] Processing need_forwarding for conversation: {conversation_id}")
            
            # Step 1: Query S07 for available partners
            partners = self._query_partners_from_s07()
            
            if not partners:
                self._send_selection_error(
                    conversation_id,
                    "No partners available"
                )
                return
            
            # Step 2: Select best partner using Gemini LLM
            selected_partner = self._select_partner_with_gemini(
                partners,
                conversation_summary
            )
            
            if selected_partner:
                # Success: send selection result
                self._send_selection_success(
                    conversation_id,
                    selected_partner["partner_id"],
                    selected_partner["name"]
                )
            else:
                # LLM returned IMPOSSIBLE or couldn't select
                self._send_selection_success(
                    conversation_id,
                    None,
                    None
                )
        
        except Exception as e:
            print(f"[S18] Error in need_forwarding handler: {e}")
            conversation_id = message.get("content", {}).get("conversation", {}).get("id")
            if conversation_id:
                self._send_selection_error(conversation_id, str(e))
    
    def _query_partners_from_s07(self) -> list[dict]:
        """
        Query S07 for available partners via A37 RabbitMQ API.
        
        Returns list of partners: [{"partner_id": "...", "name": "..."}, ...]
        """
        try:
            request_id = str(uuid.uuid4())
            
            # Prepare request
            request_message = {
                "method": "get_partners",
                "id": request_id
            }
            
            # Create a threading event to wait for response
            response_event = threading.Event()
            response_data = {"result": None}
            
            # Register this request as pending
            with self.pending_a37_lock:
                self.pending_a37_requests[request_id] = {
                    "event": response_event,
                    "data": response_data
                }
            
            # Send request to S07
            with self.mq_lock:
                mq = self.mq_service.clone()
            mq.declare_queue(self.a37_request_queue)
            mq.publish_message(self.a37_request_queue, request_message)
            
            print(f"[S18] Sent A37 request to S07: {request_id}")
            
            # Wait for response (with timeout)
            timeout = 30  # seconds
            if not response_event.wait(timeout):
                raise TimeoutError(f"Timeout waiting for A37 response from S07")
            
            # Process response
            result = response_data["result"]
            if not result:
                raise ValueError("No response received from S07")
            
            status = result.get("status")
            content = result.get("content")
            
            if status == "error":
                raise Exception(f"S07 returned error: {content}")
            
            if status == "success":
                return content if isinstance(content, list) else []
            
            raise ValueError(f"Unknown response status from S07: {status}")
        
        except Exception as e:
            print(f"[S18] Error querying S07 for partners: {e}")
            raise
    
    def _handle_a37_response(self, message: dict):
        """Handle A37 response from S07"""
        try:
            request_id = message.get("id")
            result = message.get("result")
            
            if not request_id:
                print("[S18] Received A37 response without request ID")
                return
            
            # Find the pending request
            with self.pending_a37_lock:
                pending = self.pending_a37_requests.get(request_id)
                if not pending:
                    print(f"[S18] Received A37 response for unknown request: {request_id}")
                    return
                
                # Store the result and signal the waiting thread
                pending["data"]["result"] = result
                pending["event"].set()
                
                # Clean up
                del self.pending_a37_requests[request_id]
            
            print(f"[S18] Processed A37 response: {request_id}")
        
        except Exception as e:
            print(f"[S18] Error handling A37 response: {e}")
    
    def _select_partner_with_gemini(
        self,
        partners: list[dict],
        conversation_summary: str
    ) -> dict | None:
        """
        Use Gemini LLM to select the best partner for the conversation.
        
        Returns: {"partner_id": "...", "name": "..."} or None if IMPOSSIBLE
        """
        try:
            # Prepare partner name list for prompt
            partner_names = [p.get("name", "") for p in partners if p.get("name")]
            partner_name_list = "\n".join(partner_names)
            
            # Construct prompt
            prompt = f"""Bạn là một tư vấn viên trung gian,
giúp kết nối khách hàng với các đối tác viễn thông.
Dựa trên tóm tắt cuộc hội thoại sau đây,
hãy chọn đối tác phù hợp nhất để chuyển tiếp cuộc hội thoại.

Định dạng phản hồi của bạn: chỉ là tên đối tác, không có gì khác.
Nếu không thể chọn đối tác phù hợp dựa vào ngữ cảnh
đã cho, trả lời "IMPOSSIBLE".

Danh sách các đối tác bao gồm:
---
{partner_name_list}
---

Tóm tắt cuộc hội thoại:
---
{conversation_summary}
---

Câu trả lời của bạn:"""
            
            print(f"[S18] Calling Gemini LLM for partner selection...")
            
            # Call Gemini API
            response = self.gemini_model.generate_content(prompt)
            llm_response = response.text.strip()
            
            print(f"[S18] Gemini response: {llm_response}")
            
            # Check if LLM returned IMPOSSIBLE
            if llm_response == "IMPOSSIBLE":
                print("[S18] LLM could not select a suitable partner")
                return None
            
            # Look up the selected partner by name
            selected_partner = None
            for partner in partners:
                if partner.get("name", "").lower() == llm_response.lower():
                    selected_partner = partner
                    break
            
            if not selected_partner:
                print(f"[S18] Warning: LLM selected '{llm_response}' but no matching partner found")
                return None
            
            print(f"[S18] Selected partner: {selected_partner['name']} (ID: {selected_partner['partner_id']})")
            return selected_partner
        
        except Exception as e:
            print(f"[S18] Error calling Gemini LLM: {e}")
            raise
    
    def _send_selection_success(
        self,
        conversation_id: str,
        partner_id: str | None,
        partner_name: str | None
    ):
        """Send A35b event: forwarded_partner_selection_finished with success"""
        try:
            selection = None
            if partner_id and partner_name:
                selection = {
                    "partner_id": partner_id,
                    "partner_name": partner_name
                }
            
            message = {
                "event": "forwarded_partner_selection_finished",
                "content": {
                    "conversation_id": conversation_id,
                    "status": "success",
                    "message": None,
                    "selection": selection
                }
            }
            
            with self.mq_lock:
                mq = self.mq_service.clone()
            mq.declare_queue(self.a35b_queue_name)
            mq.publish_message(self.a35b_queue_name, message)
            
            print(f"[S18] Sent success notification for conversation: {conversation_id}")
        
        except Exception as e:
            print(f"[S18] Error sending success notification: {e}")
    
    def _send_selection_error(self, conversation_id: str, error_message: str):
        """Send A35b event: forwarded_partner_selection_finished with error"""
        try:
            message = {
                "event": "forwarded_partner_selection_finished",
                "content": {
                    "conversation_id": conversation_id,
                    "status": "error",
                    "message": error_message,
                    "selection": None
                }
            }
            
            with self.mq_lock:
                mq = self.mq_service.clone()
            mq.declare_queue(self.a35b_queue_name)
            mq.publish_message(self.a35b_queue_name, message)
            
            print(f"[S18] Sent error notification for conversation: {conversation_id}")
        
        except Exception as e:
            print(f"[S18] Error sending error notification: {e}")
