# S06: Core Employee Identity Service

Service xác thực và quản lý tài khoản nhân viên Core trong hệ thống Telcenter.

## Chức năng

- Xác thực đăng nhập cho Admin và nhân viên Core
- Quản lý tài khoản nhân viên (tạo, sửa, xóa/khóa)
- Phát hành và quản lý JWT tokens (RS256)
- Cung cấp JWKS endpoint để các service khác verify tokens
- Bảo vệ chống brute-force (khóa tài khoản sau 5 lần đăng nhập sai)
- Logging và audit trail

## Yêu cầu hệ thống

- Python >= 3.12
- MongoDB
- uv (package manager)

## Cài đặt

### 1. Clone repository và cài đặt dependencies

```bash
# Cài đặt uv nếu chưa có
pip install uv

# Cài đặt dependencies
uv pip install -e .
```

### 2. Cấu hình môi trường

Tạo file `.env` từ `.env.example`:

```bash
cp .env.example .env
```

Chỉnh sửa file `.env` với thông tin MongoDB của bạn:

```env
MONGO_URL=mongodb://localhost:27017/core_employee_identity
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=True
JWT_EXPIRATION_TIME_IN_MINUTES=10
```

### 3. Khởi tạo database

Chạy script để tạo roles và admin account mặc định:

```bash
python init_db.py
```

Script sẽ tạo:
- 3 roles mặc định (ADMIN, Tư vấn viên kênh thoại, Tư vấn viên kênh nhắn tin)
- Admin account với thông tin:
  - Email: `admin_core@telcenter.vn`
  - Password: `Admin@123`

## Chạy service

```bash
python -m app
```

Service sẽ chạy tại `http://localhost:5000`

## API Endpoints

### 1. Authentication

**POST /api/v1/core-auth/login**
- Đăng nhập và nhận JWT token
- Body: `{"username": "admin_core@telcenter.vn", "password": "Admin@123"}`

### 2. JWKS

**GET /.well-known/jwks.json**
- Lấy danh sách public keys để verify JWT

### 3. Employee Management

**GET /api/v1/core-employees**
- Xem danh sách nhân viên (cần authentication)

**POST /api/v1/core-employees**
- Tạo nhân viên mới (cần admin permission)
- Body: `{"full_name": "...", "role_id": "..."}`

**PUT /api/v1/core-employees/{employee_id}**
- Cập nhật thông tin nhân viên (cần admin permission)
- Body: `{"full_name": "...", "status": "ACTIVE"}`

**DELETE /api/v1/core-employees/{employee_id}**
- Xóa/khóa nhân viên (cần admin permission)
- Query param: `?lock_only=true` để chỉ khóa tạm thời

### 4. Health Check

**GET /health**
- Kiểm tra trạng thái service

## Test Interface

Mở file `test_interface.html` trong trình duyệt để test các API endpoints với giao diện đồ họa.

Hoặc chạy lệnh:

```bash
python -m http.server 8080
```

Sau đó mở `http://localhost:8080/test_interface.html`

## Kiến trúc

```
app/
├── collections/          # MongoDB collections
│   ├── employees.py
│   ├── roles.py
│   ├── keys.py
│   └── login_attempts.py
├── services/            # Business logic
│   ├── AuthService.py
│   ├── EmployeeService.py
│   └── RoleService.py
├── controllers/         # API endpoints
│   ├── v1/
│   │   └── core_auth.py
│   └── jwks.py
├── utils/               # Utilities
│   ├── jwt_service.py
│   ├── password.py
│   └── logger.py
└── __main__.py         # Entry point
```

## Security Features

- JWT signing với RS256 algorithm
- Password hashing với bcrypt
- Brute-force protection (khóa sau 5 lần đăng nhập sai trong 30 phút)
- Permission-based authorization
- Audit logging cho tất cả các thao tác quan trọng

## Lấy Role ID để tạo nhân viên

Để tạo nhân viên mới, bạn cần Role ID từ MongoDB. Kết nối MongoDB và chạy:

```javascript
db.roles.find()
```

Copy `_id` của role bạn muốn gán cho nhân viên.

## Tài liệu tham khảo

- [H23 API Specification](docs/api_groups/H23.md)
- [JWT Signing Specification](docs/auth/SIGN.md)
- [Service Documentation](docs/services/core/S06_Core_Employee_Identity_Service.md)
