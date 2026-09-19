# HISEDU Web

Giao diện Next.js cho trợ lý học Lịch sử THCS.

## Chạy cục bộ

```bash
npm install
copy .env.local.example .env.local
npm run dev
```

File mẫu cấu hình frontend gọi backend tại `http://localhost:8000`. Nếu không khai báo
`NEXT_PUBLIC_API_BASE_URL`, frontend dùng API cùng origin. Không đặt API key OpenAI hoặc Pinecone
trong thư mục frontend.

## Kiểm tra

```bash
npm run typecheck
npm run lint
npm run test:run
npm run build
```

Toàn bộ component test dùng mock; các lệnh kiểm thử không gọi OpenAI, Pinecone hoặc API backend.

## API cần có

- `POST /api/questions/ask`
- `POST /api/questions/ask-image`
- `POST /api/quizzes/{quiz_id}/submit`
- `GET /api/health`

Frontend không nhận đáp án đúng trong response hỏi bài. `correct_option_id` chỉ được backend trả về
sau khi học sinh nộp quiz.
