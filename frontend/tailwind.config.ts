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
        background: '#F3F5FC',
        surface: '#FFFFFF',
        border: '#D8DEEE',
        text: {
          DEFAULT: '#18213B',
          muted: '#626D86',
        },
        primary: {
          DEFAULT: '#4F46E5',
          hover: '#4338CA',
          foreground: '#FFFFFF',
        },
        chart: {
          teal: '#4F46E5',
          rust: '#A84B2F',
          dark: '#312E81',
          light: '#C7D2FE',
          mauve: '#7C3AED',
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
        card: '0 2px 8px rgba(49,46,129,0.04), 0 1px 2px rgba(24,33,59,0.03)',
        'card-hover': '0 10px 24px rgba(79,70,229,0.10), 0 2px 6px rgba(24,33,59,0.04)',
      },
    },
  },
  plugins: [],
}

export default config
