import { AppProvider } from '@toolpad/core/AppProvider';
import { Box, Typography } from '@mui/material';
import { DashboardLayout } from '@toolpad/core/DashboardLayout';
import { Account } from '@toolpad/core/Account';
import logoImg from '../assets/logo.png';
import { useAuth } from '../context/AuthContext';
import { usePortfolio } from '../context/PortfolioContext';
import GlobalAddMenu from '../components/common/GlobalAddMenu';
import type { ReactNode } from 'react';
import type { Router } from '@toolpad/core/AppProvider';
import { useNavigate, useLocation } from 'react-router-dom';
import { SETTINGS_NAVIGATION } from '../config/navigation.config';
import settingsTheme from '../theme/settingsTheme';

interface SettingsShellProps {
    children: ReactNode;
}

export default function SettingsShell({ children }: SettingsShellProps) {
    const { user, logout } = useAuth();
    const { clearActivePortfolio } = usePortfolio();

    const companyName = user?.company_name ?? 'Company';

    const navigate = useNavigate();
    const location = useLocation();

    // Toolpad router integration with React Router
    const router: Router = {
        pathname: location.pathname,
        searchParams: new URLSearchParams(location.search),
        navigate: (path) => navigate(String(path)),
    };

    const handleSignOut = () => {
        void logout().finally(() => {
            clearActivePortfolio();
            navigate('/login');
        });
    };

    return (
        <AppProvider
            theme={settingsTheme}
            navigation={SETTINGS_NAVIGATION}
            router={router}
            branding={{
                logo: (
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        {/* Custom Breadcrumb - Settings Context */}
                        <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 500 }}>
                            {companyName} / Settings
                        </Typography>

                        {/* App Logo - Fixed Center - SAME AS APPLICATION SHELL */}
                        <Box sx={{
                            position: 'fixed',
                            top: 12,
                            left: '50%',
                            transform: 'translateX(-50%)',
                            display: { xs: 'none', md: 'flex' },
                            alignItems: 'center',
                            zIndex: 1200,
                            pointerEvents: 'none'
                        }}>
                            <img src={logoImg} alt="Aneriam" height={40} />
                        </Box>
                    </Box>
                ),
                title: '',
            }}
            session={{
                user: {
                    name: user?.full_name || user?.email || 'User',
                    email: user?.email || '',
                    image: '',
                },
            }}
            authentication={{
                signIn: () => navigate('/login'),
                signOut: handleSignOut,
            }}
        >
            <DashboardLayout
                defaultSidebarCollapsed
                slots={{
                    toolbarAccount: Account,
                    toolbarActions: () => (
                        <Box sx={{ mr: 1, display: 'flex', gap: 1 }}>
                            {/* Keep Global Add Menu */}
                            <GlobalAddMenu />
                            {/* Removed ProjectFilter and SettingsIcon as requested */}
                        </Box>
                    )
                }}
            >
                {children}
            </DashboardLayout>
        </AppProvider>
    );
}
