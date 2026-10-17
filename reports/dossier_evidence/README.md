# Minh chứng hồ sơ HISEDU

Thư mục này phục vụ hồ sơ dự thi Bảng A, cập nhật ngày 17/10/2026.

## Nội dung đã xác minh

- `01_dataset_audit.png`: tóm tắt số liệu từ `reports/dataset_audit.json`.
- `02_vector_pipeline.png`: tóm tắt số liệu từ `reports/ingest_manifest.json`.
- `03_ui_result_demo.png`: minh họa kết quả bằng câu hỏi và câu trả lời thật tại `answers/chapter_01/lesson_02/question_009.json`.
- `04_before_after_fix.png`: tổng hợp lỗi đã sửa và kết quả kiểm thử hiện tại.
- `11_test_results.png`: kết quả kiểm thử kỹ thuật và benchmark được cập nhật ngày 17/10/2026.
- `12_historical_images.png`: giao diện gợi ý ảnh tư liệu theo đúng chủ đề, kèm nguồn, giấy phép và câu hỏi quan sát.
- `prompt_01_dataset_clip.txt`: prompt gốc dùng cho giai đoạn audit dataset, CLIP và Pinecone.
- `prompt_02_website.txt`: prompt gốc dùng cho giai đoạn xây dựng website.

Kết quả chạy ngày 17/10/2026:

- Backend: 87/87 kiểm thử đạt.
- Frontend: 31/31 kiểm thử đạt.
- Dataset: 327/327 cặp TXT–JSON hợp lệ về cấu trúc.
- Pinecone: 327/327 vector được upsert theo manifest.

## Bắt buộc bổ sung thủ công trước khi nộp

1. Tên và thông tin giáo viên/chuyên gia hướng dẫn, nếu đội có người hướng dẫn.
2. Liên kết Google Drive minh chứng và quyền “Bất kỳ ai có đường liên kết đều có thể xem”.
3. Video trình diễn sản phẩm và ảnh chụp lịch sử hội thoại đầy đủ.
4. Chữ ký thật của đại diện đội thi và giáo viên/người hướng dẫn (nếu có).
5. Kết quả đánh giá chuyên môn do giáo viên xác nhận; không thay bằng số liệu unit test.
