# HISEDU

HISEDU là trợ lý học Lịch sử 8 gồm hai phần:

- Pipeline truy xuất `TXT + JSON → multilingual CLIP → Pinecone`.
- Website dành cho học sinh THCS: hỏi bằng văn bản hoặc ảnh, nhận lời giải, mindmap, nguồn tham khảo, video đã được hậu kiểm và quiz 5 câu.

Backend nằm trong `src/hisedu/webapi/`; frontend Next.js nằm trong `web/`.

## Trạng thái dữ liệu

- `questions/` và `answers/`: 327 cặp đã audit, UTF-8 và JSON hợp lệ.
- Đường dẫn đã chuẩn hóa thành `chapter_NN/lesson_NN/question_NNN.*`.
- `source_documents/`: 11 DOCX nguồn.
- Báo cáo hiện tại: `reports/dataset_audit.md`.
- Mapping đổi tên: `reports/path_rename_mapping.json`.
- Backup trước đổi tên: `backups/pre_path_normalization.zip`.

Audit kỹ thuật không thay thế việc giáo viên thẩm định độ chính xác lịch sử. Tất cả record hiện vẫn có `review_status` chờ giáo viên duyệt. Trường `source.page_number` của dataset hiện đều là `null`, URL SGK là trang cổng chung và câu trả lời là nội dung diễn đạt lại, không phải trích dẫn nguyên văn. Vì vậy giao diện chỉ được hiển thị “Dữ liệu hiện tại chưa ghi nhận số trang SGK”, không được tự tạo số trang.

## Kiến trúc

Luồng ingest:

`TXT + JSON → record chuẩn → multilingual CLIP text embedding → Pinecone`

Luồng hỏi bằng văn bản:

`câu hỏi → CLIP text embedding → Pinecone → OpenAI Responses API → hậu kiểm nguồn → YouTube Data API (lọc channelId) → answer + mindmap + quiz`

Luồng hỏi bằng ảnh:

1. Mặc định: `ảnh → PaddleOCR tiếng Việt → CLIP multilingual text embedding → Pinecone`.
2. Chế độ `hybrid` chỉ dùng `CLIP image embedding` dự phòng khi OCR không đọc được chữ.
3. Kết quả truy xuất đi qua cùng luồng sinh bài học như câu hỏi văn bản.

CLIP không phải OCR. Với ảnh chủ yếu chứa chữ, nên dùng `hybrid` hoặc `ocr`; số, mốc năm và tên riêng cần được đánh giá trên ảnh điện thoại thật.

Model mặc định là một cặp đã được align chung không gian 512 chiều:

- Text: `sentence-transformers/clip-ViT-B-32-multilingual-v1`.
- Image: `sentence-transformers/clip-ViT-B-32`.

Chỉ trường `question` được embed để tránh nhiễu và truncation. Answer cùng metadata được lưu để trả kết quả; JSON gốc vẫn là nguồn dữ liệu chuẩn. Backend web khởi tạo CLIP và kết nối Pinecone theo nhu cầu, không ingest hoặc tạo index khi khởi động.

## Yêu cầu môi trường

- Python 3.10 trở lên.
- Node.js 20 trở lên và npm để chạy frontend.
- Pinecone index `hisedu-clip-v1` đã ingest dữ liệu.
- OpenAI API key để sinh câu trả lời, mindmap và quiz.
- YouTube Data API v3 key để tìm video trong danh sách kênh cho phép.

## Cài đặt backend

Tại thư mục gốc dự án:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Điền `PINECONE_API_KEY`, `CHATGPT_API_KEY` và `YOUTUBE_API_KEY` thật vào `.env`. Không commit file này.

Để bật OCR local:

```powershell
python -m pip install -e ".[ocr]"
```

Extra `ocr` cài cả PaddleOCR và PaddlePaddle CPU. Lần dùng OCR đầu tiên có thể tải model weights; không commit model cache.

## Cài đặt frontend

```powershell
Set-Location .\web
npm install
if (-not (Test-Path .env.local)) { Copy-Item .env.local.example .env.local }
```

Frontend chỉ được chứa địa chỉ công khai của backend. Không đặt OpenAI key, Pinecone key hoặc bất kỳ secret nào trong biến có tiền tố `NEXT_PUBLIC_`.

## Cấu hình backend

Các biến được mô tả đầy đủ trong `.env.example`.

