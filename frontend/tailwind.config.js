/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        display: ['Outfit', 'sans-serif'],
      },
      colors: {
        border: "hsl(214,32%,91%)",
        background: "hsl(0,0%,100%)",
        foreground: "hsl(222,84%,5%)",
        muted: { DEFAULT: "hsl(210,40%,96%)", foreground: "hsl(215,16%,47%)" },
        card: { DEFAULT: "hsl(0,0%,100%)", foreground: "hsl(222,84%,5%)" },
        primary: { DEFAULT: "hsl(221,83%,53%)", foreground: "hsl(0,0%,100%)" },
        destructive: { DEFAULT: "hsl(0,84%,60%)", foreground: "hsl(0,0%,100%)" },
      },
      borderRadius: { lg: "0.5rem", md: "0.375rem", sm: "0.25rem" },
    },
  },
  plugins: [],
}