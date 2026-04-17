import React from 'react';
import { Alert, AlertTitle, Collapse } from '@mui/material';

interface FormGlobalErrorProps {
    error?: string | null;
    title?: string;
    severity?: 'error' | 'warning' | 'info';
}

/**
 * C3: FormGlobalError
 * Standardizes form-level feedback messages.
 * Uses MuiAlert with standard spacing.
 */
export const FormGlobalError: React.FC<FormGlobalErrorProps> = ({
    error,
    title = 'Submission Error',
    severity = 'error'
}) => {
    return (
        <Collapse in={!!error}>
            {error && (
                <Alert severity={severity} sx={{ mb: 3 }}>
                    {title && <AlertTitle>{title}</AlertTitle>}
                    {error}
                </Alert>
            )}
        </Collapse>
    );
};
