# Hướng dẫn cài đặt - Telcenter Base Service (S04)

## Yêu cầu hệ thống

- **Python**: 3.12 trở lên
- **MongoDB**: 4.0 trở lên (hoặc MongoDB Atlas)
- **RabbitMQ**: 3.8 trở lên (tùy chọn - nếu sử dụng message queue)
- **Git**: Để clone repository

## Bước 1: Clone Repository

```bash
git clone <repository-url>
cd telcenter-base-service
```

## Bước 2: Cài đặt Python và uv

### Windows

```bash
# Cài đặt Python từ python.org
# Sau đó cài đặt uv
pip install uv
```

### Linux/Mac

```bash
# Cài đặt uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Hoặc dùng pip
pip install uv
```

## Bước 3: Cài đặt MongoDB

### Tùy chọn A: MongoDB Local

#### Windows
1. Download từ https://www.mongodb.com/try/download/community
2. Cài đặt và chạy MongoDB service
3. MongoDB sẽ chạy tại `mongodb://localhost:27017`

#### Linux (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install -y mongodb-org
sudo systemctl start mongod
sudo systemctl enable mongod
```

#### Mac (Homebrew)
```bash
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb-community
```

### Tùy chọn B: MongoDB Atlas (Cloud)

1. Đăng ký tại https://www.mongodb.com/cloud/atlas
2. Tạo free cluster
3. Tạo database user
4. Whitelist IP của bạn (hoặc 0.0.0.0/0 cho development)
5. Lấy connection string

## Bước 4: Cài đặt RabbitMQ (Tùy chọn)

RabbitMQ chỉ cần nếu service giao tiếp với microservices khác qua message queue.

### Tùy chọn A: Docker (Khuyến nghị)

```bash
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management
```

Truy cập management UI tại: http://localhost:15672 (guest/guest)

### Tùy chọn B: Cài đặt trực tiếp

#### Windows
Download từ https://www.rabbitmq.com/download.html

#### Linux
```bash
sudo apt-get install rabbitmq-server
sudo systemctl start rabbitmq-server
sudo systemctl enable rabbitmq-server
```

#### Mac
```bash
brew install rabbitmq
brew services start rabbitmq
```

## Bước 5: Cấu hình Environment

### Tạo file .env

```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

### Chỉnh sửa .env

Mở file `.env` và cấu hình các biến môi trường:

```bash
# MongoDB
MONGO_URL=mongodb://localhost:27017/telcenter_core
PARTNER_MONGODB_URI=mongodb://localhost:27017/telcenter_partner

# JWT (Đổi secret này trong production!)
JWT_SECRET=your-very-strong-secret-key-here-change-in-production
JWT_EXPIRATION_SECONDS=3600

# Google OAuth (Xem bước 6 để lấy credentials)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:5000/api/v1/auth/oauth/callback

# RabbitMQ (nếu dùng)
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Flask
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_ENV=development
FLASK_DEBUG=True
```

## Bước 6: Cấu hình Google OAuth

### Lấy Google OAuth Credentials

