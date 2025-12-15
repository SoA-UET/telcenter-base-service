# S05 Knowledge Validator Service

Service S05 đã được lập trình hoàn chỉnh theo đặc tả trong file `docs/services/core/S05_Knowledge_Validator_Service.md`.

## Các thành phần đã triển khai

### 1. Service Class
**File:** `app/services/s05_knowledge_validator_service/KnowledgeValidatorService.py`

Class chính xử lý logic nghiệp vụ:
- Quản lý validation tasks trong MongoDB
- Emit sự kiện A08 đến S03 qua RabbitMQ
- Tích hợp với SeaweedFS để lấy dữ liệu JSON
- Thread-safe operations với Lock

**Các phương thức chính:**
- `create_validation_task()` - Tạo task mới
- `get_validation_tasks()` - Lấy danh sách tasks (có pagination)
- `get_validation_task_by_id()` - Lấy chi tiết task (bao gồm FAQs và packages từ SeaweedFS)
- `approve_validation_task()` - Duyệt task và gửi event A08 đến S03
- `reject_validation_task()` - Từ chối task

### 2. HTTP API Controller (H22)
**File:** `app/controllers/v1/partner_updates.py`

Triển khai 4 endpoints theo đặc tả H22:

1. **GET /api/v1/partner-updates**
   - Lấy danh sách updates với filtering và pagination
   - Query params: `status`, `partner_id`, `pageNumber`, `pageSize`
   - Response bao gồm summary statistics

2. **GET /api/v1/partner-updates/{update_id}**
   - Lấy chi tiết một update
   - Bao gồm FAQs và packages từ SeaweedFS

3. **POST /api/v1/partner-updates/{update_id}/approve**
   - Duyệt update
   - Gửi event A08 đến S03 để lưu vào knowledge database

4. **POST /api/v1/partner-updates/{update_id}/reject**
   - Từ chối update

**Tất cả endpoints đều:**
- Yêu cầu JWT authentication (Bearer token)
- Trích xuất validator_id từ JWT token
- Có Swagger documentation đầy đủ

### 3. Database Collection Model
**File:** `app/collections/validation_tasks.py`

Type definitions và index creation cho MongoDB collection `validation_tasks`.

### 4. Main Entry Point
**File:** `app/__main__.py`

- Khởi tạo Flask app
- Khởi tạo S05 service
- Đăng ký API routes
- Cấu hình Swagger UI tại `/api/docs`

### 5. Environment Configuration
**File:** `.env.example`

Đã thêm tất cả environment variables cần thiết:
- Flask configuration (host, port, debug)
- JWT secret
- MongoDB configuration cho S05
- RabbitMQ queue names (A08 API)
- SeaweedFS URL

## Cài đặt và chạy

### 1. Cài đặt dependencies
```bash
uv sync
```

### 2. Cấu hình environment
Tạo file `.env` từ `.env.example`:
```bash
cp .env.example .env
```

Chỉnh sửa `.env` với các giá trị thực tế:
```env
MONGODB_URL=mongodb://localhost:27017/
S05_DB_NAME=telcenter_core_s05
RABBITMQ_URL=amqp://guest:guest@localhost:5672
KNOWLEDGE_STORE_EVENT_QUEUE=knowledge_store_events
SEAWEEDFS_URL=http://localhost:8080
JWT_SECRET=your-production-secret-key
FLASK_PORT=5005
```

### 3. Khởi động service
```bash
uv run python -m app
```

Hoặc:
```bash
.venv/Scripts/python.exe -m app
```

### 4. Truy cập API Documentation
Mở trình duyệt: `http://localhost:5005/api/docs`

## Kiến trúc và luồng hoạt động

### Flow 1: Approve Knowledge Update

```
Core Portal (Frontend)
    ↓ POST /api/v1/partner-updates/{id}/approve (JWT)
S05 Controller (partner_updates.py)
    ↓ verify JWT, extract validator_id
S05 Service (KnowledgeValidatorService)
    ↓ Update status to "approved" in MongoDB
    ↓ Emit A08 event via RabbitMQ
S03 Knowledge Service
    ↓ Receives event, downloads from SeaweedFS
    ↓ Stores in knowledge database
```

### API A08 Event Format
S05 gửi event này đến S03 qua RabbitMQ queue `knowledge_store_events`:

```json
{
  "event": "store_validated_knowledge",
  "data": {
    "partner_id": "viettel_partner_001",
    "seaweed_file_id": "3,01234567",
    "validated_at": "2025-12-15T10:30:00Z"
  }
}
```

## Database Schema

**Collection:** `validation_tasks`
- `_id` (ObjectId): Primary key
- `seaweed_file_id` (string): ID file JSON trên SeaweedFS
- `partner_id` (string, nullable): Partner ID
- `status` (string): `pending` / `approved` / `rejected`
- `validator_id` (string): ID người duyệt
- `created_at` (datetime): Thời gian tạo
- `validated_at` (datetime, nullable): Thời gian duyệt

## Testing

### Test với curl

1. **List updates:**
```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  "http://localhost:5005/api/v1/partner-updates?status=pending&pageNumber=1&pageSize=20"
```

2. **Get update detail:**
```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  "http://localhost:5005/api/v1/partner-updates/{update_id}"
```

3. **Approve update:**
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' \
  "http://localhost:5005/api/v1/partner-updates/{update_id}/approve"
```

4. **Reject update:**
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' \
  "http://localhost:5005/api/v1/partner-updates/{update_id}/reject"
```

## Technology Stack

- **Python 3.12+**
- **Flask** - Web framework
- **Flask-RESTX** - REST API với Swagger
- **MongoDB** - Database
- **RabbitMQ** (via pika) - Message queue
- **PyJWT** - JWT authentication
- **Requests** - HTTP client cho SeaweedFS
- **Threading** - Multithreaded operations

## Đặc điểm kỹ thuật

1. **Thread-safe**: Sử dụng `Lock` cho các operations quan trọng
2. **Multithreading**: Event emission đến S03 chạy trong thread riêng để không block HTTP response
3. **Pagination**: Hỗ trợ phân trang với configurable page size
4. **JWT Authentication**: Tất cả endpoints đều yêu cầu JWT token
5. **Swagger Documentation**: API docs tự động tại `/api/docs`
6. **Error Handling**: Proper HTTP status codes và error messages

## Lưu ý

- Service này phụ thuộc vào S03 (phải nhận được events từ queue `knowledge_store_events`)
- Cần MongoDB và RabbitMQ đang chạy
- SeaweedFS phải có sẵn để lấy knowledge content
- JWT secret phải được cấu hình đúng và match với frontend

## Tích hợp với các services khác

### S03 Knowledge Service (via A08)
S05 gửi validated knowledge đến S03 qua RabbitMQ event queue.

### S12 Partner Knowledge Update Service (via A34)
S05 sẽ nhận snapshot events từ S12 (chưa triển khai trong version này, nhưng architecture đã sẵn sàng).
