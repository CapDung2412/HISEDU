import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "HISEDU — Học lịch sử thật dễ hiểu",
  description:
    "Bản thử nghiệm trợ lý học tập Lịch sử lớp 8: giải đáp có nguồn, ảnh tư liệu, sơ đồ tư duy, video và quiz ôn tập.",
  robots: { index: false, follow: false }
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#74231F"
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="vi">
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
