/**
 * DataView Component
 *
 * Wrapper component that handles data lifecycle states.
 * Uses locked feedback components from Milestone D.
 *
 * Rules (per FRONTEND-MODULE-READINESS.md):
 * - D-01: Data views MUST implement all four lifecycle states
 * - D-03: Error states MUST display user-friendly messages
 * - D-06: ErrorState MUST include a Retry action when recoverable
 */

import type { ReactNode } from 'react';
import LoadingState from '../ui/feedback/LoadingState';
import ErrorState from '../ui/feedback/ErrorState';
import EmptyState from '../ui/feedback/EmptyState';

interface DataViewProps {
    /** Whether data is currently loading */
    loading?: boolean;
    /** Error object if fetch failed */
    error?: Error | null;
    /** Whether the data set is empty */
    isEmpty?: boolean;
    /** Content to render when data is loaded successfully */
    children: ReactNode;
    /** Optional loading message */
    loadingMessage?: string;
    /** Error title */
    errorTitle?: string;
    /** Error message override (defaults to error.message or generic) */
    errorMessage?: string;
    /** Retry callback for error state */
    onRetry?: () => void;
    /** Empty state title */
    emptyTitle?: string;
    /** Empty state message */
    emptyMessage?: string;
    /** Optional action for empty state */
    emptyAction?: ReactNode;
}

/**
 * DataView renders appropriate feedback based on data lifecycle state.
 *
 * Order of precedence:
 * 1. Loading → LoadingState
 * 2. Error → ErrorState
 * 3. Empty → EmptyState
 * 4. Success → children
 *
 * @example
 * ```tsx
 * <DataView
 *   loading={loading}
 *   error={error}
 *   isEmpty={isEmpty}
 *   onRetry={refetch}
 *   emptyTitle="No projects found"
 *   emptyMessage="Create your first project to get started"
 * >
 *   <ProjectList projects={data} />
 * </DataView>
 * ```
 */
export default function DataView({
    loading = false,
    error = null,
    isEmpty = false,
    children,
    loadingMessage,
    errorTitle = 'Something went wrong',
    errorMessage,
    onRetry,
    emptyTitle = 'No data',
    emptyMessage = 'There are no items to display.',
    emptyAction,
}: DataViewProps) {
    // State 1: Loading
    if (loading) {
        return <LoadingState message={loadingMessage} />;
    }

    // State 2: Error
    if (error) {
        const displayMessage =
            errorMessage ||
            (error.message !== 'Unknown error'
                ? error.message
                : 'An unexpected error occurred. Please try again.');

        return (
            <ErrorState title={errorTitle} message={displayMessage} onRetry={onRetry} />
        );
    }

    // State 3: Empty
    if (isEmpty) {
        return (
            <EmptyState title={emptyTitle} message={emptyMessage} action={emptyAction} />
        );
    }

    // State 4: Success - render children
    return <>{children}</>;
}
