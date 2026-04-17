/**
 * NotFound Page (404)
 *
 * Displays when a route is not found.
 *
 * Rules (per FRONTEND-MODULE-READINESS.md):
 * - R-08: 404 (Not Found) MUST display a branded page with navigation home
 * - R-10: Error pages MUST use locked ErrorState component (Milestone D)
 */

import { Box, Button, Typography } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import HomeOutlinedIcon from '@mui/icons-material/HomeOutlined';
import { ROUTES } from '../config/routes.config';

export default function NotFound() {
    const navigate = useNavigate();

    const handleGoHome = () => {
        navigate(ROUTES.HOME);
    };

    return (
        <Box
            sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: '100vh',
                textAlign: 'center',
                px: 3,
            }}
        >
            <Typography
                variant="h1"
                sx={{
                    fontSize: { xs: '4rem', sm: '6rem' },
                    fontWeight: 700,
                    color: 'primary.main',
                    mb: 2,
                }}
            >
                404
            </Typography>

            <Typography variant="h5" color="text.primary" gutterBottom>
                Page Not Found
            </Typography>

            <Typography
                variant="body1"
                color="text.secondary"
                sx={{ mb: 4, maxWidth: 400 }}
            >
                The page you're looking for doesn't exist or has been moved.
            </Typography>

            <Button
                variant="contained"
                size="large"
                startIcon={<HomeOutlinedIcon />}
                onClick={handleGoHome}
            >
                Go to Home
            </Button>
        </Box>
    );
}
