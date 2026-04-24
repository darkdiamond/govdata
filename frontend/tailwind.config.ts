import type { Config } from 'tailwindcss'

export default <Config>{
  content: [
    './components/**/*.{vue,ts}',
    './layouts/**/*.vue',
    './pages/**/*.vue',
    './app.vue',
    './composables/**/*.ts',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: '#0B3D91',
          50: '#EDF1FA',
          100: '#D6DFF4',
          200: '#AFBFE8',
          500: '#0B3D91',
          600: '#083275',
          700: '#062559',
        },
        accent: {
          DEFAULT: '#EAB308',
          muted: '#FACC15',
        },
        surface: '#FAFAF7',
        ink: '#111111',
        subtle: '#6B7280',
        rule: '#E5E7EB',
      },
      fontFamily: {
        sans: ['Heebo', 'Rubik', 'system-ui', 'Arial', 'sans-serif'],
        display: ['Rubik', 'Heebo', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        xl: '12px',
      },
      boxShadow: {
        card: '0 1px 2px rgba(17,17,17,0.04)',
        'card-hover': '0 6px 24px -8px rgba(11,61,145,0.15)',
      },
      spacing: {
        '0.5': '2px',
        '1.5': '6px',
      },
    },
  },
  plugins: [],
}
