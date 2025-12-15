# Quick Start Guide - S05 Knowledge Validator Service

## 🚀 Khởi động nhanh trong 5 phút

### Bước 1: Kiểm tra dependencies đã cài
```bash
uv sync
```

### Bước 2: Tạo file .env
```bash
# Copy từ template
cp .env.example .env
```

Hoặc tạo file `.env` với nội dung tối thiểu:
```env
# MongoDB
MONGODB_URL=mongodb://localhost:27017/
S05_DB_NAME=telcenter_core_s05

# RabbitMQ
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
KNOWLEDGE_STORE_EVENT_QUEUE=knowledge_store_events

# SeaweedFS
SEAWEEDFS_URL=http://localhost:8080

# JWT
JWT_SECRET=dev-secret-key-change-in-production

# Flask
FLASK_PORT=5005
FLASK_DEBUG=True
```

### Bước 3: Khởi động service
```bash
uv run python -m app
```

Hoặc:
```bash
.venv\Scripts\python.exe -m app
```

### Bước 4: Kiểm tra service đang chạy
Mở trình duyệt:
```
http://localhost:5005/api/docs
```

Bạn sẽ thấy Swagger UI với 4 endpoints:
- GET /api/v1/partner-updates
- GET /api/v1/partner-updates/{id}
- POST /api/v1/partner-updates/{id}/approve
- POST /api/v1/partner-updates/{id}/reject

## 📝 Test nhanh với Python

### Test 1: Tạo validation task
```python
import os
os.environ['MONGODB_URL'] = 'mongodb://localhost:27017/'
os.environ['S05_DB_NAME'] = 'telcenter_core_s05_test'

from app.services.s05_knowledge_validator_service import KnowledgeValidatorService

service = KnowledgeValidatorService()

# Tạo task
task_id = service.create_validation_task(
    seaweed_file_id="test_file_123",
    partner_id="viettel_partner_001"
)

print(f"Created task: {task_id}")

# List tasks
result = service.get_validation_tasks(status="pending", page=1, limit=10)
print(f"Found {result['total_count']} tasks")

service.close()
```

### Test 2: Test với HTTP API
Chạy service trước, sau đó:

```python
import requests
import jwt
import time

# Tạo JWT token (demo)
secret = "dev-secret-key-change-in-production"
payload = {
    "user_id": "test_validator",
    "exp": int(time.time()) + 3600
}
token = jwt.encode(payload, secret, algorithm="HS256")

# List updates
response = requests.get(
    "http://localhost:5005/api/v1/partner-updates",
    headers={"Authorization": f"Bearer {token}"},
    params={"status": "pending", "pageNumber": 1, "pageSize": 10}
)
print(response.json())
```

## 🧪 Test với script có sẵn
```bash
.venv\Scripts\python.exe test_s05.py
```

Expected output:
```
============================================================
Testing S05 Knowledge Validator Service
============================================================

[1/5] Importing KnowledgeValidatorService...
✓ Service imported successfully

[2/5] Initializing service...
✓ Service initialized successfully

[3/5] Creating test validation task...
✓ Created task with ID: 67...

[4/5] Listing validation tasks...
✓ Found 1 task(s)
  - Pending: 1
  - Approved: 0
  - Rejected: 0

[5/5] Getting task details...
✓ Task details retrieved

============================================================
✓ ALL TESTS PASSED
============================================================
```

## 🔧 Troubleshooting

### Lỗi: "No module named 'jwt'"
```bash
uv sync
```

### Lỗi: "Can't connect to MongoDB"
Kiểm tra MongoDB đang chạy:
```bash
# Windows
net start MongoDB

# Hoặc chạy MongoDB trong Docker
docker run -d -p 27017:27017 mongo
```

### Lỗi: "Can't connect to RabbitMQ"
Kiểm tra RabbitMQ đang chạy:
```bash
# Chạy RabbitMQ trong Docker
docker run -d -p 5672:5672 -p 15672:15672 rabbitmq:management
```

### Service chạy nhưng không thấy endpoints
Kiểm tra log khi khởi động:
```
[Main] Initializing S05 Knowledge Validator Service...
[S05 KnowledgeValidatorService] Initialized
[Main] All services initialized successfully
[Main] Starting Flask server on 0.0.0.0:5005
```

Nếu thấy log trên là OK. Truy cập: `http://localhost:5005/api/docs`

## 📖 Next Steps

### 1. Đọc documentation đầy đủ
- [S05_README.md](../S05_README.md) - Hướng dẫn chi tiết
- [S05_API_FLOWS.md](../S05_API_FLOWS.md) - API flows và diagrams

### 2. Tích hợp với frontend
Frontend cần:
- Gọi GET endpoint để list updates
- Gọi GET endpoint để xem chi tiết
- Gọi POST approve/reject để duyệt/từ chối
- Truyền JWT token trong header `Authorization: Bearer <token>`

### 3. Tích hợp với S03
S03 cần:
- Lắng nghe RabbitMQ queue: `knowledge_store_events`
- Consume event: `store_validated_knowledge`
- Download data từ SeaweedFS với `seaweed_file_id`
- Store vào knowledge database

### 4. Test end-to-end
1. Tạo validation task (hoặc nhận từ S12)
2. List qua API
3. Approve qua API
4. Kiểm tra event đã gửi đến S03
5. Verify data đã lưu trong S03 database

## 💡 Tips

1. **Dùng Swagger UI** để test thay vì curl:
   - Tự động gen request format
   - Try-it-out functionality
   - Dễ nhìn response

2. **MongoDB GUI** để xem data:
   ```bash
   # MongoDB Compass
   # Connect: mongodb://localhost:27017
   # Database: telcenter_core_s05
   # Collection: validation_tasks
   ```

3. **RabbitMQ Management UI**:
   ```
   http://localhost:15672
   Username: guest
   Password: guest
   ```

4. **Debug mode**:
   ```env
   FLASK_DEBUG=True
   ```
   Service sẽ auto-reload khi code thay đổi.

## ✅ Checklist hoàn thành setup

- [ ] MongoDB đang chạy
- [ ] RabbitMQ đang chạy
- [ ] Dependencies đã cài (`uv sync`)
- [ ] File `.env` đã tạo
- [ ] Service khởi động thành công
- [ ] Swagger UI hiển thị đúng (`/api/docs`)
- [ ] Test script chạy thành công (`test_s05.py`)

Nếu tất cả OK → Service sẵn sàng sử dụng! 🎉
