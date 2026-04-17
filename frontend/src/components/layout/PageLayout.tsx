import { Box, Typography, Tabs, Tab, Breadcrumbs, Link } from '@mui/material';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import type { ReactNode } from 'react';

/**
 * Spacing Context Definitions (per PAGE_SPACING_SPEC §4.2)
 * - Standard: 3x (24px) for general dashboards and module pages
 * - Utility:  2x (16px) for settings/dense modules
 */
type PageContextType = 'standard' | 'utility';

interface PageLayoutProps {
    children: ReactNode;
    title?: string;
    breadcrumbs?: { title: string; path?: string }[];
    type?: PageContextType;

    // Type B Header Props (Tabs)
    tabs?: {
        value: number;
        onChange: (event: React.SyntheticEvent, newValue: number) => void;
        items: { label: string; value?: number }[];
    };
}

export default function PageLayout({
    children,
    title,
    breadcrumbs = [],
    type = 'standard',
    tabs,
}: PageLayoutProps) {

    // Spacing Token Logic (PAGE_SPACING_SPEC §4.2)
    // Standard = 3 (24px), Utility = 2 (16px)
    const spacingToken = type === 'utility' ? 2 : 3;

    // Header Style Logic
    // Utility pages get the dark background
    const headerBg = type === 'utility' ? 'primary.main' : 'background.paper';
    const headerColor = type === 'utility' ? 'common.white' : 'text.primary';
    const bottomBorder = 1;

    return (
        <Box sx={{
            width: '100%',
            minHeight: '100%',
            display: 'flex',
            flexDirection: 'column',
            bgcolor: 'background.default' // Ensure base background is correct
        }}>
            {/* 1. Full-Bleed Header Block */}
            <Box sx={{
                width: '100%',
                bgcolor: headerBg,
                color: headerColor,
                borderBottom: bottomBorder,
                borderColor: 'divider',
                px: 3, // Standard Horizontal Padding
                pt: 2, // Standard Top Padding
                pb: tabs ? 0 : 2, // Tabs sit on the line, otherwise balanced padding
            }}>

                {/* Manual Breadcrumbs (if provided) */}
                {breadcrumbs.length > 0 && (
                    <Breadcrumbs
                        separator={<NavigateNextIcon fontSize="small" sx={{ color: 'inherit' }} />}
                        aria-label="breadcrumb"
                        sx={{ mb: 1, color: 'inherit' }}
                    >
                        {breadcrumbs.map((crumb, index) => (
                            crumb.path ? (
                                <Link key={index} underline="hover" color="inherit" href={crumb.path}>
                                    {crumb.title}
                                </Link>
                            ) : (
                                <Typography key={index} color="inherit">
                                    {crumb.title}
                                </Typography>
                            )
                        ))}
                    </Breadcrumbs>
                )}

                {/* Page Title */}
                {title && (
                    <Typography
                        variant={type === 'utility' ? 'h6' : 'h4'}
                        gutterBottom={!tabs}
                        color="inherit"
                        sx={{ mb: tabs ? 1 : 0, fontWeight: type === 'utility' ? 500 : 400 }}
                    >
                        {title}
                    </Typography>
                )}

                {/* Type B Tabs */}
                {tabs && (
                    <Tabs
                        value={tabs.value}
                        onChange={tabs.onChange}
                        textColor="inherit"
                        aria-label="page tabs"
                        sx={{
                            minHeight: 0,
                            mb: -1 / 8, // Sit exactly on the border
                            '& .MuiTab-root': { color: 'inherit', opacity: 0.7, '&.Mui-selected': { opacity: 1 } }
                        }}
                    >
                        {tabs.items.map((tab, index) => (
                            <Tab key={index} label={tab.label} />
                        ))}
                    </Tabs>
                )}
            </Box>

            {/* 2. Content Block */}
            <Box sx={{
                p: spacingToken,
                flexGrow: 1, // Fill remaining space
                bgcolor: 'background.paper' // Canvas background
            }}>
                {children}
            </Box>
        </Box>
    );
}
