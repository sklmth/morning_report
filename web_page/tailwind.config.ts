import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#080b12',
        travel: '#75c8e8',
        music: '#ff4fa3',
        game: '#e7bc58',
        teal: '#64d9c2',
      },
      fontFamily: {
        display: ['Arial Narrow', 'Helvetica Neue', 'sans-serif'],
        sans: ['Inter', 'Arial', 'sans-serif'],
      },
      borderRadius: { frame: '8px' },
      transitionTimingFunction: { cinematic: 'cubic-bezier(0.22, 1, 0.36, 1)' },
    },
  },
  plugins: [],
} satisfies Config;
