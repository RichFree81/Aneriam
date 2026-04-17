/**
 * usePermission Hook
 *
 * Centralized permission checking hook.
 * Permissions are expressed as named capabilities, not raw role checks.
 *
 * Rules (per FRONTEND-MODULE-READINESS.md):
 * - P-01: UI permission checks MUST mirror backend enforcement
 * - P-02: Permission checks MUST be centralized in a shared hook
 * - P-03: Permissions MUST be expressed as named capabilities
 */

import { useCallback } from 'react';
import { useAuth } from '../context';

/**
 * Permission capability names.
 * Add capabilities as they are defined by the application.
 */
export type Permission =
    // Project permissions
    | 'canViewProjects'
    | 'canCreateProject'
    | 'canEditProject'
    | 'canDeleteProject'
    // User permissions
    | 'canViewUsers'
    | 'canCreateUser'
    | 'canEditUser'
    | 'canDeleteUser'
    // Admin permissions
    | 'canAccessAdmin'
    | 'canManageSettings'
    // Generic placeholder for future expansion
    | string;

import { UserRole } from '../types/enums';

/**
 * Role-to-permission mapping.
 * This is a simplified implementation; in production, this would
 * typically come from the backend or a dedicated permission service.
 */
const rolePermissions: Record<UserRole | string, Permission[]> = {
    [UserRole.ADMIN]: [
        'canViewProjects',
        'canCreateProject',
        'canEditProject',
        'canDeleteProject',
        'canViewUsers',
        'canCreateUser',
        'canEditUser',
        'canDeleteUser',
        'canAccessAdmin',
        'canManageSettings',
    ],
    [UserRole.COMPANY_ADMIN]: [
        'canViewProjects',
        'canCreateProject',
        'canEditProject',
        'canViewUsers',
    ],
    [UserRole.USER]: ['canViewProjects'],
};

/**
 * Hook for checking user permissions.
 * @returns Object with permission checking utilities
 */
export function usePermission() {
    const { user, isAuthenticated } = useAuth();

    /**
     * Check if the current user has a specific permission.
     * @param permission - The permission capability to check
     * @returns true if user has the permission, false otherwise
     */
    const hasPermission = useCallback(
        (permission: Permission): boolean => {
            if (!isAuthenticated || !user) {
                return false;
            }

            const userRole = user.role;
            const permissions = rolePermissions[userRole] ?? [];
            return permissions.includes(permission);
        },
        [isAuthenticated, user]
    );

    /**
     * Check if the current user has any of the specified permissions.
     * @param permissions - Array of permissions to check
     * @returns true if user has at least one permission
     */
    const hasAnyPermission = useCallback(
        (permissions: Permission[]): boolean => {
            return permissions.some((p) => hasPermission(p));
        },
        [hasPermission]
    );

    /**
     * Check if the current user has all of the specified permissions.
     * @param permissions - Array of permissions to check
     * @returns true if user has all permissions
     */
    const hasAllPermissions = useCallback(
        (permissions: Permission[]): boolean => {
            return permissions.every((p) => hasPermission(p));
        },
        [hasPermission]
    );

    return {
        hasPermission,
        hasAnyPermission,
        hasAllPermissions,
        isAuthenticated,
        userRole: user?.role,
    };
}
