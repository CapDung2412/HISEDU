import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SourceList } from "@/components/SourceList";

describe("SourceList", () => {
  it("không bịa trang SGK và loại bỏ URL nguy hiểm", () => {
    render(
      <SourceList
        sources={[{
          id: "S1",
          title: "Lịch sử và Địa lí 8",
          publisher: "Nhà xuất bản Giáo dục",
          type: "dataset",
          url: "javascript:alert(1)",
          grade: 8,
          book_series: "Kết nối tri thức với cuộc sống",
          page_status: "unverified",
          supports: ["Nội dung bài học"],
          evidence_excerpt: "Cách mạng tư sản Anh bùng nổ năm 1642.",
          review_status: "pending_teacher_review",
          provenance_note: "Câu trả lời được diễn đạt lại; không phải trích dẫn nguyên văn SGK."
        }]}
      />
    );

    expect(screen.getByText("Chưa xác minh số trang — không hiển thị như trích dẫn SGK")).toBeInTheDocument();
    expect(screen.getByText(/Hỗ trợ nội dung: Nội dung bài học/)).toBeInTheDocument();
    expect(screen.getByText("Nội dung tham chiếu lưu trong HISEDU")).toBeInTheDocument();
    expect(screen.getByText(/Cách mạng tư sản Anh bùng nổ năm 1642/)).toBeInTheDocument();
    expect(screen.getByText(/Câu trả lời được diễn đạt lại/)).toBeInTheDocument();
    expect(screen.getByText("Đang chờ giáo viên thẩm định")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
