/**
 * ErrorBoundary Component
 *
 * React Error Boundary for catching and displaying errors gracefully.
 *
 * Usage:
 * - App level: Catch-all for unhandled errors
 * - Route level: Per-page isolation
 * - Component level: For critical widgets
 */

import { Component, type ReactNode, type ErrorInfo } from 'react';
import ErrorState from '../ui/feedback/ErrorState';

interface ErrorBoundaryProps {
    /** Child components to wrap */
    children: ReactNode;
    /** Optional fallback component to render on error */
    fallback?: ReactNode;
    /** Optional callback when an error is caught */
    onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface ErrorBoundaryState {
    hasError: boolean;
    error: Error | null;
}

export default class ErrorBoundary extends Component<
    ErrorBoundaryProps,
    ErrorBoundaryState
> {
    constructor(props: ErrorBoundaryProps) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): ErrorBoundaryState {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        // Log error to console in development
        if (import.meta.env.DEV) {
            console.error('ErrorBoundary caught an error:', error, errorInfo);
        }

        // Call optional error callback
        this.props.onError?.(error, errorInfo);
    }

    handleRetry = () => {
        this.setState({ hasError: false, error: null });
    };

    render() {
        if (this.state.hasError) {
            // Use custom fallback if provided
            if (this.props.fallback) {
                return this.props.fallback;
            }

            // Default error display using locked ErrorState component
            return (
                <ErrorState
                    title="Something went wrong"
                    message="An unexpected error occurred. Please try again."
                    onRetry={this.handleRetry}
                />
            );
        }

        return this.props.children;
    }
}
