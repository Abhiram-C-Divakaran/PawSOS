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
        }
      },
      fontFamily: {
        sans: ['Plus Jakarta Sans', 'Inter', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
