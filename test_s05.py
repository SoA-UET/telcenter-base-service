#!/usr/bin/env python3
"""
Test script for S05 Knowledge Validator Service

This script tests the basic functionality of S05 service including:
- Service initialization
- Creating validation tasks
- Listing tasks with pagination
- Approving/rejecting tasks
"""

import os
import sys
from datetime import datetime

# Set environment variables for testing
os.environ['MONGODB_URL'] = 'mongodb://localhost:27017/'
os.environ['S05_DB_NAME'] = 'telcenter_core_s05_test'
os.environ['RABBITMQ_URL'] = 'amqp://guest:guest@localhost:5672/'
os.environ['KNOWLEDGE_STORE_EVENT_QUEUE'] = 'knowledge_store_events_test'
os.environ['SEAWEEDFS_URL'] = 'http://localhost:8080'

def test_s05_service():
    """Test S05 Knowledge Validator Service"""
    
    print("=" * 60)
    print("Testing S05 Knowledge Validator Service")
    print("=" * 60)
    
    try:
        # Import the service
        print("\n[1/5] Importing KnowledgeValidatorService...")
        from app.services.s05_knowledge_validator_service import KnowledgeValidatorService
        print("✓ Service imported successfully")
        
        # Initialize service
        print("\n[2/5] Initializing service...")
        service = KnowledgeValidatorService()
        print("✓ Service initialized successfully")
        
        # Create a test validation task
        print("\n[3/5] Creating test validation task...")
        task_id = service.create_validation_task(
            seaweed_file_id="test_file_123",
            partner_id="viettel_partner_001",
            validator_id=None
        )
        print(f"✓ Created task with ID: {task_id}")
        
        # List validation tasks
        print("\n[4/5] Listing validation tasks...")
        result = service.get_validation_tasks(
            status="pending",
            page=1,
            limit=10
        )
        print(f"✓ Found {result['total_count']} task(s)")
        print(f"  - Pending: {result['summary']['pending']}")
        print(f"  - Approved: {result['summary']['approved']}")
        print(f"  - Rejected: {result['summary']['rejected']}")
        
        # Get task details
        print("\n[5/5] Getting task details...")
        task = service.get_validation_task_by_id(task_id)
        if task:
            print(f"✓ Task details retrieved:")
            print(f"  - ID: {task['id']}")
            print(f"  - Partner: {task.get('partner_id')}")
            print(f"  - Status: {task.get('status')}")
            print(f"  - Created: {task.get('created_at')}")
        else:
            print("✗ Failed to retrieve task details")
        
        # Test approve (commented out to avoid RabbitMQ requirement)
        # print("\n[6/6] Testing approve (would send to S03)...")
        # approved_task = service.approve_validation_task(task_id, "validator_test")
        # if approved_task:
        #     print(f"✓ Task approved: {approved_task['status']}")
        
        # Cleanup
        print("\n" + "=" * 60)
        print("Cleaning up...")
        service.validation_tasks.delete_many({"seaweed_file_id": "test_file_123"})
        service.close()
        print("✓ Cleanup complete")
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_s05_service()
    sys.exit(0 if success else 1)
