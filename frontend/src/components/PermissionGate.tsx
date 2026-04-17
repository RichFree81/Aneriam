/**
 * PermissionGate Component
 *
 * Wrapper component for conditional rendering based on permissions.
 *
 * Rules (per FRONTEND-MODULE-READINESS.md):
 * - P-04: Hidden controls MUST NOT be rendered in DOM
 * - P-05: Disabled buttons MUST show a tooltip explaining why disabled
 */

import type { ReactNode } from 'react';
import { Tooltip } from '@mui/material';
import { usePermission, type Permission } from '../hooks';

interface PermissionGateProps {
    /** Required permission to view content */
    permission: Permission;
    /** Content to render when permission is granted */
    children: ReactNode;
    /**
     * If true, hides content when permission is denied.
     * If false, renders fallback or disabled state.
     * @default true
     */
    hideWhenDenied?: boolean;
    /**
     * Optional fallback content when permission is denied
     * and hideWhenDenied is false.
     */
    fallback?: ReactNode;
    /**
     * Tooltip message to show when content is disabled.
     * Only used when hideWhenDenied is false and no fallback is provided.
     */
    disabledTooltip?: string;
}

/**
 * PermissionGate conditionally renders content based on user permissions.
 *
 * Usage:
 * ```tsx
 * // Hide when denied (default)
 * <PermissionGate permission="canEditProject">
 *   <EditButton />
 * </PermissionGate>
 *
 * // Show disabled with tooltip
 * <PermissionGate
 *   permission="canDeleteProject"
 *   hideWhenDenied={false}
 *   disabledTooltip="You don't have permission to delete projects"
 * >
 *   <DeleteButton disabled />
 * </PermissionGate>
 * ```
 */
export default function PermissionGate({
    permission,
    children,
    hideWhenDenied = true,
    fallback,
    disabledTooltip = 'You do not have permission to perform this action',
}: PermissionGateProps) {
    const { hasPermission } = usePermission();

    const isGranted = hasPermission(permission);

    // Permission granted - render children
    if (isGranted) {
        return <>{children}</>;
    }

    // Permission denied and should hide - render nothing (not in DOM per P-04)
    if (hideWhenDenied) {
        return null;
    }

    // Permission denied with custom fallback
    if (fallback) {
        return <>{fallback}</>;
    }

    // Permission denied - render disabled with tooltip (per P-05)
    return (
        <Tooltip title={disabledTooltip} arrow>
            <span style={{ display: 'inline-block' }}>{children}</span>
        </Tooltip>
    );
}
