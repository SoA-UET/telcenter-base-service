# API Flow Diagrams - S05 Knowledge Validator Service

## Flow 1: List Partner Updates (H22 - GET /api/v1/partner-updates)

```
┌──────────────┐
│ Core Portal  │
│ (Frontend)   │
└──────┬───────┘
       │
       │ GET /api/v1/partner-updates
       │ ?status=pending&pageNumber=1&pageSize=20
       │ Authorization: Bearer <JWT>
       ▼
┌─────────────────────────────────────────┐
│ S05 - partner_updates.py Controller     │
│                                         │
│ 1. verify_jwt()                         │
│    └─> Extract validator_id from token │
│                                         │
│ 2. Parse query params                   │
│    - status, partner_id                 │
│    - pageNumber, pageSize               │
└──────┬──────────────────────────────────┘
       │
       │ service.get_validation_tasks()
       ▼
┌─────────────────────────────────────────┐
│ KnowledgeValidatorService               │
│                                         │
│ 1. Build MongoDB query filter           │
│ 2. Get total_count                      │
│ 3. Get summary stats (pending/approved) │
│ 4. Paginate & fetch tasks               │
│ 5. Sort by created_at DESC              │
└──────┬──────────────────────────────────┘
       │
       │ MongoDB query
       ▼
┌─────────────────┐
│ MongoDB         │
│ validation_tasks│
│ collection      │
└──────┬──────────┘
       │
       │ Returns: tasks array
       ▼
┌─────────────────────────────────────────┐
│ Response (HTTP 200)                     │
│ {                                       │
│   "status": "success",                  │
│   "total_count": 150,                   │
│   "page": 1,                            │
│   "limit": 20,                          │
│   "total_pages": 8,                     │
│   "updates": [...],                     │
│   "summary": {                          │
│     "total": 150,                       │
│     "pending": 25,                      │
│     "approved": 100,                    │
│     "rejected": 25                      │
│   }                                     │
│ }                                       │
└─────────────────────────────────────────┘
```

## Flow 2: Get Update Details (H22 - GET /api/v1/partner-updates/{id})

```
┌──────────────┐
│ Core Portal  │
└──────┬───────┘
       │
       │ GET /api/v1/partner-updates/{update_id}
       │ Authorization: Bearer <JWT>
       ▼
┌─────────────────────────────────────────┐
│ S05 Controller                          │
│ 1. verify_jwt()                         │
│ 2. Extract update_id from URL           │
└──────┬──────────────────────────────────┘
       │
       │ service.get_validation_task_by_id(update_id)
       ▼
┌─────────────────────────────────────────┐
│ KnowledgeValidatorService               │
│                                         │
│ 1. Convert update_id to ObjectId        │
│ 2. Find task in MongoDB                 │
└──────┬──────────────────────────────────┘
       │
       │ MongoDB findOne
       ▼
┌─────────────────┐
│ MongoDB         │
│ Find task by _id│
└──────┬──────────┘
       │
       │ Returns: task document
       ▼
┌─────────────────────────────────────────┐
│ KnowledgeValidatorService               │
│                                         │
│ 3. Get seaweed_file_id from task        │
│ 4. _fetch_from_seaweedfs(file_id)       │
└──────┬──────────────────────────────────┘
       │
       │ HTTP GET {SEAWEEDFS_URL}/{file_id}
       ▼
┌─────────────────┐
│ SeaweedFS       │
│ File Storage    │
└──────┬──────────┘
       │
       │ Returns: JSON content
       │ { "faqs": [...], "packages": [...] }
       ▼
┌─────────────────────────────────────────┐
│ KnowledgeValidatorService               │
│                                         │
│ 5. Merge task data + content            │
│ 6. Return complete task                 │
└──────┬──────────────────────────────────┘
       │
       │
       ▼
┌─────────────────────────────────────────┐
│ Response (HTTP 200)                     │
│ {                                       │
│   "status": "success",                  │
│   "update": {                           │
│     "id": "...",                        │
│     "partner_id": "viettel_partner_001",│
│     "status": "pending",                │
│     "faqs": [...],                      │
│     "packages": [...]                   │
│   }                                     │
│ }                                       │
└─────────────────────────────────────────┘
```

