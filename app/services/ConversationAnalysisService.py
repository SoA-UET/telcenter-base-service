import json
import os
import threading
import math
from typing import Any
import requests
import google.generativeai as genai
from dotenv import load_dotenv

from .MessageQueueService import MessageQueueService

# Load environment variables
load_dotenv()


class ConversationAnalysisService:
    """
    S19 - Conversation Analysis Service
    
    This service listens for events from S01 (new_message, rating_changed),
    analyzes message sentiment via S19b, updates customer satisfaction scores,
    and rewrites conversation summaries using Gemini LLM.
    """
    
    def __init__(self) -> None:
        # Load configuration from environment
        self.rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
        
        # A36a - S01 to S19 (incoming events)
        self.a36a_queue_name = os.getenv("A36A_QUEUE_NAME", "s01_s19_events")
        
        # A36b - S19 to S01 (outgoing events)
        self.a36b_queue_name = os.getenv("A36B_QUEUE_NAME", "s19_s01_events")
        
        # S19b Sentiment Analysis Service HTTP API
        self.s19b_base_url = os.getenv("S19B_BASE_URL", "http://localhost:8135")
        
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
        self.num_threads = int(os.getenv("S19_NUM_THREADS", "4"))
        self.threads: list[threading.Thread] = []
    
    def start(self):
        """Start the service with multiple consumer threads"""
        print("[S19] Starting Conversation Analysis Service...")
        
        # Start consumer threads for A36a events
        self.threads = [
            threading.Thread(target=self._consume_a36a_events, daemon=True)
            for _ in range(self.num_threads)
        ]
        
        for t in self.threads:
            t.start()
        
        print(f"[S19] Service started with {self.num_threads} consumer threads")
    
    def wait(self):
        """Wait for all threads to complete"""
        for t in self.threads:
            t.join()
    
    def _consume_a36a_events(self):
        """Consumer thread for A36a events from S01"""
        with self.mq_lock:
            mq = self.mq_service.clone()
        
        mq.declare_queue(self.a36a_queue_name)
        mq.register_callback(self.a36a_queue_name, self._handle_a36a_event)
        mq.start_consuming()
    
    def _handle_a36a_event(self, message: dict):
        """Handle incoming A36a events from S01"""
        try:
            event = message.get("event")
            
            if event == "new_message":
                self._handle_new_message_event(message)
            elif event == "rating_changed":
                self._handle_rating_changed_event(message)
            else:
                print(f"[S19] Unknown event type: {event}")
        except Exception as e:
            print(f"[S19] Error handling A36a event: {e}")
    
    def _handle_new_message_event(self, message: dict):
        """
        Handle the new_message event from S01.
        
        Flow:
        1. Get sentiment analysis from S19b
        2. Send update_message_emotion to S01
        3. Compute new customer satisfaction score
        4. Send update_customer_satisfaction to S01
        5. Rewrite conversation summary
        6. Send update_conversation_summary to S01
        """
        try:
            content = message.get("content", {})
            msg_data = content.get("message", {})
            conv_data = content.get("conversation", {})
            
            message_id = msg_data.get("id")
            message_content = msg_data.get("content", "")
            sender_type = msg_data.get("sender_type", "")
            
            conversation_id = conv_data.get("id")
            current_satisfaction = conv_data.get("customer_satisfaction", 3)
            current_summary = conv_data.get("summary", "")
            
            if not message_id or not conversation_id:
                print("[S19] Missing message_id or conversation_id in new_message event")
                return
            
            print(f"[S19] Processing new_message: {message_id} in conversation: {conversation_id}")
            
            # Step 1: Get sentiment analysis from S19b
            sentiment = self._get_sentiment_from_s19b(message_content)
            
            # Step 2: Send update_message_emotion to S01
            self._send_update_message_emotion(message_id, sentiment)
            
            # Step 3: Compute new customer satisfaction score
            new_satisfaction = self._compute_customer_satisfaction(
                current_satisfaction,
                sentiment
            )
            
            # Step 4: Send update_customer_satisfaction to S01
            self._send_update_customer_satisfaction(conversation_id, new_satisfaction)
            
            # Step 5: Rewrite conversation summary
            new_summary = self._rewrite_conversation_summary(
                current_summary,
                message_content,
                sender_type
            )
            
            # Step 6: Send update_conversation_summary to S01
            self._send_update_conversation_summary(conversation_id, new_summary)
            
            print(f"[S19] Completed processing new_message: {message_id}")
        
        except Exception as e:
            print(f"[S19] Error in new_message handler: {e}")
    
    def _handle_rating_changed_event(self, message: dict):
        """
        Handle the rating_changed event from S01.
        
        Flow:
        1. Extract new rating
        2. Send update_customer_satisfaction to S01 (score = rating)
        """
        try:
            content = message.get("content", {})
            conversation_id = content.get("conversation_id")
            rating_data = content.get("rating", {})
            new_rating = rating_data.get("new")
            
            if not conversation_id or new_rating is None:
                print("[S19] Missing conversation_id or new rating in rating_changed event")
                return
            
            print(f"[S19] Processing rating_changed for conversation: {conversation_id}, new rating: {new_rating}")
            
            # New customer satisfaction score equals the new rating
            self._send_update_customer_satisfaction(conversation_id, new_rating)
            
            print(f"[S19] Completed processing rating_changed for conversation: {conversation_id}")
        
        except Exception as e:
            print(f"[S19] Error in rating_changed handler: {e}")
    
    def _get_sentiment_from_s19b(self, text: str) -> str:
        """
        Call S19b HTTP API to get sentiment analysis.
        
        Returns: "Positive", "Negative", or "Neutral"
        """
        try:
            url = f"{self.s19b_base_url}/v1/infer"
            headers = {"Content-Type": "text/plain"}
            
            response = requests.post(url, data=text.encode('utf-8'), headers=headers)
            
            if response.status_code == 200:
                sentiment = response.text.strip()
                print(f"[S19] S19b sentiment analysis result: {sentiment}")
                return sentiment
            else:
                error_msg = response.text
                print(f"[S19] S19b returned error: {response.status_code} - {error_msg}")
                return "Neutral"  # Default to Neutral on error
        
        except Exception as e:
            print(f"[S19] Error calling S19b: {e}")
            return "Neutral"  # Default to Neutral on error
    
    def _compute_customer_satisfaction(self, curr_score: float, sentiment: str) -> int:
        """
        Compute new customer satisfaction score based on current score and sentiment.
        
        Formula:
        - if sentiment is Negative: new_score = floor(0.5 * (curr_score + 1))
        - if sentiment is Positive: new_score = ceil(0.5 * (curr_score + 5))
        - if sentiment is Neutral: new_score = max(curr_score, ceil(0.5 * (curr_score + 3)))
        
        Score ranges from 1 to 5, inclusive.
        """
        if sentiment == "Negative":
            new_score = math.floor(0.5 * (curr_score + 1))
        elif sentiment == "Positive":
            new_score = math.ceil(0.5 * (curr_score + 5))
        else:  # Neutral
            new_score = max(curr_score, math.ceil(0.5 * (curr_score + 3)))
        
        # Ensure score is within valid range
        new_score = max(1, min(5, int(new_score)))
        
        print(f"[S19] Customer satisfaction: {curr_score} -> {new_score} (sentiment: {sentiment})")
        return new_score
    
    def _rewrite_conversation_summary(
        self,
        current_summary: str,
        message_content: str,
        sender_type: str
    ) -> str:
        """
        Rewrite conversation summary based on new message.
        
        - If sender_type is CUSTOMER: append message to summary directly
        - Otherwise: use Gemini LLM to rewrite the entire summary
        """
        try:
            if sender_type == "CUSTOMER":
                # Simply append customer message
                new_summary = current_summary + f"\nKhách hàng: {message_content}\n"
                print(f"[S19] Appended customer message to summary")
                return new_summary
            else:
                # Use Gemini LLM to rewrite summary
                full_conversation = current_summary + f"\n{sender_type}: {message_content}\n"
                
                prompt = f"""Tóm tắt đoạn hội thoại sau đây giữa khách hàng và đại lý tư vấn viễn thông.
Bản tóm tắt phải ngắn gọn, súc tích, đầy đủ ý chính, và bằng tiếng Việt.
Đoạn hội thoại:

{full_conversation}"""
                
                print(f"[S19] Calling Gemini LLM to rewrite summary...")
                response = self.gemini_model.generate_content(prompt)
                new_summary = response.text.strip()
                
                print(f"[S19] Summary rewritten by Gemini")
                return new_summary
        
        except Exception as e:
            print(f"[S19] Error rewriting summary: {e}")
            # Fallback: just append the message
            return current_summary + f"\n{sender_type}: {message_content}\n"
    
    def _send_update_message_emotion(self, message_id: str, emotion: str):
        """Send A36b event: update_message_emotion"""
        try:
            event_message = {
                "event": "update_message_emotion",
                "content": {
                    "message_id": message_id,
                    "emotion": emotion
                }
            }
            
            with self.mq_lock:
                mq = self.mq_service.clone()
            mq.declare_queue(self.a36b_queue_name)
            mq.publish_message(self.a36b_queue_name, event_message)
            
            print(f"[S19] Sent update_message_emotion for message: {message_id}")
        
        except Exception as e:
            print(f"[S19] Error sending update_message_emotion: {e}")
    
    def _send_update_customer_satisfaction(self, conversation_id: str, satisfaction: int):
        """Send A36b event: update_customer_satisfaction"""
        try:
            event_message = {
                "event": "update_customer_satisfaction",
                "content": {
                    "conversation_id": conversation_id,
                    "customer_satisfaction": satisfaction
                }
            }
            
            with self.mq_lock:
                mq = self.mq_service.clone()
            mq.declare_queue(self.a36b_queue_name)
            mq.publish_message(self.a36b_queue_name, event_message)
            
            print(f"[S19] Sent update_customer_satisfaction for conversation: {conversation_id}")
        
        except Exception as e:
            print(f"[S19] Error sending update_customer_satisfaction: {e}")
    
    def _send_update_conversation_summary(self, conversation_id: str, summary: str):
        """Send A36b event: update_conversation_summary"""
        try:
            event_message = {
                "event": "update_conversation_summary",
                "content": {
                    "conversation_id": conversation_id,
                    "summary": summary
                }
            }
            
            with self.mq_lock:
                mq = self.mq_service.clone()
            mq.declare_queue(self.a36b_queue_name)
            mq.publish_message(self.a36b_queue_name, event_message)
            
            print(f"[S19] Sent update_conversation_summary for conversation: {conversation_id}")
        
        except Exception as e:
            print(f"[S19] Error sending update_conversation_summary: {e}")
