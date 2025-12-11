# Telcenter Base Service - Customer Identity (S04)

Đây là service quản lý danh tính và xác thực khách hàng cho hệ thống Telcenter Core.

## Tính năng

- **Đăng ký tài khoản** - Khách hàng có thể tạo tài khoản mới với số điện thoại
- **Đăng nhập** - Xác thực bằng số điện thoại và mật khẩu
- **OAuth Login** - Đăng nhập qua Google OAuth
- **JWT Authentication** - Tạo và quản lý JWT tokens cho xác thực

## Công nghệ

- Python 3.12+
- Flask & Flask-RESTX
- MongoDB
- JWT (PyJWT)
- BCrypt (mã hóa mật khẩu)
- Google OAuth 2.0

## Cài đặt

### 1. Cài đặt dependencies

Sử dụng `uv` để quản lý môi trường và cài đặt packages:

```bash
# Cài đặt uv nếu chưa có
pip install uv

# Tạo virtual environment và cài đặt dependencies
uv venv
uv pip install -e .
```

### 2. Cấu hình môi trường

Tạo file `.env` từ template:

```bash
cp .env.example .env
```

Chỉnh sửa file `.env` với các thông tin của bạn:

- `MONGO_URL` - Connection string cho MongoDB chính
- `PARTNER_MONGODB_URI` - Connection string cho Partner MongoDB (lưu customers)
- `JWT_SECRET` - Secret key cho JWT (phải đổi trong production!)
- `GOOGLE_CLIENT_ID` - Google OAuth Client ID
- `GOOGLE_CLIENT_SECRET` - Google OAuth Client Secret
- `GOOGLE_REDIRECT_URI` - Callback URL cho OAuth

#### Lấy Google OAuth credentials:

1. Truy cập https://console.cloud.google.com/
2. Tạo project mới hoặc chọn project có sẵn
3. Enable Google+ API
4. Vào "Credentials" → "Create OAuth 2.0 Client ID"
5. Thêm Authorized redirect URIs (VD: `http://localhost:5000/api/v1/auth/oauth/callback`)
6. Copy Client ID và Client Secret vào file `.env`

### 3. Khởi động MongoDB

Đảm bảo MongoDB đang chạy:

```bash
# Nếu dùng Docker
docker run -d -p 27017:27017 --name mongodb mongo:latest

# Hoặc khởi động MongoDB service đã cài đặt
```

### 4. Chạy service

```bash
# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Chạy service
python -m app
```

Service sẽ khởi động tại `http://localhost:5000`

## API Documentation

Sau khi khởi động service, truy cập:

- **Trang chủ**: http://localhost:5000/
- **API Documentation**: http://localhost:5000/api
- **Swagger UI (v1)**: http://localhost:5000/api/v1/

## API Endpoints

### POST /api/v1/auth/register
Đăng ký tài khoản mới

**Request:**
```json
{
  "phone_number": "0912345678",
  "password": "P@ssw0rd123",
  "full_name": "Nguyễn Văn A",
  "address": "TP. Hồ Chí Minh"
}
```

**Response (201):**
```json
{
  "status": "success",
  "customer_id": "507f1f77bcf86cd799439011",
  "message": "Tài khoản được tạo thành công"
}
```

### POST /api/v1/auth/login
Đăng nhập

**Request:**
```json
{
  "phone_number": "0912345678",
  "password": "P@ssw0rd123"
}
```

**Response (200):**
```json
{
  "status": "success",
  "message": "Đăng nhập thành công",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "customer": {
    "customer_id": "507f1f77bcf86cd799439011",
    "phone_number": "0912345678",
    "full_name": "Nguyễn Văn A",
    "status": "ACTIVE"
  }
}
```

### GET /api/v1/auth/oauth/login?provider=google
Bắt đầu OAuth flow (chuyển hướng đến Google)

### GET /api/v1/auth/oauth/callback?code=...
Xử lý OAuth callback (tự động được Google gọi)

## Cấu trúc Database

### Collection: `customers`

```javascript
{
  "_id": ObjectId,
  "phone_number": String,      // Unique - Số điện thoại
  "password_hash": String,      // Mật khẩu đã hash (BCrypt)
  "full_name": String,          // Họ và tên
  "address": String,            // Địa chỉ
  "created_at": Date,           // Thời gian tạo
  "status": String,             // ACTIVE/INACTIVE
  
  // Cho OAuth users
  "oauth_email": String,        // Email từ OAuth provider
  "oauth_provider": String      // google, facebook, etc.
}
```

**Indexes:**
- `{ "phone_number": 1 }` - unique
- `{ "oauth_email": 1 }` - unique (tự động tạo nếu cần)

## Testing

Sử dụng curl hoặc Postman để test APIs:

```bash
# Đăng ký
curl -X POST http://localhost:5000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "0912345678",
    "password": "P@ssw0rd123",
    "full_name": "Nguyễn Văn A",
    "address": "TP. Hồ Chí Minh"
  }'

# Đăng nhập
curl -X POST http://localhost:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "0912345678",
    "password": "P@ssw0rd123"
  }'
```

## Validation Rules

### Số điện thoại
- Format: `0[3|5|7|8|9]xxxxxxxx` hoặc `+84[3|5|7|8|9]xxxxxxxx`
- Phải unique trong hệ thống

### Mật khẩu
- Tối thiểu 8 ký tự
- Phải có ít nhất: 1 chữ hoa, 1 chữ thường, 1 số, 1 ký tự đặc biệt

## Bảo mật

- Mật khẩu được hash bằng BCrypt trước khi lưu
- JWT tokens có thời gian hết hạn
- OAuth sử dụng HTTPS và state parameter
- Validation đầy đủ cho tất cả inputs

## Lưu ý

- Đổi `JWT_SECRET` trong production
- Sử dụng HTTPS trong production
- Cấu hình CORS phù hợp với frontend
- Backup database định kỳ

## Tài liệu tham khảo

- [S04_Customer_Identity_Service.md](./docs/services/core/S04_Customer_Identity_Service.md) - Tổng quan service
- [H20.md](./docs/api_groups/H20.md) - Chi tiết API specifications
