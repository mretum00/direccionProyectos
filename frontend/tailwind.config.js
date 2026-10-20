/** @type {import('tailwindcss').Config} */

// Los colores reales están en src/index.css (:root). Aquí solo se registran
// para poder usarlos como clases: bg-fondo, text-texto-400, border-contraste/10...
const color = (variable) => `rgb(var(${variable}) / <alpha-value>)`;

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        fondo: color('--color-fondo'),
        panel: color('--color-panel'),
        tarjeta: color('--color-tarjeta'),
        elevado: color('--color-elevado'),
        contraste: color('--color-contraste'),
        texto: {
          DEFAULT: color('--color-texto'),
          100: color('--color-texto-100'),
          200: color('--color-texto-200'),
          300: color('--color-texto-300'),
          400: color('--color-texto-400'),
          500: color('--color-texto-500'),
          600: color('--color-texto-600'),
          700: color('--color-texto-700'),
        },
      },
    },
  },
  plugins: [],
};
