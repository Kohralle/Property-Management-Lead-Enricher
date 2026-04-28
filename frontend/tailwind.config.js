/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Avenir Next"', '"Helvetica Neue"', 'Arial', 'sans-serif'],
        display: ['"Iowan Old Style"', '"Baskerville"', '"Times New Roman"', 'serif'],
      },
      colors: {
        luxe: {
          shell: '#f6efe2',
          panel: '#fff9f0',
          soft: '#efe4d2',
          line: '#d9c5a7',
          accent: '#8e6839',
          accentSoft: '#ead8bb',
          ink: '#332417',
          muted: '#8c7659',
          shadow: '#a99070',
        },
        apple: {
          blue: '#8e6839',
          gray: '#8c7659',
          lightgray: '#efe4d2',
          separator: '#d9c5a7',
        },
      },
    },
  },
  plugins: [],
}
