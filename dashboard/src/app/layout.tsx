import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { Nav } from "@/components/nav";

export const metadata: Metadata = {
  title: "Sentinel",
  description: "AI-Powered Code Review with Reproducible Evaluation",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full">
        <Providers>
          <a
            href="#main-content"
            className="absolute left-[-10000px] top-auto z-[100] block h-px w-px overflow-hidden whitespace-nowrap focus:absolute focus:left-4 focus:top-4 focus:h-auto focus:w-auto focus:overflow-visible focus:whitespace-normal focus:rounded-md focus:bg-accent focus:px-4 focus:py-2 focus:text-[#0b0d10] focus:shadow-lg focus:outline-none focus:ring-2 focus:ring-accent/60"
          >
            Skip to content
          </a>
          <Nav />
          <main
            id="main-content"
            tabIndex={-1}
            className="mx-auto max-w-6xl px-4 py-8 outline-none focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
          >
            {children}
          </main>
        </Providers>
      </body>
    </html>
  );
}
