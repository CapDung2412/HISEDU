import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { MindMap } from "@/components/MindMap";
import type { MindMapData } from "@/lib/types";

const mindmap: MindMapData = {
  title: "Chiến thắng Bạch Đằng",
  nodes: [
    { id: "root", label: "Bạch Đằng 938", description: "Chiến thắng lịch sử", type: "root" },
    { id: "time", label: "Năm 938", description: "Thời điểm diễn ra trận đánh", type: "time", time: "Cuối năm 938" },
    { id: "person", label: "Ngô Quyền", description: "Người chỉ huy quân dân ta", type: "person", people: ["Ngô Quyền"] },
    { id: "event", label: "Bãi cọc ngầm", description: "Nhử quân Nam Hán vào trận địa", type: "event", details: ["Tận dụng thủy triều trên sông Bạch Đằng"] },
    { id: "meaning", label: "Độc lập", description: "Mở ra thời kỳ độc lập lâu dài", type: "meaning" },
    { id: "memory", label: "Mẹo ghi nhớ", description: "938 - Bạch Đằng - Ngô Quyền", type: "memory", memory_points: ["Nhớ bộ ba 938 - Bạch Đằng - Ngô Quyền"] }
  ],
  edges: [
    { source: "root", target: "time" },
    { source: "time", target: "event" },
    { source: "event", target: "meaning" },
    { source: "root", target: "person" },
    { source: "meaning", target: "memory" }
  ]
};

describe("MindMap", () => {
  it("có điều khiển trực quan và dạng danh sách thay thế", async () => {
    const user = userEvent.setup();
    render(<MindMap data={mindmap} />);

    expect(screen.getByRole("heading", { name: "Sơ đồ tư duy" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Phóng to sơ đồ" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Vừa khung" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Đặt lại góc nhìn" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /Sơ đồ tư duy:/ })).toHaveAttribute(
      "aria-keyshortcuts",
      expect.stringContaining("ArrowLeft")
    );
    expect(screen.getByText("10 ý kiến thức · 3 tầng liên kết")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Xem nguyên nhân: Nguyên nhân" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Xem diễn biến: Diễn biến" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Xem nhân vật: Nhân vật" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Xem ý nghĩa: Ý nghĩa" })).toBeInTheDocument();

    const eventBranch = screen.getByRole("button", { name: /Diễn biến 2 ý · đang mở/ });
    expect(eventBranch).toHaveAttribute("aria-expanded", "true");
    await user.click(eventBranch);
    expect(screen.getByRole("button", { name: /Diễn biến 2 ý · đã thu gọn/ })).toHaveAttribute(
      "aria-expanded",
      "false"
    );
    expect(screen.getByText("8/10 ý đang hiển thị · 3 tầng liên kết")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Mở tất cả" }));

    await user.click(screen.getByRole("button", { name: "Phóng to sơ đồ" }));
    expect(screen.getByRole("status", { name: "Mức thu phóng" })).toHaveTextContent("88%");

    await user.click(screen.getByRole("button", { name: "Xem diễn biến: Bãi cọc ngầm" }));
    expect(screen.getByText("Chi tiết cần hiểu")).toBeInTheDocument();
    expect(screen.getByText("Tận dụng thủy triều trên sông Bạch Đằng")).toBeInTheDocument();
    expect(
      within(screen.getByLabelText("Nhóm kiến thức có trong sơ đồ")).getByRole("button", { name: "Diễn biến" })
    ).toHaveAttribute("aria-pressed", "true");

    await user.click(screen.getByText("Xem sơ đồ dạng danh sách"));
    expect(screen.getAllByText("Mở ra thời kỳ độc lập lâu dài").length).toBeGreaterThan(0);
  });
});
