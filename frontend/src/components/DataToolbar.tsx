import type { ReactNode } from 'react';
import { Box, Typography, TextField, InputAdornment, Stack, Paper } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';

interface DataToolbarProps {
    title?: string;
    onSearch?: (value: string) => void;
    searchPlaceholder?: string;
    actions?: ReactNode;
    filters?: ReactNode;
}

/**
 * DataToolbar
 * 
 * Standard toolbar for data views.
 * Layout: [Title] [Spacer] [Search] [Filters] [Actions]
 * 
 * Complies with Milestone E standards:
 * - Uses Box/Paper (no AppBar)
 * - Standard spacing and alignment
 */
export const DataToolbar = ({
    title,
    onSearch,
    searchPlaceholder = 'Search...',
    actions,
    filters,
}: DataToolbarProps) => {
    return (
        <Paper
            elevation={0}
            sx={{
                p: 2,
                mb: 2,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: 2,
                borderRadius: 1, // Matches card/paper defaults
                border: '1px solid',
                borderColor: 'divider',
            }}
        >
            {/* Title Section */}
            {title && (
                <Typography variant="h6" component="h2" sx={{ fontWeight: 600 }}>
                    {title}
                </Typography>
            )}

            {/* Actions Section (Right Aligned) */}
            <Stack
                direction="row"
                spacing={2}
                alignItems="center"
                useFlexGap
                flexWrap="wrap"
                sx={{ ml: 'auto' }}
            >

                {/* Search Input */}
                {onSearch && (
                    <TextField
                        size="small"
                        placeholder={searchPlaceholder}
                        onChange={(e) => onSearch(e.target.value)}
                        slotProps={{
                            input: {
                                startAdornment: (
                                    <InputAdornment position="start">
                                        <SearchIcon fontSize="small" color="action" />
                                    </InputAdornment>
                                ),
                            }
                        }}
                        sx={{ width: 240 }}
                        inputProps={{ 'aria-label': 'Search data' }}
                    />
                )}

                {/* Filters Slot */}
                {filters && (
                    <Box>
                        {filters}
                    </Box>
                )}

                {/* Primary Actions Slot */}
                {actions && (
                    <Box>
                        {actions}
                    </Box>
                )}
            </Stack>
        </Paper>
    );
};
