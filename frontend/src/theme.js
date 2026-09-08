import { createTheme } from '@mui/material/styles'

// Dark theme built from the UI prototype's palette tokens
// (prototype `:root` variables in frontend/prototype/), so the
// screens match the design reference: near-black background, deep
// panel surfaces, blue accent, teal secondary.
export const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: '#6c8cff' },
    secondary: { main: '#5ee6c8' },
    background: {
      default: '#0f1117',
      paper: '#161a23',
    },
    text: {
      primary: '#e6e9f0',
      secondary: '#8b93a7',
    },
    error: { main: '#ff6b6b' },
    warning: { main: '#ffb454' },
    success: { main: '#59d47c' },
    divider: '#2a3142',
  },
  shape: { borderRadius: 12 },
  components: {
    // The prototype's panels are flat; drop MUI's dark-mode
    // elevation overlay so Paper keeps the flat look.
    MuiPaper: {
      styleOverrides: {
        root: { backgroundImage: 'none' },
      },
    },
    // Primary contained actions carry the brand gradient and a soft
    // neon lift so the CTA buttons read as colorful, glowing actions.
    MuiButton: {
      variants: [
        {
          props: { variant: 'contained', color: 'primary' },
          style: {
            backgroundImage:
              'linear-gradient(135deg, #6c8cff 0%, #8b7cff 100%)',
            boxShadow: '0 10px 22px -12px rgba(108, 140, 255, 0.8)',
            transition:
              'box-shadow 180ms ease, transform 180ms ease, background-image 180ms ease',
            '&:hover': {
              backgroundImage:
                'linear-gradient(135deg, #7d99ff 0%, #9b8cff 100%)',
              boxShadow: '0 12px 26px -10px rgba(108, 140, 255, 0.9)',
              transform: 'translateY(-1px)',
            },
          },
        },
      ],
    },
  },
})

// Ambient glow painted behind the app shell and the landing page:
// two soft radial tints (brand blue top-right, teal bottom-left) over
// the flat background, giving every screen a little color depth
// without touching the solid panels themselves.
export const pageBackgroundImage =
  'radial-gradient(900px 520px at 88% -10%, rgba(108, 140, 255, 0.14), transparent 62%), radial-gradient(820px 500px at -8% 110%, rgba(94, 230, 200, 0.1), transparent 60%)'
