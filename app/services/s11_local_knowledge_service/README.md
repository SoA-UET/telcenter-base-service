# S11 Local Knowledge Service

Service quản lý kiến thức viễn thông cục bộ của Partner (gói cước và FAQs).

## Chức năng

### API H28 (HTTP) - Partner Portal
- **CRUD Packages**: Tạo, đọc, cập nhật, xóa các gói cước viễn thông
- **CRUD FAQs**: Tạo, đọc, cập nhật, xóa các câu hỏi thường gặp
- **Import File**: Upload và xử lý file Excel/PDF/Word chứa dữ liệu gói cước

### API A33 (RabbitMQ) - From S12
- **Snapshot**: Tạo snapshot của database hiện tại và lưu vào SeaweedFS

### API A32 (RabbitMQ) - To S15
- Gửi request xử lý file import đến S15 File Importing AI Agent

## Cấu trúc

```
app/services/s11_local_knowledge_service/
├── __init__.py
├── LocalKnowledgeService.py  # Core service logic
├── models.py                  # Package và FAQ models
└── database.py               # MongoDB client utilities

app/controllers/v1/
└── local_knowledge.py        # H28 HTTP endpoints
```

## Database Schema (MongoDB)

**Database**: `telcenter_partner_knowledge`

### Collection: `packages`
- `id`: INT (Primary key)
- `partner_id`: INT
- `code`: VARCHAR(50) - Mã gói (VD: SD70)
- `meta_data`: TEXT (JSON string) - Thông tin chi tiết gói cước

### Collection: `faqs`
- `id`: INT (Primary key)
- `partner_id`: INT
- `question`: TEXT - Câu hỏi
- `answer`: TEXT - Câu trả lời
- `category`: VARCHAR(50) - Phân loại

## Cấu hình (.env)

```bash
SERVICE_MODE=s11
S11_PORT=7011
PARTNER_ID=1

# MongoDB
MONGODB_CONNECTION_STRING=mongodb://localhost:27017/
S11_DATABASE_NAME=telcenter_partner_knowledge

# SeaweedFS
SEAWEED_MASTER_URL=http://localhost:9333
SEAWEED_PUBLIC_URL=http://localhost:9333

# RabbitMQ
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# A32 Queues (to S15)
FILE_IMPORT_REQUEST_QUEUE=file_import_requests
FILE_IMPORT_RESPONSE_QUEUE=file_import_responses

# A33 Queues (from S12)
SNAPSHOT_REQUESTS_QUEUE_NAME=snapshot_requests
SNAPSHOT_RESPONSES_QUEUE_NAME=snapshot_responses
```

## Chạy Service

```bash
# Cài đặt dependencies
uv sync

# Chạy service
uv run python -m app
```

Service sẽ:
1. Khởi động HTTP server trên port 7011 (H28 API)
2. Lắng nghe RabbitMQ queues cho A32 và A33

## API Examples

### 1. CRUD Packages (H28)

**List packages:**
```bash
POST http://localhost:7011/api/v1/local-knowledge/packages
Content-Type: application/json

{
  "method": "crud_packages",
  "params": {
    "action": "list",
    "data": {
      "page": 1,
      "limit": 10
    }
  },
  "id": "req-001"
}
```

**Create package:**
```bash
POST http://localhost:7011/api/v1/local-knowledge/packages
Content-Type: application/json

{
  "method": "crud_packages",
  "params": {
    "action": "create",
    "data": {
      "code": "SD70",
      "Thời gian thanh toán": "Trả trước",
      "Giá (VNĐ)": 70000,
      "Chu kỳ (ngày)": 30,
      "4G tốc độ tiêu chuẩn/ngày": 1,
      "Tự động gia hạn": "Có"
    }
  },
  "id": "req-002"
}
```

### 2. CRUD FAQs (H28)

**Create FAQ:**
```bash
POST http://localhost:7011/api/v1/local-knowledge/faqs
Content-Type: application/json

{
  "method": "crud_faqs",
  "params": {
    "action": "create",
    "data": {
      "question": "Làm sao để kiểm tra số dư?",
      "answer": "Bấm *101# để kiểm tra số dư tài khoản.",
      "category": "Cước phí"
    }
  },
  "id": "req-003"
}
```

### 3. Import File (H28)

```bash
POST http://localhost:7011/api/v1/local-knowledge/import-file
Content-Type: multipart/form-data

file: <binary_file_data>
metadata: {
  "source": "Viettel",
  "description": "Dữ liệu gói cước Q4 2025"
}
```

### 4. Snapshot Request (A33 - via RabbitMQ)

S12 gửi request vào queue `snapshot_requests`:
```json
{
  "method": "snapshot",
  "params": {},
  "id": "snapshot-001"
}
```

S11 trả response vào queue `snapshot_responses`:
```json
{
  "id": "snapshot-001",
  "result": {
    "status": "success",
    "content": {
      "seaweed_file_id": "3,01637037d6"
    }
  }
}
```

## Dependencies

- Flask: HTTP API framework
- pymongo: MongoDB driver
- pika: RabbitMQ client
- requests: HTTP client cho SeaweedFS
- flask-cors: CORS support

## Architecture

```
Partner Portal (Web)
    ↓ H28 (HTTP)
S11 Local Knowledge Service
    ↓ A32 (RabbitMQ) → S15 File Importing AI Agent
    ↑ A33 (RabbitMQ) ← S12 Partner Knowledge Update Service
    ↓ SeaweedFS (HTTP) - File storage
    ↓ MongoDB - Knowledge database
```
