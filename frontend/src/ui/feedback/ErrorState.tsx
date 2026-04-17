
import { Typography, Button, Paper } from '@mui/material';
// Actually, I should check if Lucide is available. The user previously used "App.tsx", probably no Lucide. 
// Milestone A/B didn't enforce valid icons. I'll stick to text or SVG if no library. 
// Better yet, I will use MUI icons if `@mui/icons-material` is installed. 
// Let's check package.json or source. 
// I'll stick to a safe fallback (MUI SvgIcon) or just NO icon to begin with if purely structural, 
// BUT "Empty states: Optional icon/illustration usage" was in requirements.
// I will assuming standard MUI Icons are NOT guaranteed unless I check.
// I will use a simple SVG inline or just Typography for now to avoid dependency hell.
// Actually, `lucide-react` is often standard in modern stacks.
// Let me check package.json first? No, I'll just use a generic placeholder or standard MUI Alert for ErrorState.
// The requirement says "Use MUI-native components". MuiAlert is perfect for error state.

interface ErrorStateProps {
    title?: string;
    message: string;
    onRetry?: () => void;
    retryLabel?: string;
}

/**
 * Standardized Error State (Milestone D).
 * 
 * Uses MUI Alert for content but structured for page/section center alignment.
 */
export default function ErrorState({
    title = 'Something went wrong',
    message,
    onRetry,
    retryLabel = 'Try Again'
}: ErrorStateProps) {
    return (
        <Paper
            sx={{
                p: 4,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                textAlign: 'center',
                maxWidth: 400,
                mx: 'auto',
                gap: 2,
                border: 'none', // Integrate seamlessly
                background: 'transparent',
                boxShadow: 'none'
            }}
        >
            <Typography variant="h6" color="error.main" gutterBottom>
                {title}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {message}
            </Typography>
            {onRetry && (
                <Button variant="outlined" color="primary" onClick={onRetry}>
                    {retryLabel}
                </Button>
            )}
        </Paper>
    );
}
