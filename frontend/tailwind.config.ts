import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        brand: {
          vermillion: "#c41e3a",
          "vermillion-bg": "rgba(196,30,58,0.08)",
          gold: "#c9a96e",
          "gold-bg": "rgba(201,169,110,0.08)",
          jade: "#2d5a4a",
          "jade-bg": "rgba(45,90,74,0.10)",
        },
        surface: {
          DEFAULT: "#080808",
          alt: "#0e0c0a",
          card: "#161412",
          "card-hover": "#1e1b17",
          border: "#2a2520",
          "border-faint": "#1c1814",
        },
        ink: {
          DEFAULT: "#e8e4db",
          secondary: "#8c867c",
          muted: "#5c5650",
        },
        light: {
          bg: "#f8f6f2",
          "bg-alt": "#f2f0ea",
          card: "#ffffff",
          "card-hover": "#faf9f5",
          border: "#e0dbd0",
          "border-faint": "#eee9e0",
          ink: "#2a2520",
          "ink-secondary": "#6b6560",
          "ink-muted": "#a09890",
        },
      },
      fontFamily: {
        serif: ['Georgia', '"Noto Serif SC"', 'serif'],
        mono: ['"JetBrains Mono"', 'Consolas', 'monospace'],
      },
      maxWidth: {
        chat: "720px",
      },
      animation: {
        "fade-up": "fadeUp 0.4s cubic-bezier(0.16, 1, 0.3, 1)",
        "fade-in": "fadeIn 0.3s ease-out",
        "slide-in": "slideIn 0.3s ease-out",
        pulse: "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
      keyframes: {
        fadeUp: {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        fadeIn: {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        slideIn: {
          from: { opacity: "0", transform: "translateX(-10px)" },
          to: { opacity: "1", transform: "translateX(0)" },
        },
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};

export default config;
