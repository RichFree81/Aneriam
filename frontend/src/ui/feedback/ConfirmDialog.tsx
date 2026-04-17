
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    DialogContentText,
    type ButtonProps,
    useTheme,
    useMediaQuery
} from '@mui/material';

interface ConfirmDialogProps {
    open: boolean;
    title: string;
    content: string;
    confirmLabel?: string;
    cancelLabel?: string;
    isDestructive?: boolean;
    onConfirm: () => void;
    onCancel: () => void;
}

/**
 * Standardized Confirmation Dialog (Milestone D).
 * 
 * Enforces a strict pattern for boolean decisions (Confirm/Cancel).
 * Supports "Destructive" mode for irreversible actions.
 */
export default function ConfirmDialog({
    open,
    title,
    content,
    confirmLabel = 'Confirm',
    cancelLabel = 'Cancel',
    isDestructive = false,
    onConfirm,
    onCancel,
}: ConfirmDialogProps) {

    // Determine button colors based on destructiveness
    const confirmColor: ButtonProps['color'] = isDestructive ? 'error' : 'primary';

    // Responsive control for mobile
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    // Accessibility: Prevent accidental confirmation for destructive actions
    // Focus Cancel by default if the action is destructive.
    const autoFocusConfirm = !isDestructive;
    const autoFocusCancel = isDestructive;

    return (
        <Dialog
            open={open}
            onClose={onCancel}
            aria-labelledby="confirm-dialog-title"
            aria-describedby="confirm-dialog-description"
            maxWidth="xs"
            fullWidth
            fullScreen={isMobile} // F2 standard: Dialog sizing on small screens
        >
            <DialogTitle id="confirm-dialog-title">
                {title}
            </DialogTitle>
            <DialogContent>
                <DialogContentText id="confirm-dialog-description">
                    {content}
                </DialogContentText>
            </DialogContent>
            <DialogActions>
                <Button
                    onClick={onCancel}
                    color="inherit"
                    autoFocus={autoFocusCancel}
                >
                    {cancelLabel}
                </Button>
                <Button
                    onClick={onConfirm}
                    color={confirmColor}
                    variant="contained"
                    autoFocus={autoFocusConfirm}
                >
                    {confirmLabel}
                </Button>
            </DialogActions>
        </Dialog>
    );
}