## Flow 3: Approve Update (H22 + A08 Integration)

```
┌──────────────┐
│ Core Portal  │
│ (User clicks │
│  "Approve")  │
└──────┬───────┘
       │
       │ POST /api/v1/partner-updates/{id}/approve
       │ Authorization: Bearer <JWT>
       │ Body: {}
       ▼
┌─────────────────────────────────────────┐
│ S05 Controller                          │
│                                         │
│ 1. verify_jwt()                         │
│    └─> validator_id = "user_123"       │
│                                         │
│ 2. Call service.approve_validation_task │
│    (update_id, validator_id)            │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ KnowledgeValidatorService               │
│                                         │
│ 1. Find task by ObjectId                │
│ 2. Check status == "pending"            │
└──────┬──────────────────────────────────┘
       │
       │ MongoDB findOne
       ▼
┌─────────────────┐
│ MongoDB         │
│ Get task        │
└──────┬──────────┘
       │
       │ Returns: task (status=pending)
       ▼
┌─────────────────────────────────────────┐
│ KnowledgeValidatorService               │
│                                         │
│ 3. Thread-safe update with Lock:        │
│    - status = "approved"                │
│    - validator_id = "user_123"          │
│    - validated_at = now()               │
└──────┬──────────────────────────────────┘
       │
       │ MongoDB updateOne (atomic)
       ▼
┌─────────────────┐
│ MongoDB         │
│ Update task     │
└──────┬──────────┘
       │
       │ Success
       ▼
┌─────────────────────────────────────────┐
│ KnowledgeValidatorService               │
│                                         │
│ 4. Start background thread:             │
│    send_to_s03()                        │
│                                         │
│    def send_to_s03():                   │
│      event = {                          │
│        "event": "store_validated_...",  │
│        "data": {                        │
│          "partner_id": "...",           │
│          "seaweed_file_id": "...",      │
│          "validated_at": "..."          │
│        }                                │
│      }                                  │
│      mq_service.publish_message(        │
│        queue, event                     │
│      )                                  │
└──────┬──────────────────────────────────┘
       │
       │ (Background thread)
       │ Publish to RabbitMQ
       ▼
┌─────────────────────────────────────────┐
│ RabbitMQ                                │
│ Queue: knowledge_store_events           │
│                                         │
│ Message: {                              │
│   "event": "store_validated_knowledge", │
│   "data": {...}                         │
│ }                                       │
└──────┬──────────────────────────────────┘
       │
       │ S03 consumes event
       ▼
┌─────────────────┐
│ S03 Knowledge   │
│ Service         │
│                 │
│ 1. Get event    │
│ 2. Download     │
│    from         │
│    SeaweedFS    │
│ 3. Store in DB  │
└─────────────────┘

       │
       │ (Meanwhile, main thread continues)
       │
       ▼
┌─────────────────────────────────────────┐
│ Response (HTTP 200) - Immediate         │
│ {                                       │
│   "status": "success",                  │
│   "update": {                           │
│     "id": "...",                        │
│     "status": "approved",               │
│     "validator_id": "user_123",         │
│     "validated_at": "2025-12-15..."     │
│   }                                     │
│ }                                       │
└─────────────────────────────────────────┘
       │
       ▼
┌──────────────┐
│ Core Portal  │
│ Shows success│
└──────────────┘
```

## Flow 4: Reject Update (H22)

