import type { Config } from 'tailwindcss'

// Tokens mirror gov.il's public design system (extracted from
// https://www.gov.il/govilHF/cdn/govil.min.css + header-footer.js).
// Keep this file and services/page_builder/templates/dataset_page.html.j2
// in sync — the wrapper inlines the same config for Tailwind CDN.
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
          DEFAULT: '#0068f5',
          50:  '#f1f7ff',
          100: '#dbe8fb',
          200: '#b7d2f7',
          500: '#0068f5',
          600: '#0053c4',
          700: '#0b3668',
          800: '#0c3058',
        },
        ink:          '#0c3058',
        'ink-deep':   '#0b3668',
        surface:      '#f1f7ff',
        'surface-alt':'#f0f4fa',
        rule:         '#c3cfe7',
        subtle:       '#6c757d',
        ok:           '#198754',
        warn:         '#ffc107',
        danger:       '#dc3545',
        info:         '#0dcaf0',
      },
      fontFamily: {
        sans:    ['Rubik', 'system-ui', 'Arial', 'sans-serif'],
        display: ['Rubik', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        'gov-sm':   '0.2rem',
        'gov-md':   '0.3rem',
        gov:        '0.5rem',
        'gov-pill': '50rem',
      },
      maxWidth: {
        gov: '1400px',
      },
      backgroundImage: {
        'gov-header': 'linear-gradient(90deg, #025fdb 0%, #0b3668 100%)',
      },
      boxShadow: {
        card:         '0 1px 2px rgba(12, 48, 88, 0.06)',
        'card-hover': '0 6px 24px -8px rgba(0, 104, 245, 0.18)',
      },
      spacing: {
        'header': '64px',
      },
    },
  },
  plugins: [],
}
