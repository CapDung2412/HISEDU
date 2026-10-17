import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AnswerPanel } from "@/components/AnswerPanel";

describe("AnswerPanel", () => {
  it("làm nổi bật mốc thời gian và khối thông tin chính", () => {
    const { container } = render(
      <AnswerPanel
        question="Cách mạng tư sản Anh bùng nổ khi nào?"
        answer={{
          summary: "Nội chiến bùng nổ năm 1642 tại Anh.",
          citation_ids: [],
          sections: [{
            heading: "Diễn biến chính",
            content: "Giai đoạn 1642–1649 có nhiều biến động.",
            citation_ids: []
          }],
          key_points: ["Ghi nhớ mốc 1642 và đúng phạm vi nước Anh."]
        }}
      />
    );

    expect(screen.getByRole("heading", { name: "Thông tin chính cần nhớ" })).toBeInTheDocument();
    expect(container.querySelectorAll('mark[data-key-fact="true"]').length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText("Diễn biến chính")).toHaveClass("text-red-800");
  });

  it("làm nổi bật sự kiện, nhân vật và ý nghĩa nhưng vẫn render văn bản an toàn", () => {
    const { container } = render(
      <AnswerPanel
        question="Cách mạng Pháp có ý nghĩa gì?"
        answer={{
          summary: "Năm 1789, Cách mạng tư sản Pháp bùng nổ với nhân vật Maximilien Robespierre.",
          citation_ids: [],
          sections: [{
            heading: "Ý nghĩa lịch sử",
            content: "Ý nghĩa: mở đường cho chủ nghĩa tư bản phát triển. <img src=x onerror=alert(1)>",
            citation_ids: []
          }],
          key_points: []
        }}
      />
    );

    expect(container.querySelector('mark[data-fact-kind="time"]')).toHaveTextContent("1789");
    expect(container.querySelector('mark[data-fact-kind="event"]')).toHaveTextContent("Cách mạng tư sản Pháp");
    expect(container.querySelector('mark[data-fact-kind="person"]')).toHaveTextContent("Maximilien Robespierre");
    expect(container.querySelector('mark[data-fact-kind="meaning"]')).toHaveTextContent("Ý nghĩa");
    expect(container.querySelector("img")).not.toBeInTheDocument();
  });

  it("ưu tiên dữ liệu mindmap và không tô nhầm các cụm chữ thường", () => {
    const { container } = render(
      <AnswerPanel
        question="Cách mạng tư sản Anh diễn ra như thế nào?"
        mindmap={{
          title: "Cách mạng tư sản Anh",
          nodes: [
            { id: "n1", label: "Nội chiến Anh", description: "", type: "time", time: "1642" },
            { id: "n2", label: "Cách mạng Vinh quang", description: "", type: "event", time: "1688" },
            { id: "n3", label: "Oliver Cromwell", description: "", type: "person", people: ["Oliver Cromwell"] },
            { id: "n4", label: "củng cố chế độ quân chủ lập hiến", description: "", type: "meaning" }
          ],
          edges: []
        }}
        answer={{
          summary: "Năm 1642, phong trào đất nuôi cừu khiến các bên đối đầu. địa đem và đối địa chỉ là cụm chữ thử. Sau đó, Cách mạng Vinh quang tiếp tục củng cố chế độ vào năm 1688.",
          citation_ids: [],
          sections: [{
            heading: "Nhân vật và ý nghĩa",
            content: "Oliver Cromwell giữ vai trò nổi bật. Ý nghĩa: củng cố chế độ quân chủ lập hiến.",
            citation_ids: []
          }],
          key_points: []
        }}
      />
    );

    const marks = Array.from(container.querySelectorAll("mark"));
    const highlighted = marks.map((mark) => mark.textContent ?? "").join("|");
    expect(container.querySelector('mark[data-fact-kind="event"]')).toHaveTextContent("Cách mạng Vinh quang");
    expect(container.querySelector('mark[data-fact-kind="person"]')).toHaveTextContent("Oliver Cromwell");
    expect(container.querySelectorAll('mark[data-fact-kind="time"]')).toHaveLength(2);
    expect(highlighted).toContain("củng cố chế độ quân chủ lập hiến");
    for (const falsePositive of ["phong trào đất nuôi cừu", "địa đem", "đối đầu", "đối địa", "Sau đó"]) {
      expect(highlighted).not.toContain(falsePositive);
    }
  });

  it("giới hạn tên sự kiện dự phòng trước phần diễn giải", () => {
    const { container } = render(
      <AnswerPanel
        question="Cách mạng Vinh quang là gì?"
        answer={{
          summary: "Cách mạng Vinh quang tiếp tục củng cố chế độ.",
          citation_ids: [],
          sections: [],
          key_points: []
        }}
      />
    );

    expect(container.querySelector('mark[data-fact-kind="event"]')).toHaveTextContent(/^Cách mạng Vinh quang$/);
    expect(container.querySelectorAll("mark")).toHaveLength(1);
    expect(container.querySelector("mark")?.textContent).not.toContain("chế độ");
  });

  it("không cắt phần ý nghĩa giữa một từ khi câu dài", () => {
    const meaning = "Ý nghĩa: Sự kiện này đã xóa bỏ nhiều trở ngại phong kiến, tạo điều kiện thuận lợi cho nền kinh tế phát triển, củng cố những biến đổi xã hội và mở đường cho chủ nghĩa tư bản phát triển mạnh mẽ trong giai đoạn tiếp theo";
    const { container } = render(
      <AnswerPanel
        question="Sự kiện có ý nghĩa gì?"
        answer={{
          summary: `${meaning}.`,
          citation_ids: [],
          sections: [],
          key_points: []
        }}
      />
    );

    const highlightedMeaning = container.querySelector('mark[data-fact-kind="meaning"]');
    expect(meaning.length).toBeGreaterThan(140);
    expect(highlightedMeaning).toHaveTextContent(meaning);
    expect(highlightedMeaning?.textContent).toBe(meaning);
  });

  it("không tô các tên nhánh chung của sơ đồ tư duy", () => {
    const { container } = render(
      <AnswerPanel
        question="Bài học được chia như thế nào?"
        mindmap={{
          title: "Một chủ đề không xuất hiện trong câu trả lời",
          nodes: [
            { id: "root", label: "Chủ đề", description: "Bài học", type: "root" },
            { id: "event", label: "Diễn biến", description: "Nhánh chính", type: "event" },
            { id: "person", label: "Nhân vật", description: "Nhánh chính", type: "person" }
          ],
          edges: []
        }}
        answer={{
          summary: "Bài học có phần diễn biến và nhân vật.",
          citation_ids: [],
          sections: [],
          key_points: []
        }}
      />
    );

    expect(container.querySelectorAll("mark")).toHaveLength(0);
  });
});
