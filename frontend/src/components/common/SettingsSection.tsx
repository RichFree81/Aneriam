import { Box, Typography, IconButton, Button, Stack, Fade } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import type { ReactNode } from 'react';

interface SettingsSectionProps {
    title: string;
    children: ReactNode;
    isEditing: boolean;
    onEdit: () => void;
    onSave: () => void;
    onCancel: () => void;
}

export default function SettingsSection({
    title,
    children,
    isEditing,
    onEdit,
    onSave,
    onCancel
}: SettingsSectionProps) {
    return (
        <Box sx={{ mb: 4 }}>
            {/* Header: Title + Edit Icon (View Mode Only) */}
            <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 2, height: 32 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                    {title}
                </Typography>

                {!isEditing && (
                    <IconButton
                        size="small"
                        onClick={onEdit}
                        aria-label={`Edit ${title}`}
                        sx={{ color: 'text.secondary', '&:hover': { color: 'primary.main' } }}
                    >
                        <EditIcon fontSize="small" />
                    </IconButton>
                )}
            </Stack>

            {/* Content Container */}
            <Box sx={{
                p: 3,
                bgcolor: 'grey.50',
                borderRadius: 1,
                border: 1,
                borderColor: isEditing ? 'primary.main' : 'divider', // Highlight when editing
                transition: 'border-color 0.2s'
            }}>
                {children}

                {/* Footer: Save/Cancel (Edit Mode Only) */}
                {isEditing && (
                    <Fade in={isEditing}>
                        <Stack direction="row" spacing={2} justifyContent="flex-end" sx={{ mt: 3 }}>
                            <Button
                                variant="text"
                                color="inherit"
                                onClick={onCancel}
                            >
                                Cancel
                            </Button>
                            <Button
                                variant="contained"
                                color="primary"
                                onClick={onSave}
                            >
                                Save Changes
                            </Button>
                        </Stack>
                    </Fade>
                )}
            </Box>
        </Box>
    );
}
