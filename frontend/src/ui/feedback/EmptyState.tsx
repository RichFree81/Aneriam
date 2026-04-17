
import { Box, Typography, Paper } from '@mui/material';

interface EmptyStateProps {
    title: string;
    message?: string;
    action?: React.ReactNode;
    icon?: React.ReactNode;
}

/**
 * Standardized Empty State (Milestone D).
 * 
 * Consistent placeholder for missing data / empty lists.
 */
export default function EmptyState({ title, message, action, icon }: EmptyStateProps) {
    return (
        <Paper
            sx={{
                p: 6,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                textAlign: 'center',
                maxWidth: 400,
                mx: 'auto',
                gap: 2,
                border: '1px dashed',
                borderColor: 'divider',
                borderRadius: 2, // Matches card radius*2 logic? No, Card is *2, this is internal usually. 
                // Let's adhere to theme radius.
                // Actually if I use `Paper` with `variant="outlined"` and dashed border override...
                background: 'transparent',
                boxShadow: 'none'
            }}
        >
            {icon && (
                <Box sx={{ color: 'text.secondary', fontSize: 48, mb: 1 }}>
                    {icon}
                </Box>
            )}
            <Typography variant="h6" color="text.primary">
                {title}
            </Typography>
            {message && (
                <Typography variant="body2" color="text.secondary">
                    {message}
                </Typography>
            )}
            {action && (
                <Box sx={{ mt: 1 }}>
                    {action}
                </Box>
            )}
        </Paper>
    );
}