| Biến | Mặc định trong code | Ý nghĩa |
| --- | --- | --- |
| `PINECONE_API_KEY` | Không có | Bắt buộc khi truy vấn hoặc ingest Pinecone. |
| `PINECONE_INDEX_NAME` | `hisedu-clip-v1` | Index đã chứa embedding HISEDU. |
| `PINECONE_NAMESPACE` | `history8-v1-0-0` | Namespace của dataset. |
| `CHATGPT_API_KEY` | Không có | OpenAI API key, chỉ đọc ở backend. |
| `YOUTUBE_API_KEY` | Không có | YouTube Data API v3 key, chỉ đọc ở backend. |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Model dùng với Responses API và Structured Outputs. |
| `HISEDU_ENABLE_WEB_SEARCH` | `false` | Bật tối đa một web-search tool call cho nguồn ngoài; tìm video dùng YouTube API riêng. |
| `HISEDU_YOUTUBE_TIMEOUT_SECONDS` | `5` | Timeout cho một lần tìm video. |
| `HISEDU_YOUTUBE_CACHE_TTL_SECONDS` | `86400` | Cache kết quả tìm video, kể cả kết quả rỗng, để tiết kiệm quota. |
| `HISEDU_OPENAI_TIMEOUT_SECONDS` | `30` | Timeout của lượt sinh OpenAI. |
| `HISEDU_CACHE_TTL_SECONDS` | `900` | TTL cache bài học trong bộ nhớ tiến trình. |
| `HISEDU_QUIZ_TTL_SECONDS` | `1800` | Thời gian quiz còn hợp lệ trong bộ nhớ tiến trình. |
| `HISEDU_RATE_LIMIT_REQUESTS` | `20` | Số request tối đa cho mỗi IP trong một cửa sổ. |
| `HISEDU_RATE_LIMIT_WINDOW_SECONDS` | `60` | Độ dài cửa sổ rate limit. |
| `HISEDU_CORS_ORIGINS` | `http://localhost:3000` | Danh sách origin chính xác, phân tách bằng dấu phẩy. |
| `HISEDU_MAX_IMAGE_BYTES` | `5242880` | Dung lượng ảnh tối đa, tính bằng byte. |
| `HISEDU_MAX_IMAGE_PIXELS` | `20000000` | Số pixel tối đa sau khi giải mã ảnh. |
| `HISEDU_PROMPT_VERSION` | `hisedu-web-v6-youtube-api-video` | Phiên bản prompt dùng trong cache key. |

`.env.example` chủ động đặt `HISEDU_ENABLE_WEB_SEARCH=false` để hạn chế chi phí khi phát triển. Khi bật web search, backend chỉ giữ URL xuất hiện trong kết quả công cụ và thuộc danh sách domain tin cậy.

## Gợi ý video bằng YouTube Data API

Backend gọi `search.list` tối đa một lần cho mỗi cache miss, sau đó lọc cứng theo `channelId`. Danh sách cho phép hiện gồm EZ Sử, HTV Tin Tức, VTV24, Sử Lược - Tóm Tắt Lịch Sử và Dòng Máu Việt. URL hoặc tên kênh do mô hình AI tạo không được sử dụng. Kết quả được cache 24 giờ; thiếu key, lỗi API hoặc hết quota thì bài học vẫn hoạt động và trả `videos=[]`.

Cache, quiz store và rate limiter hiện là bộ nhớ trong từng tiến trình. Chúng phù hợp chạy local hoặc một worker. Nếu triển khai nhiều worker hoặc nhiều máy, cần thay bằng kho dùng chung như Redis để quiz, cache và rate limit nhất quán.

Không đặt `HISEDU_MIN_SCORE` trước khi có tập ảnh ground truth. Cosine similarity không phải xác suất; threshold cần được hiệu chỉnh thực nghiệm.

## Chạy website

Mở hai terminal tại thư mục dự án.

Backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn hisedu.webapi.app:app --host 127.0.0.1 --port 8000 --reload
```

Frontend:

```powershell
Set-Location .\web
npm run dev
```

Mở `http://localhost:3000`. Tài liệu OpenAPI local ở `http://localhost:8000/api/docs`.

`GET /api/health` chỉ kiểm tra cấu hình cục bộ; endpoint này không tải CLIP và không gọi Pinecone hoặc OpenAI.

## API

### `POST /api/questions/ask`

Body JSON:

```json
{
  "question": "Cách mạng tư sản Anh bùng nổ vào năm nào?",
  "top_k": 5
}
```

### `POST /api/questions/ask-image`

Gửi `multipart/form-data`:

- `file`: JPG, PNG hoặc WebP.
- `question`: mô tả bổ sung, không bắt buộc.
- `top_k`: từ 1 đến 10, mặc định 5.
- `mode`: `clip`, `ocr` hoặc `hybrid`; mặc định `hybrid`.

### `POST /api/quizzes/{quiz_id}/submit`

Body JSON là ánh xạ ID câu hỏi sang ID lựa chọn:

