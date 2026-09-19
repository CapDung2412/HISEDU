# HISEDU Dataset Audit — Phase 1

Generated (UTC): `2026-09-19T09:34:06+00:00`

> Scope: read-only audit of `question/**/*.txt`, `answer/**/*.json`, and a basic DOCX-container health check for `du_lieu/*.docx`. Dataset files were not changed, renamed, or uploaded. `.env` was not read.

## Kết luận nhanh

- TXT: **327**; JSON: **327**.
- JSON parse strict thành công: **327/327**.
- Cặp hợp lệ: **327/327**.
- Câu hỏi TXT khớp chính xác trường `question` JSON: **327/327**.
- ID và chunk ID khớp: **327** và **327**.
- BOM UTF-8 phát hiện: **0** file.
- DOCX có container hợp lệ: **11/11**.
- Kiểm tra này xác nhận cấu trúc và tính nhất quán dữ liệu, không thay thế việc giáo viên thẩm định độ chính xác lịch sử. Trường `review_status` trong dữ liệu vẫn phải được tôn trọng.

## Phân loại toàn bộ cặp TXT/JSON

| Classification | Count |
| --- | --- |
| valid_pair | 327 |
| orphan_txt | 0 |
| orphan_json | 0 |
| duplicate | 0 |
| invalid_txt | 0 |
| invalid_json | 0 |
| ambiguous_pair | 0 |

Tổng file dataset đã phân loại: **654/654**.

## Khả năng đọc và schema JSON

Mọi JSON được kiểm tra bằng UTF-8 strict, JSON syntax strict, từ chối `NaN`/`Infinity`, phát hiện duplicate key, kiểm tra root object, field bắt buộc và kiểu dữ liệu.

| Field | Present | Missing | Observed types |
| --- | --- | --- | --- |
| answer | 327 | 0 | {"string": 327} |
| answer_type | 327 | 0 | {"string": 327} |
| chapter | 327 | 0 | {"object": 327} |
| chunk_id | 327 | 0 | {"string": 327} |
| dataset_name | 327 | 0 | {"string": 327} |
| difficulty | 327 | 0 | {"string": 327} |
| id | 327 | 0 | {"string": 327} |
| keywords | 327 | 0 | {"array": 327} |
| lesson | 327 | 0 | {"object": 327} |
| paired_question_file | 327 | 0 | {"string": 327} |
| provenance_note | 327 | 0 | {"string": 327} |
| question | 327 | 0 | {"string": 327} |
| review_status | 327 | 0 | {"string": 327} |
| source | 327 | 0 | {"object": 327} |
| title | 327 | 0 | {"string": 327} |
| version | 327 | 0 | {"string": 327} |

Schema đề xuất được lưu tại `reports/proposed_answer.schema.json`. Đây là schema suy ra từ dataset hiện tại, chưa phải hợp đồng production đã được phê duyệt.

## Thống kê nội dung

- Độ dài câu hỏi (ký tự): `{"min": 36, "max": 138, "mean": 78.98, "median": 77, "p95": 114}`
- Độ dài câu hỏi (từ tách theo khoảng trắng): `{"min": 8, "max": 31, "mean": 17.77, "median": 17, "p95": 26}`
- Độ dài câu trả lời (ký tự): `{"min": 35, "max": 280, "mean": 185.68, "median": 191, "p95": 242}`
- Độ dài câu trả lời (từ tách theo khoảng trắng): `{"min": 8, "max": 63, "mean": 40.02, "median": 41, "p95": 53}`
- Kích thước JSON (bytes): `{"min": 1516, "max": 2264, "mean": 1960.21, "median": 1974, "p95": 2170}`

Các số trên không phải token count. Cần đo lại bằng tokenizer đúng của checkpoint trước khi quyết định chunking hoặc truncation.

## Trường dùng cho retrieval

- Nên tạo `search_text` từ: `question`, `chapter.title`, `lesson.title`, `keywords`.
- Không nên embed JSON thô. `answer` và các trường provenance/review nên được trả về dưới dạng metadata gọn hoặc tải theo `record_id`.
- Không nên mặc định embed toàn bộ đáp án vì sẽ làm lệch mục tiêu tìm đúng câu hỏi.

## Audit đường dẫn

- File path đã kiểm tra: **665**.
- Path chứa non-ASCII: **654**.
- Path chứa khoảng trắng: **654**.
- Path chứa Windows reserved name: **0**.
- Path tuyệt đối dài ít nhất 260 ký tự: **0**.
- Độ dài path tuyệt đối: `{"min": 36, "max": 122, "mean": 105.81, "median": 109, "p95": 117}`.

Tên thư mục `Chương ...`, `Bài ...` chưa đạt ASCII/English. Basename câu hỏi tuy ASCII nhưng là tiếng Việt không dấu, chưa phải tên tiếng Anh. Đề xuất tránh dịch 327 câu hỏi bằng tay; dùng đường dẫn định danh ổn định:

`questions/chapter_NN/lesson_NN/question_NNN.txt`

`answers/chapter_NN/lesson_NN/question_NNN.json`

Nội dung và title tiếng Việt vẫn giữ trong TXT/JSON. Mapping mới chỉ là dry-run; chưa áp dụng.

