Đây là phần basic của đồ án, những điểm chính là:

-Xác thực thông qua log in (user và password)

-Gửi file (server)

-Tải file (clients)

Những cú pháp có thể thắc mắc:
"\r\n" ý nghĩa là giống phím "Enter" trong máy tính, báo hiệu là kết thúc câu, nếu không có thì server bị đứng

Ưu điểm khi làm UDP với TCP:
-Khi gửi file có dung lượng thấp thì nhanh hơn so với TCP và sẽ có mất mát ít hơn


Phần chuyển đổi active/passive:

- Tạo 1 class chung cho node với các chức năng (Node.py):
    + Chuyển đổi protocol TCP/UDP
    + Chuyển đổi mode active(client) và passive(server)
- Gọi class Node dưới 2 file serverNode và clientNode để chạy 
- Các file đang dùng: Node.py, FTPCommandHandle.py, serverNode.py, clientNode.py
- Để chạy node và giao tiếp cơ bản:
    + Chạy serverNode.py, tạo userName và password, chạy clientNode.py và kết nối tới server
- Để demo tính năng xử lý multi thread: chạy file MultiThreadDemo.py
