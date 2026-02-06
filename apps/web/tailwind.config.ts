import type { Config } from "tailwindcss"

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // 主色调 - 绿色暗黑主题 (Green-Tinted Dark)
        canvas: {
          DEFAULT: "#020402", // Deep Forest Black - 纯黑带极微绿，替代之前的 Zinc/Slate
          light: "#0a0f0c",   // Dark Jungle - 替代 Zinc 900
          dark: "#010301",    // Void Green - 替代 Slate 950
        },
        ink: {
          DEFAULT: "#ecfdf5", // Emerald 50 - 替代 Zinc 100
          muted: "#6ee7b7",   // Emerald 300 - 替代 Zinc 400
          dim: "#34d399",     // Emerald 400 - 替代 Zinc 500
        },
        accent: {
          DEFAULT: "#10b981", // Emerald 500
          hover: "#059669",   // Emerald 600
          soft: "#10b98120",
        },
        panel: {
          DEFAULT: "#0c120f", // Dark Jungle - 替代 Zinc 900
          hover: "#151f1a",   // Deep Green Gray - 替代 Zinc 800
          border: "#1d2e25",  // Greenish Charcoal - 替代 Zinc 800
        },
        success: "#10b981",
        warning: "#f59e0b",
        error: "#ef4444",
      },
      fontFamily: {
        display: ["Outfit", "system-ui", "sans-serif"],
        body: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      animation: {
        "fade-in": "fadeIn 0.3s ease-out",
        "slide-up": "slideUp 0.4s ease-out",
        "scale-in": "scaleIn 0.2s ease-out",
        "pulse-soft": "pulseSoft 2s ease-in-out infinite",
        "shimmer": "shimmer 2s linear infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(20px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        scaleIn: {
          "0%": { opacity: "0", transform: "scale(0.95)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        pulseSoft: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.7" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "grid-pattern": "linear-gradient(to right, #1e3a3a 1px, transparent 1px), linear-gradient(to bottom, #1e3a3a 1px, transparent 1px)",
      },
    },
  },
  plugins: [],
}

export default config
