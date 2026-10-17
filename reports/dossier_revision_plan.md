# Kế hoạch chỉnh sửa hồ sơ Bảng A theo phản biện

## Nguyên tắc công bố

- Giữ nguyên kết quả đường cơ sở ngày 22/09/2026: **59/60 câu đạt**, thời gian phản hồi trung bình **23,32 giây**.
- **Dưới 20 giây** là mục tiêu cho lần đo tiếp theo, không phải kết quả hiện tại.
- Lượt không đạt là HTTP 502 do `Pinecone read timeout`; chưa có benchmark mới xác nhận lỗi đã được khắc phục.
- Bộ 60 câu là kiểm thử hồi quy từ dữ liệu có cặp hỏi–đáp, **không phải kiểm thử mù**.
- Unit test kỹ thuật không được trình bày thay cho thẩm định chuyên môn của giáo viên.

## Nội dung đã đưa vào bản DOCX chỉnh sửa

| Nội dung chỉnh sửa | Cách cải tiến | Ý nghĩa | Trạng thái |
|---|---|---|---|
| Phạm vi và baseline | Ghi rõ chỉ hỗ trợ kho tri thức Lịch sử lớp 8 hiện tại; giữ 59/60 và 23,32 giây. | Tránh biến mục tiêu thành thành tích. | Đã hoàn thành |
| Nguồn và giới hạn dữ liệu | Hiển thị nguồn/trạng thái; không bịa trang SGK. | Cho phép đối chiếu. | Đã hoàn thành |
| Đoạn dữ liệu đối chiếu | Hiển thị nội dung từ bản ghi truy xuất và trạng thái thẩm định; nói rõ đây không phải trích dẫn nguyên văn SGK khi chưa xác minh. | Phát hiện sai niên đại, nhân vật, thiếu sự kiện. | Đã hoàn thành |
| Nút “Báo câu trả lời sai” | Dùng mã câu trả lời do máy chủ cấp; khi có báo cáo, máy chủ lưu đúng câu hỏi, câu trả lời, nguồn, dữ liệu đối chiếu, nhận xét và thời điểm vào JSONL `pending_teacher_review`. | Tạo hồ sơ đủ dữ liệu cho giáo viên đối chiếu, không tin nội dung do trình duyệt tự khai. | Đã hoàn thành; chưa có dashboard giáo viên |
| Dashboard giáo viên | Duyệt đúng/sai/thiếu/chưa rõ; lưu người duyệt và thời điểm. | Xác nhận chuyên môn thật. | Mục tiêu; chưa có dashboard |
| Cổng dừng dưới ngưỡng | Backend dừng trước bước sinh nội dung khi truy xuất mang nhãn `below_threshold`; chưa đặt ngưỡng mặc định trước khi hiệu chuẩn. | Hạn chế đoán khi thiếu căn cứ. | Đã hoàn thành cơ chế; đang hiệu chuẩn |
| Kiểm thử mù | Quy trình 20 câu: 12 trong phạm vi với cách hỏi mới, 4 mơ hồ, 4 ngoài phạm vi; đo riêng trả lời đúng và từ chối đúng. | Đo khái quát và biết giới hạn. | Mục tiêu; đã có quy trình, chưa có số liệu |
| Tốc độ | Đo riêng các giai đoạn, tối ưu, rồi chạy lại cùng quy trình 60 câu. | So sánh công bằng với baseline. | Mục tiêu: trung bình < 20 giây |
| Tiến trình và hủy | Hiển thị các giai đoạn, số giây đã chờ và dùng `AbortController` để hủy request phía client; chưa khẳng định hủy tính toán server. | Giảm cảm giác chờ bị động. | Đã hoàn thành phần client |
| Tư liệu xác thực thí điểm | 4 hồ sơ Commons phạm vi công cộng/CC0 cho Cách mạng Anh/Pháp, kèm chú thích, nơi lưu giữ, giấy phép và link gốc. | Bổ sung chứng cứ trực quan có xuất xứ. | Đã hoàn thành trong 2 chủ đề |
| Mở rộng kho hình ảnh | Bổ sung tư liệu có xuất xứ/quyền sử dụng cho các chủ đề lớp 8 còn lại. | Không dùng hình thay thế chỉ để trang trí. | Đang triển khai |
| Mở rộng nội dung | Thí điểm một chủ đề lớp 8, sau đó toàn lớp 8, cuối cùng mới đến lớp 6/7/9. | Kiểm soát chất lượng theo giai đoạn. | Mục tiêu |

## Trình tự thực hiện và nghiệm thu

1. Hiệu chuẩn cổng dừng và chạy quy trình 20 câu trong `reports/blind_classroom_pilot_protocol.md`; giáo viên chấm độ đúng, nhóm kỹ thuật chỉ tổng hợp số liệu.
2. Khắc phục timeout có giới hạn, chạy lại câu lỗi và toàn bộ 60 câu; lưu JSON kết quả mới thay vì sửa file baseline.
3. Xây dashboard giáo viên trên hàng đợi `pending_teacher_review`; không gắn nhãn đã duyệt tự động.
4. Đo trung bình, P50, P95 và tỷ lệ timeout. Chỉ ghi “đạt < 20 giây” sau lần đo có thể tái lập.
5. Mở rộng kho tư liệu xác thực và thí điểm một chủ đề lớp 8. Chỉ mở rộng khi có ngưỡng nghiệm thu được giáo viên thống nhất trước.

## Đầu ra

- Bản gốc được giữ nguyên: `AI2026 - Hồ sơ Bảng A.docx`.
- Script tạo bản sao: `scripts/revise_dossier_expert_feedback.py`.
- Bản sao dự kiến: `AI2026 - Hồ sơ Bảng A - Bản chỉnh sửa theo phản biện.docx`.
- PDF gốc không bị ghi đè. Chỉ xuất PDF mới sau khi kiểm tra bố cục DOCX trên Word/LibreOffice.
