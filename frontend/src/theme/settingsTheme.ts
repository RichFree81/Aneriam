import { createTheme } from '@mui/material/styles';
import palette from './palette';
import typography from './typography';
import components from './components';

// Create a distinct palette for Settings
// Only overriding primary to a neutral/slate color to distinguish context
const settingsPalette = {
    ...palette,
    primary: {
        main: '#475569', // Slate 600
        light: '#64748b', // Slate 500 
        dark: '#334155', // Slate 700
        contrastText: '#ffffff',
    },
    background: {
        default: '#ffffff',
        paper: '#ffffff',
    },
};

const settingsTheme = createTheme({
    palette: settingsPalette,
    typography,
    components,
    shape: {
        borderRadius: 4,
    },
});

export default settingsTheme;
