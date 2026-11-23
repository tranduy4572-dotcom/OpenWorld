# Tạo OpenWorld_Clean trên Windows

Mục tiêu: tạo bản **sao chép mới** của `OpenWorld-main` (mã Python cốt lõi, tests, tài liệu, demo) và loại bỏ tệp thừa của repo gốc như Node/npm, dữ liệu SQLite mẫu, cache và các bản xuất.

## Cách nhanh nhất

1. Giải nén ZIP này vào **cùng thư mục** với folder `OpenWorld-main` đã có trên máy, hoặc đặt ngay trong thư mục chứa `OpenWorld-main`.
2. Nhấp đúp **`TAO_OPENWORLD_CLEAN.bat`**.
3. Công cụ sẽ tự tìm `OpenWorld-main` và tạo folder **`OpenWorld_Clean`** mới cạnh đó.
4. Mở `OpenWorld_Clean` trong VS Code; đọc `BAT_DAU_TAI_DAY.md`.

Nếu máy không có bản gốc ở gần, script sẽ thử tải thư mục `OpenWorld-main` trực tiếp từ GitHub; cần Internet.

## Chỉ định chính xác folder gốc (nếu không tìm thấy)

Mở terminal tại thư mục chứa script, ví dụ:

```powershell
python .\tao_openworld_clean.py --source "D:\duong-dan\open_world\OpenWorld-main"
```

Hoặc chỉ định nơi lưu bản mới:

```powershell
python .\tao_openworld_clean.py --source "D:\duong-dan\OpenWorld-main" --output "D:\OpenWorld_Copies"
```

Để tải mới từ GitHub thay vì copy bản local:

```powershell
python .\tao_openworld_clean.py --github
```

## Giữ và bỏ gì?

**Giữ toàn bộ:** mã Python trong `src`, demo trong `examples`, `tests`, `benchmarks`, tài liệu `docs`, `scripts`, `research`, `.github` và root README/pyproject/LICENSE/AGENTS/SECURITY/CONTRIBUTING.

**Không đưa vào bản mới:** những file ở ngoài `OpenWorld-main` như `node.exe`, `node_modules`, `npm/npx`, các file `.txt` hướng dẫn riêng, dữ liệu SQLite demo, folder ghi log so sánh; bên trong chỉ bỏ cache, `.env`, thư mục build, file tạm, cơ sở dữ liệu phát sinh và nhị phân.

Tại sao vẫn giữ `tests` và `benchmarks`? Chúng là bằng chứng/kiểm thử có ích cho dự án nghiên cứu và tránh làm hỏng chức năng khi phát triển thêm. Nếu chỉ giữ demo mà xóa chúng, bạn khó phát triển OpenWorld thành sản phẩm thực thụ.

**An toàn:** Script không xóa/sửa mã nguồn gốc. Nếu có `OpenWorld_Clean`, nó tạo `OpenWorld_Clean_2`, không ghi đè. Khi lỗi đang copy, nó dọn thư mục tạm và không tạo bản sao chưa đầy đủ.
