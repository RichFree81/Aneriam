/**
 * Context barrel export
 *
 * Central export for all context providers and hooks.
 * Modules MUST import contexts from here, not directly from context files.
 */

// Auth Context
export { AuthProvider, useAuth } from './AuthContext';

// Project Context
export { PortfolioProvider, usePortfolio } from './PortfolioContext';
export { ProjectFilterProvider, useProjectFilter } from './ProjectFilterContext';

// Action Registry
export { ActionRegistryProvider, useActionRegistry } from './ActionRegistryContext';
export { useRegisterAction } from '../hooks/useRegisterAction';


// Notification Context
export {
    NotificationProvider,
    useNotification,
    type Notification,
} from './NotificationContext';
