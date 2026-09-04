/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        command: {
          bg: '#0a0e1a',
          surface: '#111827',
          card: '#131b2e',
          cardBorder: '#1e293b',
          sidebar: '#0d1322',
          activeBlue: '#2563eb',
          activeHighlight: '#1d4ed8',
          accentCyan: '#06b6d4',
          emeraldOnline: '#10b981',
          hazardRed: '#ef4444',
          hazardAmber: '#f59e0b',
          hazardBlue: '#38bdf8',
          textMain: '#f8fafc',
          textMuted: '#94a3b8',
          textDim: '#64748b'
        }
      },
      fontFamily: {
        sans: ['Inter', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace']
      },
      boxShadow: {
        'tactical': '0 4px 20px -2px rgba(0, 0, 0, 0.5), 0 0 1px 1px rgba(255, 255, 255, 0.05)',
        'glow-blue': '0 0 15px rgba(37, 99, 235, 0.35)',
        'glow-red': '0 0 15px rgba(239, 68, 68, 0.35)',
        'glow-amber': '0 0 15px rgba(245, 158, 11, 0.35)',
        'glow-green': '0 0 15px rgba(16, 185, 129, 0.35)'
      }
    },
  },
  plugins: [],
}
