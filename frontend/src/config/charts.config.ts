import { useTheme } from '@mui/material/styles';

/**
 * Standard Chart Colors
 * Derived from the application theme.
 */
export const useChartColors = () => {
    const theme = useTheme();

    return {
        // Primary series colors
        primary: [
            theme.palette.primary.main,
            theme.palette.secondary.main,
            theme.palette.info.main,
            theme.palette.success.main,
            theme.palette.warning.main,
            theme.palette.error.main,
        ],
        // Semantic colors
        semantic: {
            success: theme.palette.success.main,
            warning: theme.palette.warning.main,
            error: theme.palette.error.main,
            neutral: theme.palette.grey[400],
        },
        // Grid/Axis colors
        grid: {
            stroke: theme.palette.divider,
            strokeDasharray: '3 3',
        },
        tooltip: {
            background: theme.palette.background.paper,
            color: theme.palette.text.primary,
        }
    };
};
