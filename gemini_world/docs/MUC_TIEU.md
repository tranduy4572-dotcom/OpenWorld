# Mục tiêu và hành động của bài mô phỏng

Mở **../CHAY.bat** để chạy. Chọn 1 dùng Gemini thật hoặc 2 dùng luật offline.

Trong W3, World giữ tick, agent, quan hệ, số dư, thời tiết, sự kiện và nhật ký.
create_world tạo trạng thái ban đầu; gateway.observe cấp quan sát;
gateway.advance kiểm quyền và gọi luật chuyển trạng thái.

Bài thử hiện tại:

- Mục tiêu: Bob đạt 2 tài nguyên mô phỏng.
- Ban đầu: Alice 3/Bob 0.
- Bob đề xuất signal hoặc hold; Alice đề xuất transfer 1, signal hoặc hold.
- Gemini chỉ đề xuất JSON, không có quyền sửa DB hay chạy lệnh hệ thống.
- Người dùng xác nhận, host kiểm tra rồi mới thực hiện.

Các thiết lập nằm trong **../app/agent_lab.py**:
GOAL_BOB_BALANCE, START_ALICE, START_BOB và make_prompt().
Đổi luật/mục tiêu thì tạo bài mới bằng --fresh để không trộn lịch sử.

Core chỉ có transfer và signal. Hold được biểu diễn bằng một tick không có
action. Build, collect, trade hoặc viết file cần thiết kế công cụ/adapter
riêng; chỉ sửa prompt chưa tạo ra chức năng thực thi đó.

Mở menu 6 để xem báo cáo của lần chạy mới nhất, hoặc mở trực tiếp
../runs/<tên-lần-chạy>/XEM_DU_LIEU.html bằng trình duyệt.
