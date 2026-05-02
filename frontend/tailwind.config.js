/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#17202A",
        panel: "#F7F8FA",
        line: "#D9DEE7",
        signal: "#0F766E",
        danger: "#B42318",
        amber: "#B54708"
      }
    },
  },
  plugins: [],
};
