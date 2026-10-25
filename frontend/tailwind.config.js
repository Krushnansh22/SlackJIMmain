/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        wmd: {
          bg: "#0b0b12",
          card: "#15151f",
          line: "#262636",
          orange: "#ff6a1a",
          purple: "#8b5cf6",
          green: "#22c55e",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      keyframes: {
        pop: {
          "0%": { transform: "scale(.96)", opacity: 0 },
          "100%": { transform: "scale(1)", opacity: 1 },
        },
        pulseRing: {
          "0%": { boxShadow: "0 0 0 0 rgba(255,106,26,.6)" },
          "100%": { boxShadow: "0 0 0 18px rgba(255,106,26,0)" },
        },
      },
      animation: {
        pop: "pop .25s ease-out",
        ring: "pulseRing 1.2s infinite",
      },
    },
  },
  plugins: [],
};
