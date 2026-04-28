/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"SF Pro Display"', '"SF Pro Text"', '"Helvetica Neue"', 'Arial', 'sans-serif'],
      },
      colors: {
        apple: {
          blue: '#007AFF',
          gray: '#8E8E93',
          lightgray: '#F2F2F7',
          separator: '#C6C6C8',
        },
      },
    },
  },
  plugins: [],
}
