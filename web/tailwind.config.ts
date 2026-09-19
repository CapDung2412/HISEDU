import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#17324D",
        brand: {
          50: "#EEF8FF",
          100: "#D9EEFF",
          200: "#B8DFFF",
          300: "#7FC1F0",
          500: "#1677C8",
          600: "#0C64AE",
          700: "#084F8C",
          800: "#073E70",
          950: "#062642"
        },
        sun: {
          50: "#FFFBEA",
          100: "#FFF4BF",
          400: "#F8C94D"
        }
      },
      boxShadow: {
        card: "0 14px 40px rgba(33, 73, 105, 0.10)"
      },
      borderRadius: {
        "4xl": "2rem"
      },
      animation: {
        "soft-pulse": "soft-pulse 1.8s ease-in-out infinite"
      },
      keyframes: {
        "soft-pulse": {
          "0%, 100%": { opacity: "0.48" },
          "50%": { opacity: "1" }
        }
      }
    }
  },
  plugins: []
};

export default config;
