import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HistoricalSourceGallery } from "@/components/HistoricalSourceGallery";
import type { HistoricalImage, LearningAnswer } from "@/lib/types";

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
    expect(screen.getAllByRole("link", { name: /Xem hồ sơ nguồn/ })).toHaveLength(2);
    expect(screen.getByText("Tranh lịch sử")).toBeInTheDocument();
    expect(screen.getByText("Văn kiện")).toBeInTheDocument();

    const documentImage = screen.getByAltText(/Bản trang trí Tuyên ngôn/);
    expect(documentImage).toHaveClass("object-contain");
    expect(documentImage).toHaveAttribute("loading", "lazy");
  });

  it("không chèn ảnh không liên quan để lấp chỗ trống", () => {
    const { container } = render(
      <HistoricalSourceGallery question="Nhà Nguyễn chọn kinh đô ở đâu?" answer={answer} />
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("hiển thị đầy đủ nguồn, giấy phép và gợi ý quan sát từ backend", () => {
    const materials: HistoricalImage[] = [{
      id: "verified-document",
      title: "Một văn kiện đã kiểm duyệt",
      description: "Mô tả ngắn về văn kiện.",
      image_url: "/historical/declaration-rights-1789.jpg",
      source_url: "https://commons.wikimedia.org/wiki/File:Example.jpg",
      institution: "Bảo tàng kiểm thử",
      license: "CC0",
      license_url: "https://creativecommons.org/publicdomain/zero/1.0/",
      creator: "Tác giả kiểm thử",
      date: "Năm 1789",
      media_type: "document",
      alt: "Văn kiện lịch sử dùng trong kiểm thử",
      observation_prompt: "Em nhìn thấy biểu tượng nào?",
      relevance: "Liên quan trực tiếp đến nội dung vừa học."
    }];

    render(
      <HistoricalSourceGallery
        question="Một câu hỏi lịch sử"
        answer={answer}
        materials={materials}
      />
    );

    expect(screen.getByText("Tác giả kiểm thử")).toBeInTheDocument();
    expect(screen.getByText("Bảo tàng kiểm thử")).toBeInTheDocument();
    expect(screen.getByText(/Liên quan trực tiếp/)).toBeInTheDocument();
    expect(screen.getByText("Gợi ý quan sát ảnh")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "CC0" })).toHaveAttribute(
      "href",
      "https://creativecommons.org/publicdomain/zero/1.0/"
    );
  });

  it("loại URL ảnh không thuộc kho cục bộ và nguồn không an toàn", () => {
    const unsafe: HistoricalImage[] = [{
      id: "unsafe",
      title: "Ảnh không an toàn",
      description: "Không được hiển thị.",
      image_url: "https://tracker.example/image.jpg",
      source_url: "http://example.com/source",
      institution: "Không rõ",
      license: "Không rõ",
      media_type: "photograph",
      alt: "Ảnh không an toàn"
    }];

    const { container } = render(
      <HistoricalSourceGallery question="Câu hỏi" answer={answer} materials={unsafe} />
    );

    expect(container).toBeEmptyDOMElement();
  });
});
