# S11 Local Knowledge Service - API Documentation

## Overview

S11 Local Knowledge Service quản lý kiến thức viễn thông cục bộ (packages và FAQs) cho Partner. Service này expose cả HTTP API (H28) cho Partner Portal và RabbitMQ API (A32, A33) để tương tác với các services khác.

## H28 HTTP API

Base URL: `http://localhost:7011/api/v1/local-knowledge`

### Authentication
- Yêu cầu JWT authentication với partner employee credentials
- Rate limiting: 60 requests/minute/user

---

## 1. CRUD Packages

**Endpoint:** `POST /api/v1/local-knowledge/packages`

### 1.1 List Packages

**Request:**
```json
{
  "method": "crud_packages",
  "params": {
    "action": "list",
    "data": {
      "page": 1,
      "limit": 10,
      "code": "SD70"  // optional filter
    }
  },
  "id": "req-001"
}
```

**Response (Success):**
```json
{
  "id": "req-001",
  "result": {
    "status": "success",
    "content": [
      {
        "id": 1,
        "partner_id": 1,
        "code": "SD70",
        "meta_data": "{\"payment_type\":\"Trả trước\",\"price\":70000,...}"
      }
    ]
  }
}
```

### 1.2 Create Package

**Request:**
```json
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
      "4G tốc độ cao/ngày": 0,
      "Chi tiết": "Gói cước data 4G",
      "Tự động gia hạn": "Có",
      "Cú pháp đăng ký": "SD70 DK8 gửi 290"
    }
  },
  "id": "req-002"
}
```

**Response (Success):**
```json
{
  "id": "req-002",
  "result": {
    "status": "success",
    "content": {
      "id": 101,
      "message": "Package created successfully"
    }
  }
}
```

**Response (Error - Duplicate Code):**
```json
{
  "id": "req-002",
  "result": {
    "status": "error",
    "content": "Duplicate package code: SD70"
  }
}
```

### 1.3 Update Package

**Request:**
```json
{
  "method": "crud_packages",
  "params": {
    "action": "update",
    "data": {
      "id": 101,
      "Giá (VNĐ)": 75000,
      "Chi tiết": "Gói cước data 4G (cập nhật)"
    }
  },
  "id": "req-003"
}
```

**Response (Success):**
```json
{
  "id": "req-003",
  "result": {
    "status": "success",
    "content": {
      "id": 101,
      "message": "Package updated successfully"
    }
  }
}
```

**Response (Error - Missing ID):**
```json
{
  "id": "req-003",
  "result": {
    "status": "error",
    "content": "Missing required field: id"
  }
}
```

### 1.4 Delete Package

**Request:**
```json
{
  "method": "crud_packages",
  "params": {
    "action": "delete",
    "data": {
      "id": 101
    }
  },
  "id": "req-004"
}
```

**Response (Success):**
```json
{
  "id": "req-004",
  "result": {
    "status": "success",
    "content": {
      "id": 101,
      "message": "Package deleted successfully"
    }
  }
}
```

---

## 2. CRUD FAQs

**Endpoint:** `POST /api/v1/local-knowledge/faqs`

### 2.1 List FAQs

**Request:**
```json
{
  "method": "crud_faqs",
  "params": {
    "action": "list",
    "data": {
      "page": 1,
      "limit": 10,
      "category": "balance"  // optional filter
    }
  },
  "id": "req-101"
}
```

**Response (Success):**
```json
{
  "id": "req-101",
  "result": {
    "status": "success",
    "content": [
      {
        "id": 1,
        "partner_id": 1,
        "question": "Làm sao để kiểm tra số dư?",
        "answer": "Bấm *101# để kiểm tra số dư tài khoản.",
        "category": "balance"
      }
    ]
  }
}
```

### 2.2 Create FAQ

**Request:**
```json
{
  "method": "crud_faqs",
  "params": {
    "action": "create",
    "data": {
      "question": "Làm sao để kiểm tra số dư?",
      "answer": "Bấm *101# để kiểm tra số dư tài khoản.",
      "category": "balance"
    }
  },
  "id": "req-102"
}
```

**Response (Success):**
```json
{
  "id": "req-102",
  "result": {
    "status": "success",
    "content": {
      "id": 202,
      "message": "FAQ created successfully"
    }
  }
}
```

**Response (Error - Duplicate Question):**
```json
{
  "id": "req-102",
  "result": {
    "status": "error",
    "content": "Duplicate FAQ question"
  }
}
```

### 2.3 Update FAQ

**Request:**
```json
{
  "method": "crud_faqs",
  "params": {
    "action": "update",
    "data": {
      "id": 202,
      "answer": "Bấm *101# hoặc truy cập My Viettel để kiểm tra số dư.",
      "category": "Cước phí"
    }
  },
  "id": "req-103"
}
```

### 2.4 Delete FAQ

**Request:**
```json
{
  "method": "crud_faqs",
  "params": {
    "action": "delete",
    "data": {
      "id": 202
    }
  },
  "id": "req-104"
}
```

---

## 3. Import File

**Endpoint:** `POST /api/v1/local-knowledge/import-file`

**Content-Type:** `multipart/form-data`

### Request

