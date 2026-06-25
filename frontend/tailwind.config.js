export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        ink: '#17202a',
        ocean: '#1b7286',
        coral: '#f26a5b',
        mint: '#4cbf9f',
        amber: '#f1b84b'
      },
      boxShadow: {
        soft: '0 18px 60px rgba(23, 32, 42, 0.12)'
      }
    }
  },
  plugins: []
};
