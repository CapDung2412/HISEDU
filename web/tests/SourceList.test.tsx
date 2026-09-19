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
          type: "sgk",
          url: "javascript:alert(1)",
          supports: ["Nội dung bài học"]
        }]}
      />
    );

    expect(screen.getByText("Dữ liệu hiện tại chưa ghi nhận số trang")).toBeInTheDocument();
    expect(screen.getByText(/Hỗ trợ nội dung: Nội dung bài học/)).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
