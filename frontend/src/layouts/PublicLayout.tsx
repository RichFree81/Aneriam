import { Box, Container } from '@mui/material';
import type { ReactNode } from 'react';

/**
 * PublicLayout
 * 
 * A full-height, centered layout for public pages like Login or Register.
 * Do not implement page-specific layout here; keep this generic and reusable.
 */

interface PublicLayoutProps {
    children: ReactNode;
    maxWidth?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
}

export default function PublicLayout({ children, maxWidth = 'sm' }: PublicLayoutProps) {
    return (
        <Box
            component="main"
            sx={{
                minHeight: '100vh',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                bgcolor: 'background.default',
                py: 3
            }}
        >
            <Container maxWidth={maxWidth}>
                {children}
            </Container>
        </Box>
    );
}
