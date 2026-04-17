/**
 * Route Configuration
 *
 * Central registry for all route paths and constants.
 * All route strings MUST be defined here; no inline route strings allowed.
 *
 * Rules (per FRONTEND-MODULE-READINESS.md):
 * - R-01: Routes MUST use kebab-case
 * - R-02: Collection routes MUST be plural nouns
 * - R-03: Detail routes MUST follow /:collection/:id pattern
 * - R-04: Action routes MUST use /new or /edit suffix
 * - R-05: Dynamic segments MUST use :paramName format with camelCase
 */

/**
 * Application route paths.
 * Use these constants instead of inline strings.
 */
export const ROUTES = {
    // Public routes
    LOGIN: '/login',

    // Core application routes
    HOME: '/',

    // Future module routes (add as modules are implemented):
    // PROJECTS: '/projects',
    // PROJECT_DETAIL: '/projects/:id',
    // PROJECT_NEW: '/projects/new',
    // PROJECT_EDIT: '/projects/:id/edit',
    //
    // USERS: '/users',
    // USER_DETAIL: '/users/:id',

    // Auth-only routes
    SELECT_PORTFOLIO: '/select-portfolio',

    // Error routes
    NOT_FOUND: '*',
} as const;

/**
 * Route type for type-safe route usage.
 */
export type RouteKey = keyof typeof ROUTES;
export type RoutePath = (typeof ROUTES)[RouteKey];

/**
 * Helper to build dynamic route paths.
 * @example buildRoute(ROUTES.PROJECT_DETAIL, { id: '123' }) => '/projects/123'
 */
export function buildRoute(
    template: string,
    params: Record<string, string | number>
): string {
    let path = template;
    for (const [key, value] of Object.entries(params)) {
        path = path.replace(`:${key}`, String(value));
    }
    return path;
}

/**
 * Route metadata for configuration.
 * Defines properties for each route beyond just the path.
 */
export interface RouteConfig {
    /** The route path (from ROUTES constant) */
    path: string;
    /** Whether this route requires authentication */
    requiresAuth: boolean;
    /** Whether this route is only available in development */
    devOnly?: boolean;
    /** Optional permission required to access this route */
    permission?: string;
    /** Page title for this route */
    title?: string;
}

/**
 * Route configurations.
 * Add metadata for routes that need special handling.
 */
export const routeConfigs: Record<string, RouteConfig> = {
    [ROUTES.LOGIN]: {
        path: ROUTES.LOGIN,
        requiresAuth: false,
        title: 'Login',
    },
    [ROUTES.HOME]: {
        path: ROUTES.HOME,
        requiresAuth: true,
        title: 'Home',
    },
};
