import { AppProvider } from '@toolpad/core/AppProvider';
import { Box, Typography, IconButton } from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import { DashboardLayout } from '@toolpad/core/DashboardLayout';
import { Account } from '@toolpad/core/Account';
import logoImg from '../assets/logo.png';
import { useAuth } from '../context/AuthContext';
import { usePortfolio } from '../context/PortfolioContext';
import { useProjectFilter } from '../context/ProjectFilterContext';
import ProjectSelectionDialog from '../components/dialogs/ProjectSelectionDialog';
import GlobalAddMenu from '../components/common/GlobalAddMenu';
import FilterListIcon from '@mui/icons-material/FilterList';
import { useState } from 'react';
import type { ReactNode } from 'react';
import type { Router } from '@toolpad/core/AppProvider';
import { useNavigate, useLocation } from 'react-router-dom';
import { NAVIGATION } from '../config/navigation.config';
import theme from '../theme';

interface ToolpadShellProps {
    children: ReactNode;
}

export default function ToolpadShell({ children }: ToolpadShellProps) {
    const { user, logout } = useAuth();
    const { activePortfolio, clearActivePortfolio } = usePortfolio();
    const { filterMode, selectedProjectIds, projects } = useProjectFilter();
    const [projectDialogOpen, setProjectDialogOpen] = useState(false);

    // Derived display string
    const projectStatus = filterMode === 'ALL'
        ? 'All Projects'
        : selectedProjectIds.length === 1
            ? projects.find(p => p.id === selectedProjectIds[0])?.name || 'Unknown Project'
            : `${selectedProjectIds.length} Selected`;

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
            theme={theme}
            navigation={NAVIGATION}
            router={router}
            branding={{
                logo: (
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        {/* Custom Breadcrumb - In Flow */}
                        <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 500 }}>
                            {activePortfolio?.name} / {projectStatus}
                        </Typography>

                        {/* App Logo - Fixed Center - Hidden on Mobile */}
                        <Box sx={{
                            position: 'fixed',
                            top: 12,
                            left: '50%',
                            transform: 'translateX(-50%)',
                            display: { xs: 'none', md: 'flex' }, /* Hide on small screens */
                            alignItems: 'center',
                            zIndex: 1200,
                            pointerEvents: 'none' /* ensure clicks pass through if invisible space overlaps */
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
                            <GlobalAddMenu />
                            <IconButton color="inherit" aria-label="Filter projects" onClick={() => setProjectDialogOpen(true)}>
                                <FilterListIcon />
                            </IconButton>
                            <IconButton color="inherit" aria-label="Open settings" onClick={() => navigate('/settings')}>
                                <SettingsIcon />
                            </IconButton>
                        </Box>
                    )
                }}
            >
                {children}
                <ProjectSelectionDialog
                    open={projectDialogOpen}
                    onClose={() => setProjectDialogOpen(false)}
                />
            </DashboardLayout>
        </AppProvider>
    );
}
