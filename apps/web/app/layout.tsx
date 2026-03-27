import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "sunrise-hes-platform",
  description: "Sunrise HES platform scaffold",
};

type RootLayoutProps = {
  children: ReactNode;
};

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
