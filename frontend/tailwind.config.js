/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Page surfaces, dark to lighter
        bg: '#000000',
        surface: '#0E0E0E',
        surface2: '#161616',
        surface3: '#1F1F1F',

        // Borders
        border: '#222222',
        border2: '#2E2E2E',

        // Text
        ink: '#FFFFFF',
        muted: '#8A8A8A',
        muted2: '#5A5A5A',

        // Brand: ER ATC-app yellow. Used for primary CTAs and the brand mark.
        accent: '#FFCD00',
        'accent-hover': '#FFDA33',
        'accent-ink': '#0A0A0A', // text color when sitting on yellow

        // Urgent/red callout, matches the red card on the ATC app
        alert: '#FF2030',
        'alert-bg': '#2A0A0E',

        // Status palette (brighter for dark-mode contrast)
        good: '#4ADE80',
        'good-bg': '#0F2A1A',
        warn: '#FB923C',
        'warn-bg': '#2A1908',
        bad: '#F87171',
        'bad-bg': '#2A0F0F',

        // Status pill backgrounds for outreach tracking
        status: {
          untouched: '#2A2A2A',
          contacted: '#1E3A8A',
          followup: '#7C2D12',
          interested: '#14532D',
          declined: '#7F1D1D',
          won: '#854D0E',
          lost: '#262626'
        }
      },
      fontFamily: {
        sans: [
          'Inter',
          'system-ui',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'sans-serif'
        ],
        display: [
          'Inter',
          'system-ui',
          'sans-serif'
        ]
      },
      fontSize: {
        // Editorial-scale headlines to match the ATC app's big bold airport codes
        'display-xl': ['4.5rem', { lineHeight: '0.95', letterSpacing: '-0.04em', fontWeight: '900' }],
        'display-lg': ['3rem', { lineHeight: '1', letterSpacing: '-0.03em', fontWeight: '900' }],
        'display-md': ['2rem', { lineHeight: '1.05', letterSpacing: '-0.02em', fontWeight: '800' }]
      },
      borderRadius: {
        DEFAULT: '10px',
        pill: '999px'
      }
    }
  },
  plugins: []
}