```http
POST /api/v1/local-knowledge/import-file HTTP/1.1
Host: localhost:7011
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary

------WebKitFormBoundary
Content-Disposition: form-data; name="file"; filename="packages_q4_2025.xlsx"
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet

[binary file content]
------WebKitFormBoundary
Content-Disposition: form-data; name="metadata"

{
  "source": "Viettel",
  "description": "Dữ liệu gói cước Q4 2025",
  "import_type": "local_only"
}
------WebKitFormBoundary--
```

**Response (Success):**
```json
{
  "id": "h28-import-1702893456789",
  "result": {
    "status": "success",
    "content": {
      "import_id": "import_1_1702893456789",
      "seaweed_file_id": "3,01637037d6"
    }
  }
}
```

**Response (Error - Unsupported Format):**
```json
{
  "id": "h28-import-1702893456789",
  "result": {
    "status": "error",
    "content": "Unsupported file format. Supported: .pdf, .xlsx, .xls, .docx"
  }
}
```

**Response (Error - File Too Large):**
```json
{
  "id": "h28-import-1702893456789",
  "result": {
    "status": "error",
    "content": "File size exceeds maximum limit of 50MB"
  }
}
```

**Response (Error - SeaweedFS Upload Failed):**
```json
{
  "id": "h28-import-1702893456789",
  "result": {
    "status": "error",
    "content": "Failed to upload file to storage: Connection refused"
  }
}
```

### Supported File Types
- `.pdf` - PDF documents
- `.xlsx` - Excel 2007+ files
- `.xls` - Excel 97-2003 files
- `.docx` - Word documents

### File Size Limit
- Maximum: 50MB

---

## A32 RabbitMQ API (S11 → S15)

### Queue Configuration
- **Request Queue:** `file_import_requests`
- **Response Queue:** `file_import_responses`

### Method: import_file

**Request Message (S11 → S15):**
```json
{
  "method": "import_file",
  "params": {
    "seaweed_file_id": "3,01234567"
  },
  "id": "import_1_1702893456789"
}
```

**Response Message (S15 → S11):**
```json
{
  "id": "import_1_1702893456789",
  "result": {
    "status": "success",
    "content": {
      "processed_at": "2025-12-10T12:00:00Z",
      "packages": [
        {
          "code": "SD70",
          "price": 70000,
          ...
        }
      ],
      "warnings": ["Row 15: missing service code"],
      "extracted_count": 42
    }
  }
}
```

---

## A33 RabbitMQ API (S12 → S11)

### Queue Configuration
- **Request Queue:** `snapshot_requests`
- **Response Queue:** `snapshot_responses`

### Method: snapshot

**Request Message (S12 → S11):**
```json
{
  "method": "snapshot",
  "params": {},
  "id": "snapshot-001"
}
```

**Response Message (S11 → S12):**
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

**Snapshot File Format (JSON in SeaweedFS):**
```json
{
  "partner_id": 1,
  "timestamp": "2025-12-10T12:00:00Z",
  "packages": [
    {
      "id": 1,
      "partner_id": 1,
      "code": "SD70",
      "meta_data": "{...}"
    }
  ],
  "faqs": [
    {
      "id": 1,
      "partner_id": 1,
      "question": "...",
      "answer": "...",
      "category": "..."
    }
  ]
}
```

**Response (Error):**
```json
{
  "id": "snapshot-001",
  "result": {
    "status": "error",
    "content": "Failed to upload snapshot to SeaweedFS: Connection refused"
  }
}
```

---

## Error Codes

### HTTP Status Codes
- `200` - Success
- `400` - Bad Request (invalid parameters, validation errors)
- `500` - Internal Server Error

### Error Messages

#### Package CRUD
- `"Invalid action. Must be one of: list, create, update, delete"`
- `"Missing required field: id"`
- `"Duplicate package code: <code>"`
- `"Package not found: <id>"`

#### FAQ CRUD
- `"Invalid action. Must be one of: list, create, update, delete"`
- `"Missing required field: id"`
- `"Duplicate FAQ question"`
- `"FAQ not found: <id>"`

#### File Import
- `"Unsupported file format. Supported: .pdf, .xlsx, .xls, .docx"`
- `"File size exceeds maximum limit of 50MB"`
- `"Failed to upload file to storage: <details>"`

---

## Example Usage with curl

### Create Package
```bash
curl -X POST http://localhost:7011/api/v1/local-knowledge/packages \
  -H "Content-Type: application/json" \
  -d '{
    "method": "crud_packages",
    "params": {
      "action": "create",
      "data": {
        "code": "SD70",
        "Thời gian thanh toán": "Trả trước",
        "Giá (VNĐ)": 70000
      }
    },
    "id": "req-001"
  }'
```

### Upload File
```bash
curl -X POST http://localhost:7011/api/v1/local-knowledge/import-file \
  -F "file=@packages.xlsx" \
  -F 'metadata={"source":"Viettel","description":"Q4 2025 packages"}'
```

### List FAQs
```bash
curl -X POST http://localhost:7011/api/v1/local-knowledge/faqs \
  -H "Content-Type: application/json" \
  -d '{
    "method": "crud_faqs",
    "params": {
      "action": "list",
      "data": {"page": 1, "limit": 10}
    },
    "id": "req-101"
  }'
```
