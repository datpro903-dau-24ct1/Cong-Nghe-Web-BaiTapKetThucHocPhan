# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## 5. Dự án

**Dự án:** Django Shop Mô hình Anime.

**Bảng chức năng**
- Phạm vi công việc lấy từ `Bang chuc nang anime shop.md` (mã CN01–CN28), không làm chức năng ngoài bảng.
- Làm theo thứ tự trong bảng, tôn trọng cột "Phụ thuộc" và xử lý các "Trường hợp biên" của chức năng đang làm.

**Cấu trúc app và các tầng**
- Tuân thủ mô hình MVT (Model-View-Template), hoặc REST Framework nếu đã được setup sẵn trong dự án.
- Mỗi app gồm: `models.py`, `selectors.py` (đọc dữ liệu), `services.py` (nghiệp vụ, ghi dữ liệu), `views.py`, `forms.py`, `urls.py`, `templates/`, `tests/`.
- Logic nghiệp vụ nằm trong Services/Selectors, tách biệt khỏi tầng View. Services/Selectors không import từ `views.py`, không nhận `request`, và không gọi trực tiếp mạng bên ngoài (email, cổng thanh toán) mà nhận qua tham số.
- View chỉ làm ba việc: nhận input, gọi service/selector, rồi render hoặc redirect.

**Cách diễn đạt thất bại dùng chung**
- Lỗi nghiệp vụ trong Services/Selectors: `raise ValidationError(message, code=...)`.
- View bắt `ValidationError` rồi hiển thị bằng `messages.error` hoặc trả lại form. Không tìm thấy đối tượng: dùng `get_object_or_404` / `Http404` chỉ ở tầng View.
- Không trả tuple `(False, error_message)`, không nuốt lỗi bằng `except: pass`.

**Công nghệ**
- Python 3.12+, Django 5.x.
- Không thêm thư viện nào ngoài pytest / django test và các thư viện core đã chỉ định trong `requirements.txt` (gồm Pillow, vì `ImageField` cần). Cần thư viện mới thì dừng lại và hỏi.
- Cơ sở dữ liệu: MariaDB/MySQL (XAMPP) qua `mysqlclient`, chọn bằng `DJANGO_DB_ENGINE=mysql` trong `.env`; `sqlite` chỉ là phương án dự phòng. Giá trị bí mật (`SECRET_KEY`, mật khẩu) đọc bằng `os.environ`, không hard-code.
- Không dùng: django-environ, pipenv, six, Docker, PayPal, AWS.

**Giới hạn kỹ thuật**
- Chỉ dùng kỹ thuật trong ba bài sau, trừ khi cần thêm kỹ thuật khác để làm nhanh hơn (khi đó phải nêu rõ kỹ thuật và lý do trước khi dùng):
  - https://viblo.asia/p/python-django-xay-dung-ung-dung-e-commerce-part-1-LzD5da4dKjY#_gioi-thieu-django---khoi-tao-project-0
  - https://viblo.asia/p/de-dang-co-ngay-ung-dung-e-commerce-voi-django-part-2-aWj53n2Yl6m
  - https://viblo.asia/p/hoan-thanh-ung-dung-e-commerce-voi-python-django-3Q75wExeZWb
- Các kỹ thuật chính trong bài: tùy chỉnh user model (`AbstractBaseUser` + `BaseUserManager`); tách app theo miền (accounts, category, store, carts, orders); `slug` + `prepopulated_fields` trong admin; `ImageField` cùng cấu hình static/media; `Paginator`; tìm kiếm bằng `Q(...__icontains)`; giỏ hàng theo session cho khách vãng lai rồi gắn vào user sau khi đăng nhập; context processor; `messages`; kích hoạt email và quên mật khẩu bằng token; mô hình Order / OrderProduct / Payment; rating sản phẩm.
- Các bài viết viết cho Python 3.7 / Django 3.2, nên khi áp dụng phải chuyển sang cú pháp Django 5.x. Chỉ lấy kỹ thuật, không lấy thư viện: dùng `os.environ` thay django-environ, `venv` thay pipenv, `default_token_generator` của `django.contrib.auth.tokens` thay six.

**Quản lý tài nguyên**
- Luôn đóng tệp, session, kết nối bằng context manager (`with`), kể cả transaction (`with transaction.atomic():`).
- Tuyệt đối không dùng biến toàn cục toàn app. Cấu hình đọc qua `django.conf.settings`.

**Quy trình**
- Mỗi lần chỉ làm một chức năng/API trong bảng chức năng.
- Không sửa mã kiểm thử (test) của hệ thống cho xanh: test lỗi thì sửa code, nếu nghi ngờ test sai thì báo lại cho người dùng. Không xóa, không `skip`, không nới lỏng assert.
- Test mới cho chức năng đang làm thì được thêm vào.

**Vận hành** (đối chiếu với `README.md`)
```
python manage.py makemigrations
python manage.py migrate
python manage.py collectstatic      # chỉ khi cần gom static
python manage.py createsuperuser
python manage.py runserver
pytest                              # hoặc: python manage.py test
```

**Giao tiếp**
- Trả lời bằng tiếng Việt, giữ nguyên thuật ngữ kỹ thuật và mã nguồn bằng tiếng Anh.
