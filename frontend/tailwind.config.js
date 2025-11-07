/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        'bg-primary': '#0A0C16',
        'panel-secondary': '#1A1D2E',
        'accent-gold': '#E8C370',
        'success-green': '#4BE37D',
        'error-red': '#FF5E5E',
        'text-primary': '#F5F6F9',
        'text-secondary': '#A5A8B3',
      },
      backgroundImage: {
        'highlight-gradient': 'linear-gradient(90deg, #7B3FE4, #C26DFD)',
        'gold-gradient': 'linear-gradient(90deg, #CBA45E, #F7E9A3)',
      },
      keyframes: {
        'rr-spin': {
          to: { transform: 'rotate(360deg)' }
        },
        'rr-pulse': {
          '0%': { boxShadow: '0 0 0 0 rgba(232,195,112,0.14)' },
          '70%': { boxShadow: '0 0 0 10px rgba(232,195,112,0)' },
          '100%': { boxShadow: '0 0 0 0 rgba(232,195,112,0)' }
        },
        'rr-float': {
          '0%': { transform: 'translateY(0) scale(0.98)', opacity: '0.02' },
          '25%': { transform: 'translateY(-10px) scale(1)', opacity: '0.08' },
          '50%': { transform: 'translateY(6px) scale(1.02)', opacity: '0.06' },
          '75%': { transform: 'translateY(-6px) scale(1)', opacity: '0.09' },
          '100%': { transform: 'translateY(0) scale(0.98)', opacity: '0.02' }
        }
      },
      animation: {
        'rr-spin': 'rr-spin 1s linear infinite',
        'rr-pulse': 'rr-pulse 2s infinite',
        'rr-float': 'rr-float 10s ease-in-out infinite'
      }
    },
  },
  plugins: [],
}
