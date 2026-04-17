import type { Navigation } from '@toolpad/core/AppProvider';
import HomeIcon from '@mui/icons-material/Home';
import PersonIcon from '@mui/icons-material/Person';
import SecurityIcon from '@mui/icons-material/Security';
import ViewModuleIcon from '@mui/icons-material/ViewModule';
import ExitToAppIcon from '@mui/icons-material/ExitToApp';

/**
 * Navigation Configuration
 * 
 * Defines the sidebar menu structure for the Toolpad Shell.
 * This configuration is fed into the AppProvider navigation prop.
 */
export const NAVIGATION: Navigation = [
    {
        kind: 'header',
        title: 'Main',
    },
    {
        segment: '',
        title: 'Home',
        icon: <HomeIcon />,
    },
    // Future module navigation will be added here
];

export const SETTINGS_NAVIGATION: Navigation = [
    {
        kind: 'header',
        title: 'Settings',
    },
    {
        segment: 'settings/profile',
        title: 'Profile',
        icon: <PersonIcon />,
    },
    {
        segment: 'settings/security',
        title: 'Security',
        icon: <SecurityIcon />,
    },
    {
        segment: 'settings/modules',
        title: 'Modules',
        icon: <ViewModuleIcon />,
    },
    {
        kind: 'divider',
    },
    {
        segment: '', // navigating back to root
        title: 'Back to App',
        icon: <ExitToAppIcon />,
    },
];
