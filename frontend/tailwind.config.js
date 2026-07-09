/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#E9EBE3",
        paper2: "#DFE2D8",
        ink: "#1F232B",
        inkSoft: "#565C55",
        navy: "#263A5C",
        navy2: "#324B73",
        clay: "#A8432E",
        moss: "#3F6B4A",
        ochre: "#B98429",
        line: "#C6CABA",
        card: "#F4F4EE",
      },
      fontFamily: {
        serif: ["Fraunces", "serif"],
        sans: ["Inter", "sans-serif"],
        mono: ["IBM Plex Mono", "monospace"],
      },
      borderRadius: {
        DEFAULT: "3px",
        lg: "4px",
        xl: "6px",
      },
      boxShadow: {
        sm: "0 1px 2px rgba(31,35,43,0.06)",
        md: "0 8px 24px rgba(31,35,43,0.12)",
      },
    },
  },
  plugins: [],
};
