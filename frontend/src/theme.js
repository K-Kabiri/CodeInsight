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
  },
})
