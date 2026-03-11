import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Assistant Console",
  description: "Workspace-first dashboard for follow-through across work and Camp Downer.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
