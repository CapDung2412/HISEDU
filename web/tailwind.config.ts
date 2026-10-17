import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#251B19",
        brand: {
          50: "#FFF7F2",
          100: "#F9E5DA",
          200: "#EDC7B4",
          300: "#D99C7D",
          500: "#A83D32",
          600: "#8F2E29",
          700: "#74231F",
          800: "#5B211E",
          950: "#351311"
        },
        sun: {
          50: "#FFFAED",
          100: "#F8ECC8",
          400: "#C99535"
        },
        heritage: {
          50: "#F1F6F8",
          100: "#DDE8ED",
          600: "#294C60",
          700: "#1E3A4A",
          900: "#142936"
        }
      },
      boxShadow: {
        card: "0 18px 48px rgba(61, 38, 29, 0.12)"
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