```json
{
  "answers": {
    "q1": "a",
    "q2": "c",
    "q3": "b",
    "q4": "d",
    "q5": "a"
  }
}
```

Một quiz hợp lệ có đúng 5 câu nên request chấm bài phải gửi đủ 5 lựa chọn. Đáp án đúng và giải thích chỉ được trả về sau khi nộp.

### `GET /api/health`

Trả trạng thái cấu hình backend mà không gọi dịch vụ bên ngoài.

## Ước lượng lượt gọi và cách tiết kiệm quota

Trong trường hợp bình thường:

| Tình huống | Pinecone | OpenAI Responses | Web search | YouTube Search |
| --- | ---: | ---: | ---: | ---: |
| Text, cache miss | 1 | 2 (bài học + quiz) | 0 khi tắt; tối đa 1 khi bật | Tối đa 1 nếu cache video miss |
| Text, cache hit | 1 | 0 | 0 | 0 |
| Ảnh `clip` hoặc `ocr`, cache miss | 1 | 2 | 0 hoặc tối đa 1 | Tối đa 1 nếu cache video miss |
| Ảnh `hybrid`, cache miss | 2 | 2 | 0 hoặc tối đa 1 | Tối đa 1 nếu cache video miss |
| Health, validate-data và test mock | 0 | 0 | 0 | 0 |

Cache vẫn cần truy xuất Pinecone để xác định các record phù hợp trước khi tạo cache key. Mỗi cache hit tạo một `quiz_id` mới nhưng không gọi lại OpenAI. Backend không tự retry OpenAI hay YouTube, nhằm giữ thời gian chờ và quota có thể dự đoán.

Để tiết kiệm quota trong quá trình phát triển:

1. Đặt `HISEDU_ENABLE_WEB_SEARCH=false`.
2. Giữ nguyên `top_k=5` và không chạy lại ingest nếu dataset/model không đổi.
3. Dùng test mock thay vì gọi endpoint với credential thật.
4. Chỉ thực hiện một smoke test live có kiểm soát sau khi toàn bộ test local đạt.

## CLI retrieval

Kiểm tra dataset mà không cần model hoặc Pinecone:

```powershell
hisedu validate-data
```

Tạo hoặc kiểm tra Pinecone index, encode và upsert 327 record:

```powershell
hisedu ingest
```

Không chạy lại lệnh ingest chỉ để khởi động website. Vector ID là `chunk_id`, nên ingest lại sẽ overwrite cùng record thay vì tạo duplicate. Nếu index có dimension hoặc metric khác, chương trình dừng và không tự xóa index.

Truy vấn ảnh:

```powershell
hisedu query-image .\samples\question.jpg --mode clip --top-k 5
hisedu query-image .\samples\question.jpg --mode hybrid --top-k 5
```

Smoke test bằng text trong cùng CLIP space:

```powershell
hisedu query-text "Cách mạng tư sản Anh bùng nổ năm nào?" --top-k 5
```

## Kiểm thử không dùng API thật

Backend và pipeline retrieval:

```powershell
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Frontend:

```powershell
Set-Location .\web
npm run typecheck
npm run lint
npm run test:run
npm run build
```

Các test backend dùng fake retrieval/OpenAI/Pinecone; component test frontend dùng mock. Những lệnh trên không chủ động gọi OpenAI, Pinecone hoặc web search.

Đã xác nhận cục bộ: 327/327 bản ghi dữ liệu hợp lệ, 47/47 test Python đạt, 8/8 test frontend đạt, TypeScript/ESLint đạt và Next.js build production thành công. Website chưa được kiểm thử live end-to-end với OpenAI, Pinecone và YouTube API sau khi ghép frontend/backend nhằm tránh tiêu tốn quota. Trước production cần:

- Một smoke test live có giới hạn quota.
- Một holdout ảnh điện thoại gồm ảnh rõ, mờ, nghiêng, thiếu sáng và các câu có mốc năm gần nhau.
- Đánh giá Recall@K, OCR CER/WER và hiệu chỉnh confidence threshold.
- Giáo viên duyệt nội dung lịch sử và bổ sung metadata số trang SGK.

## Tài liệu nền tảng

- [OpenAI Responses API](https://developers.openai.com/api/reference/python/resources/responses/methods/create)
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenAI web search](https://developers.openai.com/api/docs/guides/tools-web-search)
- [Pinecone Python SDK quickstart](https://sdk.pinecone.io/python/getting-started/quickstart.html)
- [Multilingual CLIP model card](https://huggingface.co/sentence-transformers/clip-ViT-B-32-multilingual-v1)
- [Sentence Transformers image search](https://sbert.net/examples/sentence_transformer/applications/image-search/README.html)
- [PaddleOCR general OCR pipeline](https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html)