| Current path (sample) | Proposed path |
| --- | --- |
| question/Chương 1/Bài 1/001-cach-mang-tu-san-anh-bung-no-vao-nam-nao.txt | questions/chapter_01/lesson_01/question_001.txt |
| question/Chương 1/Bài 1/002-nhung-luc-luong-xa-hoi-nao-la-luc-luong-chu-yeu-chong-che-do-phong-kien.txt | questions/chapter_01/lesson_01/question_002.txt |
| question/Chương 1/Bài 1/003-vi-sao-che-do-phong-kien-anh-tro-thanh-tro-ngai-doi-voi-su-phat-trien.txt | questions/chapter_01/lesson_01/question_003.txt |
| question/Chương 1/Bài 1/004-noi-chien-o-anh-dien-giua-nhung-luc-luong-nao.txt | questions/chapter_01/lesson_01/question_004.txt |
| question/Chương 1/Bài 1/005-su-kien-vua-charles-i-bi-xu-tu-nam-1649-co-y-nghia-gi.txt | questions/chapter_01/lesson_01/question_005.txt |
| question/Chương 1/Bài 1/006-cach-mang-vinh-quang-o-anh-dien-vao-nam-nao.txt | questions/chapter_01/lesson_01/question_006.txt |
| question/Chương 1/Bài 1/007-tuyen-ngon-nhan-quyen-nam-1689-o-anh-co-y-nghia-nhu-the-nao.txt | questions/chapter_01/lesson_01/question_007.txt |
| question/Chương 1/Bài 1/008-13-thuoc-dia-anh-o-bac-my-dau-tranh-chong-chinh-quoc-vi-nhung-nguyen-nhan.txt | questions/chapter_01/lesson_01/question_008.txt |
| question/Chương 1/Bài 1/009-su-kien-che-boston-dien-vao-nam-nao-va-phan-anh-dieu-gi.txt | questions/chapter_01/lesson_01/question_009.txt |
| question/Chương 1/Bài 1/010-tuyen-ngon-doc-lap-cua-13-thuoc-dia-anh-o-bac-my-duoc-thong-qua-ngay.txt | questions/chapter_01/lesson_01/question_010.txt |
| question/Chương 1/Bài 1/011-chien-thang-xa-to-ga-nam-1777-co-y-nghia-gi-doi-voi-cuoc-chien.txt | questions/chapter_01/lesson_01/question_011.txt |
| question/Chương 1/Bài 1/012-chien-tranh-gianh-doc-lap-cua-13-thuoc-dia-ket-thuc-bang-su-kien-nao.txt | questions/chapter_01/lesson_01/question_012.txt |

Dry-run mapping: **665** entry; unresolved: **0**; collision không phân biệt hoa thường: **0**.

## DOCX nguồn

| Path | Bytes | Valid DOCX container | ZIP error |
| --- | --- | --- | --- |
| du_lieu/Chuong_1_20_cau.docx | 37980 | True | None |
| du_lieu/Chuong_2_20_cau.docx | 38154 | True | None |
| du_lieu/Chuong_3_20_cau.docx | 38029 | True | None |
| du_lieu/LS_01_Cau_hoi.docx | 40237 | True | None |
| du_lieu/LS_02_Cau_hoi.docx | 40323 | True | None |
| du_lieu/LS_03_Cau_hoi.docx | 40472 | True | None |
| du_lieu/LS_04_Cau_hoi.docx | 40376 | True | None |
| du_lieu/LS_05_Cau_hoi.docx | 40231 | True | None |
| du_lieu/LS_06_Cau_hoi.docx | 40205 | True | None |
| du_lieu/LS_07_Cau_hoi.docx | 40576 | True | None |
| du_lieu/Tom_tat_Lich_su_8_Ket_noi_tri_thuc_Bai_1-9.docx | 41482 | True | None |

Audit này chỉ xác nhận DOCX là container ZIP hợp lệ và có phần document chính; chưa đối chiếu toàn bộ nội dung DOCX với 327 câu hỏi.

## CLIP và OCR

Dataset hiện tại không có ảnh ground truth. Nếu đầu vào là ảnh chụp câu hỏi in trên giấy/màn hình, CLIP thuần không đủ tin cậy vì CLIP không phải OCR. Pipeline khuyến nghị:

`ảnh → chỉnh hướng/chất lượng → OCR tiếng Việt → chuẩn hóa text → multilingual text retrieval → lấy answer JSON theo record_id`

CLIP có thể được giữ làm tín hiệu ảnh–văn bản phụ, với cùng checkpoint/preprocessing ở lúc index và query. Cần tập ảnh thật để đo Recall@K và hiệu chỉnh threshold; hiện chưa có cơ sở tuyên bố độ chính xác.

## Lỗi và cảnh báo

Không phát hiện lỗi hoặc cảnh báo tự động.

## Trạng thái

Giai đoạn 1 hoàn tất. Chưa đổi tên file, chưa viết pipeline CLIP/Pinecone, chưa đọc `.env`, và chưa gửi dữ liệu ra dịch vụ bên ngoài. Cần xác nhận `TIẾP TỤC` trước Giai đoạn 2.
