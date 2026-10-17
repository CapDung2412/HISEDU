import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HistoricalSourceGallery } from "@/components/HistoricalSourceGallery";
import type { LearningAnswer } from "@/lib/types";

const answer: LearningAnswer = {
  summary: "Sự kiện mở đầu năm 1789.",
  sections: [],
  key_points: [],
  citation_ids: []
};

describe("HistoricalSourceGallery", () => {
  it("chỉ hiển thị tư liệu khớp chủ đề đã tuyển chọn", () => {
    render(
      <HistoricalSourceGallery
        question="Cách mạng tư sản Pháp diễn ra như thế nào?"
        answer={answer}
      />
    );

    expect(screen.getByRole("heading", { name: "Tư liệu lịch sử xác thực" })).toBeInTheDocument();
    expect(screen.getByText(/Cuộc tấn công pháo đài Bastille/)).toBeInTheDocument();
    expect(screen.queryByText(/Trận Naseby/)).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /Xem hồ sơ tư liệu/ })).toHaveLength(2);
  });

  it("không chèn ảnh không liên quan để lấp chỗ trống", () => {
    const { container } = render(
      <HistoricalSourceGallery question="Nhà Nguyễn chọn kinh đô ở đâu?" answer={answer} />
    );

    expect(container).toBeEmptyDOMElement();
  });
});
