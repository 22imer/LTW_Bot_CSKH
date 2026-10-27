# Telegram CSKH Bot (AI agent)

Bot chăm sóc khách hàng cho hệ thống cafe. Khách nhắn tin tự do, một LLM agent (API bên thứ ba, tương thích OpenAI) trả lời bằng đúng 4 tool định sẵn. Không có nhân viên thật trong luồng này.

## Tính năng
- `/start`: lời chào và 2 nút nhanh (địa chỉ, liên hệ). Nút gọi thẳng dữ liệu, không tốn lượt LLM.
- Nhắn văn bản bất kỳ: agent trả lời tiếng Việt, nhớ 10 tin nhắn gần nhất.
- 4 tool: `list_stores`, `get_store_contact` (gửi danh thiếp điện thoại), `get_web_link` (liên kết web: xem menu/đặt mang đi, đặt bàn, thành viên), `submit_feedback` (ghi góp ý/khiếu nại vào SQLite).
- Agent xưng "Mây", tư vấn cách gọi món tại bàn, mang đi, đặt bàn, thanh toán, thành viên dựa trên `data/faq.md`.
- Menu lệnh (nút ☰ cạnh ô nhập tin): `/start`, `/diachi` (địa chỉ và giờ mở cửa), `/lienhe` (chọn cơ sở nhận danh thiếp). Bot tự đăng ký menu này khi khởi động.
- Tin không phải văn bản (ảnh, voice, sticker): trả lời cố định, không gọi LLM.
- Giới hạn: 10 tin/phút/khách, 1000 ký tự/tin, tối đa 3 vòng tool mỗi lượt. LLM lỗi thì xin lỗi khách.
- Lịch sử hội thoại giữ 30 ngày rồi tự xóa.

## Cấu hình
```bash
cp .env.example .env
```
| Biến | Ý nghĩa |
|---|---|
| `BOT_TOKEN` | Token từ `@BotFather` |
| `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` | LLM tương thích OpenAI. `LLM_BASE_URL` để trống nếu dùng OpenAI |
| `MENU_URL` | Web chính của quán (mặc định `shop.example.com`); bot nối thêm `/pickup`, `/reservations`, `/member` |
| `SHOP_NAME` | Tên quán dùng trong lời chào và prompt (mặc định `Mây Cafe`) |
| `STORES_FILE`, `FAQ_FILE`, `DB_PATH` | Tùy chọn: `data/stores.json`, `data/faq.md`, `data/cskh.sqlite3` |

Sửa `data/faq.md` khi quán đổi cách vận hành (giờ hẹn, chính sách hủy, thanh toán). Đây là nguồn duy nhất agent dùng để trả lời về cách quán hoạt động; sửa xong chạy lại `docker compose restart`.

## Chạy bằng Docker
```bash
docker compose up -d --build
docker compose logs -f bot
```
`./data` được mount vào container và chứa `stores.json` cùng file SQLite `data/cskh.sqlite3`. Container chạy user uid 1000, nên `./data` phải ghi được bởi user này.

## Chạy trực tiếp
```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
python bot.py
```

## Kịch bản demo
1. "Các quán mở cửa lúc mấy giờ, ở đâu?" → agent gọi `list_stores`.
2. "Cho mình số điện thoại cơ sở Quận 1" → agent gọi `get_store_contact`, bot gửi danh thiếp.
3. "Quán có trà đào không, giá bao nhiêu?" → agent gửi liên kết `/pickup`, không tự nêu món hay giá.
3b. "Mình muốn đặt bàn tối mai cho 4 người" → agent gửi liên kết `/reservations` và nhắc quy tắc giữ bàn.
4. "Nhân viên cơ sở 2 phục vụ chậm quá" → agent xin lỗi, gọi `submit_feedback`.
5. "Viết giúp mình bài thơ" → từ chối lịch sự, hướng về web chính.
6. Gửi một ảnh → bot trả lời cố định.
7. Xem dữ liệu: `sqlite3 data/cskh.sqlite3 "SELECT * FROM messages; SELECT * FROM feedback;"`.

## Test
```bash
python -m unittest discover -s tests -v
```

## Lưu ý
- Không commit `.env`.
- Bot dùng polling và xử lý tin lần lượt, đủ cho demo. Xem `ARCHITECTURE.md`.
