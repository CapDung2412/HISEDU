# Quy trình kiểm thử kín HISEDU với học sinh lớp 8

## Mục đích

Đo khả năng trả lời câu hỏi mới và khả năng từ chối đúng khi kho dữ liệu chưa đủ. Đây là kế hoạch kiểm thử; không được ghi số liệu vào hồ sơ trước khi giáo viên hoàn tất đối chiếu.

## Phạm vi thí điểm

- Đối tượng: một lớp 8, một chủ đề đã học.
- Người ra câu hỏi: học sinh/giáo viên không tham gia biên soạn kho câu hỏi.
- Câu hỏi phải được khóa trước khi chạy và kiểm tra để không trùng nguyên văn với `questions/`.
- Không thu tên, số điện thoại hoặc thông tin nhận dạng học sinh.

## Bộ câu hỏi tối thiểu

| Nhóm | Số câu | Mục đích |
| --- | ---: | --- |
| Đúng phạm vi, cách hỏi mới | 12 | Đo độ đúng và khả năng tìm bằng diễn đạt khác dữ liệu gốc. |
| Thiếu ngữ cảnh hoặc mơ hồ | 4 | Kiểm tra hệ thống có yêu cầu làm rõ hoặc từ chối thay vì đoán. |
| Ngoài kho kiến thức thí điểm | 4 | Kiểm tra thông báo “chưa đủ dữ liệu” đúng lúc. |
| **Tổng** | **20** | Mỗi câu chạy một lần ở cấu hình cố định. |

## Phiếu ghi kết quả

| Mã | Câu hỏi mới | Có trong phạm vi? | HTTP/kết quả | Đúng kiến thức? | Nguồn hỗ trợ đúng? | Từ chối đúng? | Thời gian (giây) | Giáo viên xác nhận | Ghi chú |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- |
| T01 |  |  |  |  |  |  |  |  |  |

Sao chép dòng `T01` thành `T02`–`T20` khi thực hiện. Không sửa đáp án tham chiếu sau khi đã xem câu trả lời của hệ thống.

## Tiêu chí chấm

- **Đúng kiến thức:** không sai mốc thời gian, nhân vật, quan hệ nguyên nhân–kết quả và không bỏ sót ý bắt buộc trong đáp án giáo viên.
- **Nguồn hỗ trợ đúng:** đoạn dữ liệu đối chiếu thực sự liên quan đến kết luận; trang SGK chỉ được ghi khi metadata đã xác minh.
- **Từ chối đúng:** câu ngoài phạm vi hoặc thiếu dữ liệu không được trả lời như một sự thật chắc chắn.
- **Thời gian:** ghi thời gian đầu-cuối cho từng câu; báo cáo trung vị, trung bình, P95 và số lượt trên 20 giây.
- Mỗi câu bị báo sai phải có trạng thái `pending_teacher_review` cho tới khi giáo viên kết luận.

## Chỉ số được phép công bố

1. `Số câu đúng / số câu đúng phạm vi`.
2. `Số lần từ chối đúng / số câu cần từ chối`.
3. `Số nguồn hỗ trợ đúng / số câu có trả lời`.
4. Thời gian phản hồi trung bình, trung vị và P95.
5. Số phản hồi đã được giáo viên duyệt, cần sửa và chưa duyệt.

Kết quả kiểm thử 60 câu hiện có là benchmark nội bộ từ dữ liệu tham chiếu, không thay thế kiểm thử kín này.
