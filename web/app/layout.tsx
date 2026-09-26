import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DelayCast",
  description: "A compact National Rail delay-risk portfolio project",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
