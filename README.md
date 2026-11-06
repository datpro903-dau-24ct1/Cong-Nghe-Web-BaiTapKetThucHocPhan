# Shop Mô hình Anime (Django)

## Chuẩn bị cơ sở dữ liệu (XAMPP / MariaDB)
1. Mở XAMPP Control Panel, bấm **Start** ở dòng **MySQL**.
2. Vào http://localhost/phpmyadmin → tab **SQL**, chạy:
   ```sql
   CREATE DATABASE shopmohinh CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
3. Cần MariaDB 10.5+ (Django 5.x). Kiểm tra bằng `SELECT VERSION();`.
4. Muốn chạy nhanh không cần MariaDB: đặt `DJANGO_DB_ENGINE=sqlite` trong `.env`.

## Chạy dự án lần đầu
```
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # rồi sửa DJANGO_SECRET_KEY trong .env
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```
Mở http://127.0.0.1:8000/ (trang quản trị: /admin/).

## Biến môi trường
Đặt trong tệp `.env` cùng cấp `manage.py` (không commit). Biến môi trường thật của hệ thống được ưu tiên hơn `.env`.

| Biến | Ý nghĩa |
|---|---|
| `DJANGO_DEBUG` | `1` để bật chế độ dev. Mặc định tắt. |
| `DJANGO_SECRET_KEY` | Bắt buộc khi `DJANGO_DEBUG` không bật. |
| `DJANGO_DB_ENGINE` | `mysql` (MariaDB/MySQL) hoặc `sqlite` (mặc định nếu không đặt). |
| `DJANGO_DB_NAME` / `_USER` / `_PASSWORD` / `_HOST` / `_PORT` | Thông tin kết nối khi dùng `mysql` (XAMPP mặc định: `shopmohinh` / `root` / rỗng / `127.0.0.1` / `3306`). |
| `DJANGO_ALLOWED_HOSTS` | Danh sách host, cách nhau dấu phẩy (khi deploy). |

## Kiểm thử và static
```
python manage.py test
python manage.py collectstatic       # chỉ khi cần gom static
```
