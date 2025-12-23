/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "primary": "#135bec",
        "background-light": "#f6f6f8",
        "background-dark": "#101622",
        "dark": {
          "bg": "#111318",
          "card": "#1c1f27",
          "border": "#282e39",
          "border-light": "#3b4354",
          "text": "#c4c9d4",
          "text-muted": "#9da6b9",
        }
      },
      fontFamily: {
        "display": ["Inter", "sans-serif"]
      },
      borderRadius: {
        "DEFAULT": "0.25rem",
        "lg": "0.5rem",
        "xl": "0.75rem",
        "full": "9999px"
      },
      minWidth: {
        "btn": "84px",
      },
      maxWidth: {
        "input": "480px",
        "content": "960px",
      },
      minHeight: {
        "hero": "400px",
      },
      spacing: {
        "3.25": "13px",
        "3.75": "15px",
      },
      borderWidth: {
        "3": "3px",
      },
      letterSpacing: {
        "tight-sm": "-0.015em",
        "tight-lg": "-0.033em",
        "wide-sm": "0.015em",
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
}
