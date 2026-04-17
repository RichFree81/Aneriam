
import { Box, CircularProgress, Typography, Backdrop, useTheme } from '@mui/material';
import { alpha } from '@mui/material/styles';

interface LoadingStateProps {
    variant?: 'fullscreen' | 'section' | 'overlay';
    message?: string;
}

/**
 * Standardized Loading State (Milestone D).
 * 
 * - `fullscreen`: Blocking backdrop with centered spinner.
 * - `section`: Inline centered spinner for content areas or cards.
 * - `overlay`: Non-blocking overlay (e.g. for long lists or transparent blocking).
 */
export default function LoadingState({ variant = 'section', message }: LoadingStateProps) {
    const theme = useTheme();

    if (variant === 'fullscreen') {
        return (
            <Backdrop
                sx={{
                    color: theme.palette.common.white,
                    zIndex: (theme) => theme.zIndex.drawer + 9999, // Super high z-index
                    flexDirection: 'column',
                    gap: 2
                }}
                open={true}
            >
                <CircularProgress color="inherit" />
                {message && <Typography variant="h6">{message}</Typography>}
            </Backdrop>
        );
    }

    if (variant === 'overlay') {
        return (
            <Box sx={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: alpha(theme.palette.background.paper, 0.7),
                zIndex: 1,
                flexDirection: 'column',
                gap: 2
            }}>
                <CircularProgress />
                {message && <Typography variant="body2" color="text.secondary">{message}</Typography>}
            </Box>
        );
    }

    // Default: 'section' (Basic centered block)
    return (
        <Box sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '200px', // Reasonable default minimum
            p: 4,
            gap: 2
        }}>
            <CircularProgress />
            {message && <Typography variant="body2" color="text.secondary">{message}</Typography>}
        </Box>
    );
}
