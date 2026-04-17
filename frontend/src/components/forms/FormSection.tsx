import React from 'react';
import { Box, Stack, Typography } from '@mui/material';

interface FormSectionProps {
    title?: string;
    description?: string;
    children: React.ReactNode;
}

/**
 * C1/C5: FormSection
 * Standardizes the grouping and spacing of form fields.
 * Uses a Stack for vertical spacing between fields.
 */
export const FormSection: React.FC<FormSectionProps> = ({ title, description, children }) => {
    return (
        <Box component="section" sx={{ mb: 4 }}>
            {(title || description) && (
                <Box sx={{ mb: 2 }}>
                    {title && (
                        <Typography variant="subtitle1" component="h3" gutterBottom sx={{ fontWeight: 600 }}>
                            {title}
                        </Typography>
                    )}
                    {description && (
                        <Typography variant="body2" color="text.secondary">
                            {description}
                        </Typography>
                    )}
                </Box>
            )}
            <Stack spacing={3}>
                {children}
            </Stack>
        </Box>
    );
};
