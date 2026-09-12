/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          darkNavy: "#0F1D3A",
          deepNavy: "#091426",
          teal: "#0D9488",
          brightTeal: "#14B8A6",
          coral: "#F06445",
          warmBg: "#FCFAF7",
          softMint: "#F0FAF7",
        },
        ngo: {
          sidebar: "#10243E",
          deepNavy: "#0C1D34",
          primary: "#2F73D9",
          brightBlue: "#3B82F6",
          critical: "#EF4444",
          urgent: "#F59E0B",
          treatment: "#8B5CF6",
          recovery: "#22A65A",
          bg: "#F5F8FC",
          card: "#FFFFFF",
          border: "#E4EAF2",
          text: "#12213A",
          muted: "#65748B",
        }
      },
      fontFamily: {
        sans: ['Plus Jakarta Sans', 'Inter', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
