import { useState } from 'react';
import { Box, IconButton, Menu, MenuItem, ListItemIcon, ListItemText, Tooltip } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { useActionRegistry } from '../../context/ActionRegistryContext';

export default function GlobalAddMenu() {
    const { actions } = useActionRegistry();
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
    const open = Boolean(anchorEl);

    if (actions.length === 0) {
        return null;
    }

    const handleClick = (event: React.MouseEvent<HTMLElement>) => {
        // If only one action, check if we want direct click? 
        // For consistency, let's stick to menu, or maybe direct for single item?
        // User requested "menu".
        setAnchorEl(event.currentTarget);
    };

    const handleClose = () => {
        setAnchorEl(null);
    };

    const handleActionClick = (action: () => void) => {
        handleClose();
        action();
    };

    return (
        <Box>
            <Tooltip title="Create New...">
                <IconButton
                    onClick={handleClick}
                    size="small"
                    sx={{ ml: 1 }}
                    aria-controls={open ? 'global-add-menu' : undefined}
                    aria-haspopup="true"
                    aria-expanded={open ? 'true' : undefined}
                >
                    <AddIcon />
                </IconButton>
            </Tooltip>
            <Menu
                anchorEl={anchorEl}
                id="global-add-menu"
                open={open}
                onClose={handleClose}
                onClick={handleClose}
                transformOrigin={{ horizontal: 'right', vertical: 'top' }}
                anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
            >
                {actions.map((action) => (
                    <MenuItem key={action.id} onClick={() => handleActionClick(action.onClick)}>
                        {action.icon && (
                            <ListItemIcon>
                                {action.icon}
                            </ListItemIcon>
                        )}
                        <ListItemText>{action.label}</ListItemText>
                    </MenuItem>
                ))}
            </Menu>
        </Box>
    );
}
