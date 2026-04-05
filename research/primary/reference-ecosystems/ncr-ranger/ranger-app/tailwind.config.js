/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './index.html',
    './src/**/*.{js,ts,tsx}',
  ],
  theme: {
    extend: {
      backgroundImage: theme => ({
        'home-background': "url('/src/assets/cr14_taust.jpg')",
      }),
      boxShadow: {
        'inner': 'inset 0 0 0 1px rgba(17, 20, 24, 0.2),  inset 0 1px 1px rgba(17, 20, 24, 0.5)'
      }
    },
  },
  plugins: [],
};
