import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0b0d10",
        panel: "#12151a",
        panel2: "#171b22",
        border: "#242a33",
        muted: "#8891a0",
        fg: "#e6e9ef",
        accent: "#6aa7ff",
        /** Semantic UI: success */
        ok: "#4ade80",
        /** Warnings — light amber/yellow tuned for dark surfaces */
        warn: "#fde047",
        /** Errors */
        bad: "#fb7185",
        crit: "#f87171",
        /** Informational / security tips (sky) */
        info: "#38bdf8",
      },
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
      fontSize: {
        xxs: "0.6875rem",
      },
    },
  },
  plugins: [],
};

export default config;
