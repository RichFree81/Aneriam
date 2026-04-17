import { useEffect } from 'react';
import { Box, Card, Typography, Button, CircularProgress, Alert, Avatar } from '@mui/material';
import { usePortfolio } from '../context/PortfolioContext';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import PublicLayout from '../layouts/PublicLayout';
import type { Portfolio } from '../types/portfolio';

export default function SelectPortfolio() {
    const { portfolios, refreshPortfolios, setActivePortfolio, isLoading, error } = usePortfolio();
    const { isAuthenticated, logout } = useAuth();
    const navigate = useNavigate();

    useEffect(() => {
        if (!isAuthenticated) {
            navigate('/login');
            return;
        }
        refreshPortfolios();
    }, [isAuthenticated, navigate, refreshPortfolios]);

    const handleSelect = (portfolio: Portfolio) => {
        setActivePortfolio(portfolio);
        navigate('/');
    };

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    return (
        <PublicLayout>
            <Card sx={{ p: 4, width: '100%', maxWidth: 800 }}>
                <Typography variant="h5" component="h1" align="center" gutterBottom sx={{ fontWeight: 600 }}>
                    Select Portfolio
                </Typography>
                <Typography variant="body1" color="text.secondary" align="center" paragraph>
                    Choose a portfolio to continue.
                </Typography>

                {error && (
                    <Alert severity="error" sx={{ mb: 3 }}>
                        {error}
                    </Alert>
                )}

                {isLoading ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
                        <CircularProgress />
                    </Box>
                ) : (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 2, mt: 1 }}>
                        {portfolios.length === 0 && !error ? (
                            <Box sx={{ width: '100%', textAlign: 'center', py: 4 }}>
                                <Typography color="text.secondary">
                                    No portfolios found. Please contact support.
                                </Typography>
                            </Box>
                        ) : (
                            portfolios.map((portfolio) => (
                                <Box key={portfolio.id} sx={{ width: { xs: '100%', sm: 'calc(50% - 8px)', md: 'calc(33.33% - 11px)' } }}>
                                    <Button
                                        variant="outlined"
                                        fullWidth
                                        sx={{
                                            p: 3,
                                            display: 'flex',
                                            flexDirection: 'column',
                                            alignItems: 'center',
                                            textAlign: 'center',
                                            height: '100%',
                                            gap: 2
                                        }}
                                        onClick={() => handleSelect(portfolio)}
                                    >
                                        <Avatar
                                            src={portfolio.logo}
                                            alt={portfolio.name}
                                            sx={{ width: 56, height: 56, bgcolor: 'primary.main', fontSize: '1.25rem' }}
                                        >
                                            {portfolio.name.substring(0, 3).toUpperCase()}
                                        </Avatar>
                                        <Box>
                                            <Typography variant="subtitle1" component="div" sx={{ fontWeight: 600 }}>
                                                {portfolio.name}
                                            </Typography>
                                            {portfolio.description && (
                                                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                                                    {portfolio.description}
                                                </Typography>
                                            )}
                                        </Box>
                                    </Button>
                                </Box>
                            ))
                        )}
                    </Box>
                )}

                <Box sx={{ mt: 4, textAlign: 'center' }}>
                    <Button color="inherit" onClick={handleLogout}>
                        Log Out
                    </Button>
                </Box>
            </Card>
        </PublicLayout>
    );
}
