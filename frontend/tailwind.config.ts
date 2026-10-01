import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#F7F6F2',
        surface: '#F9F8F5',
        border: '#D4D1CA',
        text: {
          DEFAULT: '#28251D',
          muted: '#7A7974',
        },
        primary: {
          DEFAULT: '#01696F',
          hover: '#0C4E54',
          foreground: '#FFFFFF',
        },
        chart: {
          teal: '#20808D',
          rust: '#A84B2F',
          dark: '#1B474D',
          light: '#BCE2E7',
          mauve: '#944454',
          yellow: '#FFC553',
        },
        platform: {
          twitter: '#1DA1F2',
          reddit: '#FF4500',
          instagram: '#E1306C',
          tiktok: '#000000',
          youtube: '#FF0000',
          facebook: '#1877F2',
          pinterest: '#E60023',
          linkedin: '#0A66C2',
        },
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
      borderRadius: {
        DEFAULT: '0.5rem',
      },
      boxShadow: {
        card: '0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)',
        'card-hover': '0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04)',
      },
    },
  },
  plugins: [],
}

export default config