1. Truy cập [Google Cloud Console](https://console.cloud.google.com/)
2. Tạo project mới hoặc chọn project có sẵn
3. Vào **APIs & Services** → **Library**
4. Tìm và enable **Google+ API** hoặc **Google People API**
5. Vào **APIs & Services** → **Credentials**
6. Click **Create Credentials** → **OAuth 2.0 Client ID**
7. Chọn **Application type**: Web application
8. Đặt tên cho OAuth client
9. Thêm **Authorized redirect URIs**:
   - Development: `http://localhost:5000/api/v1/auth/oauth/callback`
   - Production: `https://yourdomain.com/api/v1/auth/oauth/callback`
10. Click **Create**
11. Copy **Client ID** và **Client Secret** vào file `.env`

### Test configuration

Để test OAuth, truy cập:
```
http://localhost:5000/api/v1/auth/oauth/login?provider=google
```

## Bước 7: Cài đặt Dependencies

### Tùy chọn A: Sử dụng uv (Khuyến nghị)

```bash
# Tạo virtual environment
uv venv

# Kích hoạt virtual environment
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# Cài đặt dependencies
uv pip install -e .
```

### Tùy chọn B: Sử dụng pip truyền thống

```bash
# Tạo virtual environment
python -m venv .venv

# Kích hoạt virtual environment
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# Cài đặt dependencies
pip install -r requirements.txt
```

## Bước 8: Khởi động Service

### Tùy chọn A: Sử dụng script tự động

**Windows:**
```bash
start.bat
```

**Linux/Mac:**
```bash
chmod +x start.sh
./start.sh
```

### Tùy chọn B: Khởi động thủ công

```bash
# Kích hoạt virtual environment (nếu chưa)
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# Chạy service
python -m app
```

## Bước 9: Kiểm tra Service

Service sẽ chạy tại `http://localhost:5000`

### Truy cập tài liệu API

- **Trang chủ**: http://localhost:5000/
- **API Docs**: http://localhost:5000/api
- **Swagger UI**: http://localhost:5000/api/v1/

### Test API với curl

#### Đăng ký
```bash
curl -X POST http://localhost:5000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"phone_number\":\"0912345678\",\"password\":\"P@ssw0rd123\",\"full_name\":\"Nguyễn Văn A\",\"address\":\"TP. Hồ Chí Minh\"}"
```

#### Đăng nhập
```bash
curl -X POST http://localhost:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"phone_number\":\"0912345678\",\"password\":\"P@ssw0rd123\"}"
```

## Troubleshooting

### Lỗi kết nối MongoDB

```
Error: Environment variable MONGO_URL is missing
```

**Giải pháp:**
- Kiểm tra file `.env` đã được tạo
- Đảm bảo MongoDB đang chạy: `mongod --version`
- Kiểm tra connection string trong `.env`

### Lỗi import modules

```
ModuleNotFoundError: No module named 'flask'
```

**Giải pháp:**
- Kích hoạt virtual environment
- Cài đặt lại dependencies: `uv pip install -e .`

### Lỗi OAuth

```
OAUTH_NOT_CONFIGURED
```

**Giải pháp:**
- Kiểm tra `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` trong `.env`
- Đảm bảo redirect URI trong Google Console khớp với `.env`

### Port đã được sử dụng

```
Address already in use
```

**Giải pháp:**
- Thay đổi `FLASK_PORT` trong `.env`
- Hoặc dừng process đang chiếm port 5000

### Lỗi permission (Linux/Mac)

```
Permission denied: 'audit.log'
```

**Giải pháp:**
```bash
chmod 755 .
chmod 644 audit.log  # nếu file đã tồn tại
```

## Production Deployment

### Cấu hình bảo mật

1. **Đổi JWT_SECRET**: Tạo secret mạnh
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Sử dụng HTTPS**: Cấu hình reverse proxy (nginx/Apache)

3. **Đổi FLASK_ENV**: Set `FLASK_ENV=production`

4. **Tắt DEBUG**: Set `FLASK_DEBUG=False`

5. **Bảo mật MongoDB**: 
   - Enable authentication
   - Use strong passwords
   - Restrict network access

6. **CORS**: Cấu hình CORS chỉ cho phép domain cụ thể

### Chạy với production server

Không dùng Flask development server trong production. Sử dụng:

#### Gunicorn (Linux/Mac)
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 'app:app'
```

#### Waitress (Windows)
```bash
pip install waitress
waitress-serve --port=5000 app:app
```

## Maintenance

### Backup Database

```bash
# MongoDB
mongodump --uri="mongodb://localhost:27017/telcenter_partner" --out=backup/
```

### Restore Database

```bash
mongorestore --uri="mongodb://localhost:27017/telcenter_partner" backup/telcenter_partner/
```

### View Logs

Logs được ghi vào file `audit.log`:

```bash
tail -f audit.log
```

## Hỗ trợ

Nếu gặp vấn đề, vui lòng:
1. Kiểm tra logs trong `audit.log`
2. Xem tài liệu API tại `/api/v1/`
3. Đọc [S04 Service Documentation](docs/services/core/S04_Customer_Identity_Service.md)
