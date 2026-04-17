import type { Components, Theme } from '@mui/material';

// Tab font size reduced 20% from MUI default (0.875rem → 0.7rem)
const components: Components<Theme> = {
    MuiTab: {
        styleOverrides: {
            root: {
                textTransform: 'none' as const,
                // fontSize removed to align with standard MUI default (0.875rem)
                // fontSize removed to align with standard MUI default (0.875rem)
                // fontWeight: 600 removed to unbold tabs
            },
        },
    },
};

export default components;
