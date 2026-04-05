/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx}',
    './pages/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        'cr14-dark-blue': '#142667 !important',
        'cr14-light-blue': '#0082be',
        'cr14-gray': '#f5f6f7',
      }
    },
  },
  plugins: [],
};
