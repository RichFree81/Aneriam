/**
 * useDataFetch Hook
 *
 * Standardized data fetching with lifecycle state handling.
 *
 * Rules (per FRONTEND-MODULE-READINESS.md):
 * - D-01: Data views MUST implement all four lifecycle states
 * - D-02: Loading indicators MUST appear within 300ms of request start
 * - D-08: Requests SHOULD be cancelled on component unmount
 */

import { useState, useEffect, useCallback, useRef } from 'react';

export interface UseDataFetchOptions<T> {
    /** Initial data value */
    initialData?: T;
    /** Whether to fetch immediately on mount */
    immediate?: boolean;
    /** Delay before showing loading state (per D-02: max 300ms) */
    loadingDelay?: number;
}

export interface UseDataFetchResult<T> {
    /** Fetched data (null if not yet loaded or error) */
    data: T | null;
    /** Whether the request is currently loading */
    loading: boolean;
    /** Error object if request failed */
    error: Error | null;
    /** Refetch the data */
    refetch: () => Promise<void>;
    /** Whether data is empty (loaded successfully but empty) */
    isEmpty: boolean;
}

/**
 * Hook for standardized data fetching with lifecycle states.
 *
 * @param fetchFn - Async function that returns the data
 * @param options - Configuration options
 * @returns Object with data, loading, error, refetch, isEmpty
 *
 * @example
 * ```tsx
 * const { data, loading, error, refetch, isEmpty } = useDataFetch(
 *   () => fetchProjects(),
 *   { immediate: true }
 * );
 * ```
 */
export function useDataFetch<T>(
    fetchFn: (signal: AbortSignal) => Promise<T>,
    options: UseDataFetchOptions<T> = {}
): UseDataFetchResult<T> {
    const { initialData, immediate = true, loadingDelay = 300 } = options;

    const [data, setData] = useState<T | null>(initialData ?? null);
    const [loading, setLoading] = useState(immediate);
    const [showLoading, setShowLoading] = useState(false);
    const [error, setError] = useState<Error | null>(null);

    // AbortController ref for cleanup
    const abortControllerRef = useRef<AbortController | null>(null);
    // Loading timer ref
    const loadingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const fetch = useCallback(async () => {
        // Cancel any in-flight request
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }

        // Create new AbortController
        abortControllerRef.current = new AbortController();
        const signal = abortControllerRef.current.signal;

        // Start loading
        setLoading(true);
        setError(null);

        // Delay showing loading indicator per D-02
        loadingTimerRef.current = setTimeout(() => {
            setShowLoading(true);
        }, loadingDelay);

        try {
            const result = await fetchFn(signal);
            if (!signal.aborted) {
                setData(result);
                setError(null);
            }
        } catch (err) {
            if (!signal.aborted) {
                if (err instanceof Error && err.name === 'AbortError') {
                    // Request was cancelled, don't update state
                    return;
                }
                setError(err instanceof Error ? err : new Error('Unknown error'));
                setData(null);
            }
        } finally {
            if (!signal.aborted) {
                setLoading(false);
                setShowLoading(false);
                if (loadingTimerRef.current) {
                    clearTimeout(loadingTimerRef.current);
                }
            }
        }
    }, [fetchFn, loadingDelay]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
            if (loadingTimerRef.current) {
                clearTimeout(loadingTimerRef.current);
            }
        };
    }, []);

    // Initial fetch
    useEffect(() => {
        if (immediate) {
            fetch();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [immediate]);

    // Check if data is empty
    const isEmpty =
        !loading &&
        !error &&
        data !== null &&
        (Array.isArray(data) ? data.length === 0 : false);

    return {
        data,
        loading: showLoading,
        error,
        refetch: fetch,
        isEmpty,
    };
}
