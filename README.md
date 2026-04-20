# Python Socket Email Client (SMTP & POP3)

Đây là đồ án môn **Mạng máy tính**, triển khai một ứng dụng Email Client hoàn chỉnh từ đầu (from scratch) sử dụng **Socket Programming** trong Python. Dự án giao tiếp trực tiếp với các máy chủ mail thông qua giao thức SMTP (để gửi thư) và POP3 (để nhận thư), hoàn toàn không sử dụng các thư viện giao tiếp mail cấp cao có sẵn.

## Các tính năng nổi bật

### Phía Gửi thư (SMTP Client)
- **Giao tiếp Socket trực tiếp**: Tự động thực hiện quá trình handshaking (`HELO`, `MAIL FROM`, `RCPT TO`, `DATA`).
- **Hỗ trợ đính kèm (Attachments)**: Xử lý đọc file nhị phân, mã hóa Base64 và chia định dạng thư theo chuẩn `MIME multipart`. Kiểm soát dung lượng file gửi (tối đa 3MB).
- **Đa dạng người nhận**: Hỗ trợ đầy đủ các trường `To`, `CC`, và `BCC`.

### Phía Nhận và Quản lý thư (POP3 Client)
- **Tải thư tự động (Auto-fetch)**: Chạy một luồng ngầm (Background Thread) liên tục lắng nghe và tải email mới về máy dựa trên thời gian cấu hình.
- **Phân loại thư thông minh (Mail Categorization)**: Tự động quét `Subject` và nội dung thư (Content) để phân luồng vào các thư mục: `Inbox`, `Important`, `Work`, `Spam`, và `Project`.
- **Đánh dấu Trạng thái**: Theo dõi và lưu trữ trạng thái Đã đọc / Chưa đọc (Read/Unread) của từng email vào file `email_status.json`.
- **Parse EML Files**: Đọc và giải mã dữ liệu raw từ POP3 thành cấu trúc thư rõ ràng, cho phép tải ngược file đính kèm từ thư đã nhận.

## 🛠 Công nghệ và Thư viện sử dụng

- **Ngôn ngữ**: Python 3.x
- **Core Networking**: `socket` (TCP/IP communication)
- **Concurrency**: `threading` (cho tính năng Auto-load email)
- **Data Handling**: `json`, `email.mime`, `email.parser` (xử lý MIME headers và EML data).
