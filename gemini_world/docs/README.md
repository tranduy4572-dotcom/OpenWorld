# Gemini + OpenWorld

Điểm chạy duy nhất: **[CHAY.bat](../CHAY.bat)** ở thư mục cha.
Đọc nhanh **[BAT_DAU.txt](../BAT_DAU.txt)** nếu chưa quen thao tác.

## Cách dùng

Nhấp đúp CHAY.bat, gõ số và nhấn Enter:

| Số | Chức năng |
|---|---|
| 1 | Chạy Gemini thật, dùng key trong ../.env |
| 2 | Demo offline, không gọi API |
| 3 | Liệt kê model Gemini mà key truy cập được |
| 4 | Kiểm tra kết nối tới core OpenWorld |
| 5 | Chạy test cục bộ, có mock thay cho Gemini thật |
| 6 | Mở báo cáo HTML mới nhất từ runs/ |
| 0 | Thoát |

Ở chế độ Gemini, mỗi lượt vẫn hỏi xác nhận trước khi áp dụng đề xuất.
Sau khi một tác vụ kết thúc, chương trình quay lại menu.

## Cấu trúc

```text
gemini_world/
├─ CHAY.bat                # mở menu
├─ BAT_DAU.txt             # hướng dẫn ngắn
├─ .env                    # key/model cá nhân, giữ ở đây
├─ .env.example
├─ .gitignore
├─ openworld_config.json   # chọn ../OpenWorld-main
├─ app/                    # code và mẫu HTML
├─ tests/                  # kiểm tra extension
├─ docs/                   # tài liệu; kiem_tra/ giữ bằng chứng
└─ runs/                   # SQLite, trace, báo cáo từng lần chạy
```

Không cần mở app/ để sử dụng thông thường. Các file .bat cũ đã được thay bằng
các lựa chọn trong CHAY.bat. File HTML xuất trùng ở thư mục gốc đã được bỏ;
báo cáo gốc và toàn bộ dữ liệu runs/ vẫn còn.

## API key và kết nối

Điền GEMINI_API_KEY và GEMINI_MODEL trong ../.env rồi dùng lựa chọn 3 hoặc 1.
Chương trình đọc cùng file .env sau khi tổ chức lại. Không đưa key vào code.
Model/quota phải được kiểm tra bằng tài khoản của bạn; test mock không xác
nhận API thật. Đường dẫn core được lấy từ ../openworld_config.json hoặc
OPENWORLD_ROOT, tính từ gemini_world chứ không từ thư mục terminal.

## Luồng hoạt động

app/agent_lab.py gọi module core để quan sát, đọc bộ nhớ, kiểm quyền và cập
nhật thế giới. app/gemini_api.py chỉ cung cấp đề xuất. app/report.py dùng
app/viewer_template.html để xuất báo cáo. Dữ liệu mỗi lần chạy nằm trong
runs/; hai SQLite riêng là world.sqlite3 và memory.sqlite3.

Mục tiêu: Alice giúp Bob đạt 2 tài nguyên, ban đầu Alice 3/Bob 0.
Đây là mô phỏng cùng chủ sở hữu. Gemini không được sửa trực tiếp số dư
hoặc thực hiện thao tác ngoài đời. Hai SQLite không cùng một giao dịch
nguyên tử; extension phát hiện một số trạng thái lệch và dừng để kiểm tra.

## Lệnh cho terminal

Từ thư mục gemini_world:

```powershell
.\CHAY.bat
python -B app/menu.py
python -B app/verify_integration.py
python -B -m unittest discover -s tests -p "test_*.py" -v
python -B app/agent_lab.py --mode offline --steps 6 --auto --fresh
python -B app/agent_lab.py --mode gemini --steps 6 --fresh
```

Dùng cùng --data-dir và bỏ --fresh để tiếp tục bài thử đã lưu. Thêm --fresh
để tạo bài mới. Không xóa runs/ nếu còn cần bộ nhớ hoặc lịch sử các lần chạy.
