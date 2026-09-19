import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { MindMap } from "@/components/MindMap";
import type { MindMapData } from "@/lib/types";

const mindmap: MindMapData = {
  title: "Chiến thắng Bạch Đằng",
  nodes: [
    { id: "root", label: "Bạch Đằng 938", description: "Chiến thắng lịch sử", type: "root" },
    { id: "meaning", label: "Độc lập", description: "Mở ra thời kỳ độc lập lâu dài", type: "meaning" }
  ],
  edges: [{ source: "root", target: "meaning" }]
};

describe("MindMap", () => {
  it("có điều khiển trực quan và dạng danh sách thay thế", async () => {
    const user = userEvent.setup();
    render(<MindMap data={mindmap} />);

    expect(screen.getByRole("heading", { name: "Sơ đồ tư duy" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Phóng to sơ đồ" })).toBeInTheDocument();

    await user.click(screen.getByText("Xem sơ đồ dạng danh sách"));
    expect(screen.getAllByText("Mở ra thời kỳ độc lập lâu dài").length).toBeGreaterThan(0);
  });
});