```
┌──────────────┐
│ Core Portal  │
│ (User clicks │
│  "Reject")   │
└──────┬───────┘
       │
       │ POST /api/v1/partner-updates/{id}/reject
       │ Authorization: Bearer <JWT>
       │ Body: {}
       ▼
┌─────────────────────────────────────────┐
│ S05 Controller                          │
│                                         │
│ 1. verify_jwt()                         │
│    └─> validator_id = "user_123"       │
│                                         │
│ 2. Call service.reject_validation_task  │
│    (update_id, validator_id)            │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ KnowledgeValidatorService               │
│                                         │
│ 1. Find task by ObjectId                │
│ 2. Check status == "pending"            │
│ 3. Thread-safe update:                  │
│    - status = "rejected"                │
│    - validator_id = "user_123"          │
│    - validated_at = now()               │
└──────┬──────────────────────────────────┘
       │
       │ MongoDB updateOne
       ▼
┌─────────────────┐
│ MongoDB         │
│ Update task     │
└──────┬──────────┘
       │
       │ Success
       ▼
┌─────────────────────────────────────────┐
│ Response (HTTP 200)                     │
│ {                                       │
│   "status": "success",                  │
│   "update": {                           │
│     "id": "...",                        │
│     "status": "rejected",               │
│     "validator_id": "user_123",         │
│     "validated_at": "2025-12-15..."     │
│   }                                     │
│ }                                       │
└─────────────────────────────────────────┘
       │
       ▼
┌──────────────┐
│ Core Portal  │
│ Shows success│
└──────────────┘
```

## Thread Safety & Concurrency

### Approve Operation - Thread Model

```
Main HTTP Thread                Background Thread
─────────────────              ──────────────────

1. Receive POST approve
2. Verify JWT
3. Acquire Lock
4. Update MongoDB
   └─> status = approved
5. Release Lock
6. Start daemon thread ────────> 1. Get queue connection
7. Return HTTP 200                2. Build A08 event
   immediately                    3. Publish to RabbitMQ
                                  4. Log success/error
                                  5. Thread exits
```

**Benefits:**
- HTTP response không bị block bởi RabbitMQ operation
- User nhận response ngay lập tức
- Event emission chạy async trong background
- Nếu RabbitMQ fail, không ảnh hưởng HTTP response

### Lock Usage

```python
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
```

**Why Lock?**
- Prevent race conditions khi multiple requests cùng approve một task
- Đảm bảo atomic operation với MongoDB
- Thread-safe cho concurrent HTTP requests

## Error Handling

### Case 1: Task Not Found
```
Request: POST /api/v1/partner-updates/invalid_id/approve
Response: HTTP 404
{
  "message": "Update invalid_id not found or already processed"
}
```

### Case 2: Task Already Processed
```
Request: POST /api/v1/partner-updates/{id}/approve
(task đã có status = "approved")

Response: HTTP 404
{
  "message": "Update {id} not found or already processed"
}
```

### Case 3: Invalid JWT
```
Request: POST /api/v1/partner-updates/{id}/approve
Authorization: Bearer invalid_token

Response: HTTP 401
{
  "message": "Unauthorized: Invalid or missing JWT token"
}
```

### Case 4: SeaweedFS Unavailable
```
Request: GET /api/v1/partner-updates/{id}
(SeaweedFS không trả về file)

Response: HTTP 200
{
  "status": "success",
  "update": {
    "id": "...",
    "faqs": [],        # Empty nếu không lấy được
    "packages": []
  }
}
```

## Performance Considerations

### Database Indexes
```javascript
// Created on initialization
validation_tasks.createIndex({ status: 1 })
validation_tasks.createIndex({ partner_id: 1 })
validation_tasks.createIndex({ created_at: -1 })
```

**Impact:**
- List queries với filter nhanh hơn
- Sort by created_at DESC tối ưu
- Partner-specific queries efficient

### Pagination
```python
# Max page size = 100
if page_size > 100:
    page_size = 100

# Skip calculation
skip = (page - 1) * limit

# Limited result set
cursor = collection.find(filter).skip(skip).limit(limit)
```

**Benefits:**
- Giới hạn memory usage
- Network bandwidth efficient
- Response time predictable

### Background Threading
```python
thread = Thread(target=send_to_s03)
thread.daemon = True
thread.start()
# Don't wait for thread
return response
```

**Benefits:**
- HTTP response time < 100ms
- RabbitMQ latency không ảnh hưởng user experience
- Service vẫn responsive khi RabbitMQ slow
