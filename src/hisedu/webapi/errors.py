from __future__ import annotations


class WebApiError(RuntimeError):
    code = "HISEDU_ERROR"
    status_code = 500
    public_message = "Đã xảy ra lỗi. Vui lòng thử lại sau."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.public_message)
        self.message = message or self.public_message


class KnowledgeNotFoundError(WebApiError):
    code = "KNOWLEDGE_NOT_FOUND"
    status_code = 404
    public_message = "Chưa tìm thấy dữ liệu đủ phù hợp. Em hãy viết câu hỏi cụ thể hơn."


class AiServiceError(WebApiError):
    code = "AI_SERVICE_ERROR"
    status_code = 502
    public_message = "Trợ lý AI đang tạm thời không phản hồi. Vui lòng thử lại."


class AiTimeoutError(AiServiceError):
    code = "AI_TIMEOUT"
    status_code = 504
    public_message = "Trợ lý AI phản hồi quá lâu. Vui lòng thử lại."


class RetrievalServiceError(WebApiError):
    code = "RETRIEVAL_SERVICE_ERROR"
    status_code = 502
    public_message = "Kho kiến thức đang tạm thời không khả dụng."


class InvalidImageError(WebApiError):
    code = "INVALID_IMAGE"
    status_code = 415
    public_message = "Ảnh không hợp lệ. Chỉ hỗ trợ JPEG, PNG hoặc WebP."


class ImageTooLargeError(WebApiError):
    code = "IMAGE_TOO_LARGE"
    status_code = 413
    public_message = "Ảnh vượt quá dung lượng cho phép."


class QuizNotFoundError(WebApiError):
    code = "QUIZ_NOT_FOUND"
    status_code = 404
    public_message = "Bài quiz không tồn tại hoặc đã hết hạn."


class InvalidQuizSubmissionError(WebApiError):
    code = "INVALID_QUIZ_SUBMISSION"
    status_code = 422
    public_message = "Cần trả lời đúng 5 câu bằng các lựa chọn hợp lệ."


class RateLimitError(WebApiError):
    code = "RATE_LIMITED"
    status_code = 429
    public_message = "Em gửi câu hỏi quá nhanh. Vui lòng chờ một chút rồi thử lại."
