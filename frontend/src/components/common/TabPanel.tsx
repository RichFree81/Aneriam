import { Box } from '@mui/material';
import type { ReactNode } from 'react';

interface TabPanelProps {
    children?: ReactNode;
    value: number;
    index: number;
    /** Prefix for aria IDs — keeps IDs unique per page (e.g. "portfolio", "project"). */
    idPrefix: string;
}

export default function TabPanel({ children, value, index, idPrefix }: TabPanelProps) {
    return (
        <div
            role="tabpanel"
            hidden={value !== index}
            id={`${idPrefix}-tabpanel-${index}`}
            aria-labelledby={`${idPrefix}-tab-${index}`}
        >
            {value === index && (
                <Box>
                    {children}
                </Box>
            )}
        </div>
    );
}
