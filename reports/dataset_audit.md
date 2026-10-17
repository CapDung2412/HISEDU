# HISEDU Dataset Audit — Phase 1

Generated (UTC): `2026-09-20T01:48:43+00:00`

> Scope: read-only audit of `questions/**/*.txt`, `answers/**/*.json`, and a basic DOCX-container health check for `source_documents/*.docx`. Dataset files were not changed, renamed, or uploaded. `.env` was not read.

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
- Kích thước JSON (bytes): `{"min": 1490, "max": 2207, "mean": 1905.82, "median": 1917, "p95": 2111}`

Các số trên không phải token count. Cần đo lại bằng tokenizer đúng của checkpoint trước khi quyết định chunking hoặc truncation.

## Trường dùng cho retrieval

- Nên tạo `search_text` từ: `question`, `chapter.title`, `lesson.title`, `keywords`.
- Không nên embed JSON thô. `answer` và các trường provenance/review nên được trả về dưới dạng metadata gọn hoặc tải theo `record_id`.
- Không nên mặc định embed toàn bộ đáp án vì sẽ làm lệch mục tiêu tìm đúng câu hỏi.

## Audit đường dẫn

- File path đã kiểm tra: **665**.
- Path chứa non-ASCII: **0**.
- Path chứa khoảng trắng: **0**.
- Path chứa Windows reserved name: **0**.
- Path tuyệt đối dài ít nhất 260 ký tự: **0**.
- Độ dài path tuyệt đối: `{"min": 52, "max": 68, "mean": 56.52, "median": 56, "p95": 57}`.

Đường dẫn hiện dùng định danh tiếng Anh/ASCII ổn định; nội dung câu hỏi và title tiếng Việt vẫn được giữ trong TXT/JSON:

`questions/chapter_NN/lesson_NN/question_NNN.txt`

`answers/chapter_NN/lesson_NN/question_NNN.json`

Mapping bên dưới chỉ xuất hiện nếu audit phát hiện path còn cần chuẩn hóa.

| Current path (sample) | Proposed path |
| --- | --- |

Dry-run mapping: **0** entry; unresolved: **0**; collision không phân biệt hoa thường: **0**.

## DOCX nguồn

| Path | Bytes | Valid DOCX container | ZIP error |
| --- | --- | --- | --- |
| source_documents/chapter_01_20_questions.docx | 37980 | True | None |
| source_documents/chapter_02_20_questions.docx | 38154 | True | None |
| source_documents/chapter_03_20_questions.docx | 38029 | True | None |
| source_documents/history_01_questions.docx | 40237 | True | None |
| source_documents/history_02_questions.docx | 40323 | True | None |
| source_documents/history_03_questions.docx | 40472 | True | None |
| source_documents/history_04_questions.docx | 40376 | True | None |
| source_documents/history_05_questions.docx | 40231 | True | None |
| source_documents/history_06_questions.docx | 40205 | True | None |
| source_documents/history_07_questions.docx | 40576 | True | None |
| source_documents/history_8_summary_lessons_01_09.docx | 41482 | True | None |

Audit này chỉ xác nhận DOCX là container ZIP hợp lệ và có phần document chính; chưa đối chiếu toàn bộ nội dung DOCX với 327 câu hỏi.

## CLIP và OCR

Dataset hiện tại không có ảnh ground truth. Nếu đầu vào là ảnh chụp câu hỏi in trên giấy/màn hình, CLIP thuần không đủ tin cậy vì CLIP không phải OCR. Pipeline khuyến nghị:

`ảnh → chỉnh hướng/chất lượng → OCR tiếng Việt → chuẩn hóa text → multilingual text retrieval → lấy answer JSON theo record_id`

CLIP có thể được giữ làm tín hiệu ảnh–văn bản phụ, với cùng checkpoint/preprocessing ở lúc index và query. Cần tập ảnh thật để đo Recall@K và hiệu chỉnh threshold; hiện chưa có cơ sở tuyên bố độ chính xác.

## Lỗi và cảnh báo

Không phát hiện lỗi hoặc cảnh báo tự động.

## Trạng thái

Giai đoạn 1 hoàn tất. Chưa đổi tên file, chưa viết pipeline CLIP/Pinecone, chưa đọc `.env`, và chưa gửi dữ liệu ra dịch vụ bên ngoài. Cần xác nhận `TIẾP TỤC` trước Giai đoạn 2.
