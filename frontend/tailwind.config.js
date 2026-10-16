/** @type {import('tailwindcss').Config} */
export default { content: ["./index.html", "./src/**/*.{ts,tsx}"], theme: { extend: { colors: { navy: { 950: "#050b1a", 900: "#081432", 800: "#0c1d4a", 700: "#12296b" }, brand: { blue: "#2563EB", cyan: "#22D3EE" } }, boxShadow: { glow: "0 0 40px rgba(34,211,238,0.15)" } } }, plugins: [] };
