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
          supports: ["Nội dung bài học"]
        }]}
      />
    );

    expect(screen.getByText("Chưa xác minh số trang — không hiển thị như trích dẫn SGK")).toBeInTheDocument();
    expect(screen.getByText(/Hỗ trợ nội dung: Nội dung bài học/)).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
