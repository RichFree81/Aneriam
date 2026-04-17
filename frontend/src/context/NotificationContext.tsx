/**
 * Notification Context
 *
 * Provides global toast/snackbar notification queue.
 * All notifications should go through this context for consistent UX.
 *
 * Uses MUI Snackbar with locked theme tokens.
 */

import {
    createContext,
    useContext,
    useState,
    useCallback,
    type ReactNode,
} from 'react';
import { Snackbar, Alert, type AlertColor } from '@mui/material';

/**
 * Notification item structure.
 */
export interface Notification {
    id: string;
    message: string;
    severity: AlertColor;
    autoHideDuration?: number;
}

interface NotificationContextType {
    /** Show a notification */
    notify: (message: string, severity?: AlertColor, duration?: number) => void;
    /** Convenience methods */
    notifySuccess: (message: string) => void;
    notifyError: (message: string) => void;
    notifyWarning: (message: string) => void;
    notifyInfo: (message: string) => void;
}

const NotificationContext = createContext<NotificationContextType | undefined>(
    undefined
);

interface NotificationProviderProps {
    children: ReactNode;
}

const DEFAULT_DURATION = 5000;

// eslint-disable-next-line react-refresh/only-export-components
export function NotificationProvider({ children }: NotificationProviderProps) {
    const [notification, setNotification] = useState<Notification | null>(null);
    const [open, setOpen] = useState(false);

    const notify = useCallback(
        (
            message: string,
            severity: AlertColor = 'info',
            duration: number = DEFAULT_DURATION
        ) => {
            setNotification({
                id: Date.now().toString(),
                message,
                severity,
                autoHideDuration: duration,
            });
            setOpen(true);
        },
        []
    );

    const notifySuccess = useCallback(
        (message: string) => notify(message, 'success'),
        [notify]
    );
    const notifyError = useCallback(
        (message: string) => notify(message, 'error'),
        [notify]
    );
    const notifyWarning = useCallback(
        (message: string) => notify(message, 'warning'),
        [notify]
    );
    const notifyInfo = useCallback(
        (message: string) => notify(message, 'info'),
        [notify]
    );

    const handleClose = useCallback(
        (_event?: React.SyntheticEvent | Event, reason?: string) => {
            if (reason === 'clickaway') {
                return;
            }
            setOpen(false);
        },
        []
    );

    return (
        <NotificationContext.Provider
            value={{ notify, notifySuccess, notifyError, notifyWarning, notifyInfo }}
        >
            {children}
            <Snackbar
                open={open}
                autoHideDuration={notification?.autoHideDuration ?? DEFAULT_DURATION}
                onClose={handleClose}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
            >
                <Alert
                    onClose={handleClose}
                    severity={notification?.severity ?? 'info'}
                    variant="filled"
                    sx={{ width: '100%' }}
                >
                    {notification?.message}
                </Alert>
            </Snackbar>
        </NotificationContext.Provider>
    );
}

/**
 * Hook to access notification context.
 * Must be used within NotificationProvider.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useNotification() {
    const context = useContext(NotificationContext);
    if (!context) {
        throw new Error(
            'useNotification must be used within a NotificationProvider'
        );
    }
    return context;
}
