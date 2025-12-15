# Quick Start Guide - S11 Local Knowledge Service

## Prerequisites

1. **Python 3.12+** with `uv` package manager
2. **MongoDB** running on localhost:27017
3. **RabbitMQ** running on localhost:5672
4. **SeaweedFS** running on localhost:9333

## Installation

```bash
# Clone repository
cd d:\VisualCode\telcenter-base-service

# Install dependencies with uv
uv sync
```

## Configuration

Create `.env` file from template:

```bash
cp .env.example .env
```

Edit `.env`:

```bash
# Service configuration
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

# Queue names
FILE_IMPORT_REQUEST_QUEUE=file_import_requests
FILE_IMPORT_RESPONSE_QUEUE=file_import_responses
SNAPSHOT_REQUESTS_QUEUE_NAME=snapshot_requests
SNAPSHOT_RESPONSES_QUEUE_NAME=snapshot_responses
```

## Running the Service

```bash
uv run python -m app
```

Output:
```
[Telcenter Partner] Starting service...
[Telcenter Partner] Running S11 Local Knowledge Service
[S11] RabbitMQ listeners started for A32 and A33
[S11] HTTP API listening on port 7011
[S11] RabbitMQ listeners active
 * Serving Flask app 'app.__main__'
 * Running on http://0.0.0.0:7011
```

## Testing the API

### 1. Test Package Creation

```bash
curl -X POST http://localhost:7011/api/v1/local-knowledge/packages \
  -H "Content-Type: application/json" \
  -d '{
    "method": "crud_packages",
    "params": {
      "action": "create",
      "data": {
        "code": "TEST01",
        "Thời gian thanh toán": "Trả trước",
        "Giá (VNĐ)": 50000,
        "Chu kỳ (ngày)": 30
      }
    },
    "id": "test-001"
  }'
```

Expected response:
```json
{
  "id": "test-001",
  "result": {
    "status": "success",
    "content": {
      "id": 1,
      "message": "Package created successfully"
    }
  }
}
```

### 2. Test Package Listing

```bash
curl -X POST http://localhost:7011/api/v1/local-knowledge/packages \
  -H "Content-Type: application/json" \
  -d '{
    "method": "crud_packages",
    "params": {
      "action": "list",
      "data": {"page": 1, "limit": 10}
    },
    "id": "test-002"
  }'
```

### 3. Test FAQ Creation

```bash
curl -X POST http://localhost:7011/api/v1/local-knowledge/faqs \
  -H "Content-Type: application/json" \
  -d '{
    "method": "crud_faqs",
    "params": {
      "action": "create",
      "data": {
        "question": "Test question?",
        "answer": "Test answer",
        "category": "test"
      }
    },
    "id": "test-003"
  }'
```

### 4. Test File Import

```bash
# Create a test Excel file first, then:
curl -X POST http://localhost:7011/api/v1/local-knowledge/import-file \
  -F "file=@test_packages.xlsx" \
  -F 'metadata={"source":"Test","description":"Test import"}'
```

## Using Postman

1. Import the collection:
   - File → Import
   - Select `docs/S11_Postman_Collection.json`

2. Run requests from the collection:
   - H28 - Package CRUD → List Packages
   - H28 - Package CRUD → Create Package
   - H28 - FAQ CRUD → List FAQs
   - H28 - File Import → Import File

## Verify MongoDB Data

```bash
# Connect to MongoDB
mongosh mongodb://localhost:27017/

# Switch to database
use telcenter_partner_knowledge

# View packages
db.packages.find().pretty()

# View FAQs
db.faqs.find().pretty()

# Count documents
db.packages.countDocuments()
db.faqs.countDocuments()
```

## Verify RabbitMQ Queues

Access RabbitMQ Management UI:
- URL: http://localhost:15672
- Default credentials: guest/guest

Check queues:
- `file_import_requests`
- `file_import_response`
- `snapshot_requests`
- `snapshot_responses`

## Troubleshooting

### Service won't start

**Problem**: MongoDB connection error
```
pymongo.errors.ServerSelectionTimeoutError
```

**Solution**: Ensure MongoDB is running
```bash
# Windows
net start MongoDB

# Or start manually
mongod --dbpath C:\data\db
```

---

**Problem**: RabbitMQ connection error
```
pika.exceptions.AMQPConnectionError
```

**Solution**: Ensure RabbitMQ is running
```bash
# Windows
net start RabbitMQ

# Or check service status
rabbitmqctl status
```

---

**Problem**: Port already in use
```
OSError: [Errno 48] Address already in use
```

**Solution**: Change port in `.env`
```bash
S11_PORT=7012
```

### API returns errors

**Problem**: "Duplicate package code"
- The package code already exists
- Use a different code or delete the existing package first

**Problem**: "Missing required field: id"
- For update/delete operations, include the `id` field in `data`

**Problem**: "Invalid action"
- Check that `action` is one of: list, create, update, delete

### File upload fails

**Problem**: "Unsupported file format"
- Only .pdf, .xlsx, .xls, .docx are supported

**Problem**: "File size exceeds maximum limit"
- File must be under 50MB

**Problem**: "Failed to upload file to storage"
- Ensure SeaweedFS is running on configured URL

## Running Tests

```bash
python test_s11.py
```

Expected output:
```
============================================================
S11 Local Knowledge Service - Test Suite
============================================================
Testing S11 service imports...
✓ LocalKnowledgeService imported successfully
✓ Models (Package, FAQ) imported successfully
✓ MongoDBClient imported successfully
✓ H28 controller imported successfully

✓ All imports successful!

Testing models...
✓ Package serialization: {...}
✓ Package deserialization: code=SD70
✓ FAQ serialization: {...}
✓ FAQ deserialization: question=Test question?

✓ All model tests passed!

============================================================
✓ All tests passed!
============================================================
```

## Next Steps

1. **Implement S15** - File Importing AI Agent (for file processing)
2. **Implement S12** - Partner Knowledge Update Service (for snapshot feature)
3. **Add authentication** - JWT middleware for HTTP API
4. **Add logging** - Structured logging for monitoring
5. **Add metrics** - Prometheus metrics export
6. **Deploy to production** - Docker containerization

## Documentation

- Full API documentation: [docs/S11_API_Documentation.md](docs/S11_API_Documentation.md)
- Service README: [app/services/s11_local_knowledge_service/README.md](app/services/s11_local_knowledge_service/README.md)
- Implementation summary: [S11_IMPLEMENTATION_SUMMARY.md](S11_IMPLEMENTATION_SUMMARY.md)
- Specification: [docs/services/partner/S11_Partner_Local_Knowledge_Service.md](docs/services/partner/S11_Partner_Local_Knowledge_Service.md)

## Support

For issues or questions:
1. Check error logs in console
2. Verify all services (MongoDB, RabbitMQ, SeaweedFS) are running
3. Check `.env` configuration
4. Review API documentation
5. Check MongoDB for data consistency
