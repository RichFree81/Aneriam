/**
 * useFeatureFlag Hook
 *
 * Centralized feature flag consumption.
 *
 * Rules (per FRONTEND-MODULE-READINESS.md):
 * - P-06: Feature flags SHOULD be consumed via a single hook
 * - P-07: Feature flags MUST default to false if unavailable
 * - P-08: Feature-flagged code MUST NOT leave dead code paths when flag is removed
 */

import { useCallback } from 'react';

/**
 * Feature flag names.
 * Add flags as features are developed.
 */
export type FeatureFlag =
    | 'enableNewDashboard'
    | 'enableProjectAnalytics'
    | 'enableDarkMode'
    | 'enableBetaFeatures'
    // Generic placeholder for future expansion
    | string;

/**
 * Static feature flag configuration.
 * In production, this would be loaded from a configuration service.
 */
const featureFlags: Record<FeatureFlag, boolean> = {
    enableNewDashboard: false,
    enableProjectAnalytics: false,
    enableDarkMode: false,
    enableBetaFeatures: import.meta.env.DEV, // Beta features only in dev
};

/**
 * Hook for checking feature flags.
 * @returns Object with feature flag utilities
 */
export function useFeatureFlag() {
    /**
     * Check if a feature flag is enabled.
     * @param flag - The feature flag to check
     * @returns true if enabled, false otherwise (defaults to false)
     */
    const isEnabled = useCallback((flag: FeatureFlag): boolean => {
        // Default to false if flag is not defined (per P-07)
        return featureFlags[flag] ?? false;
    }, []);

    /**
     * Check if any of the specified feature flags are enabled.
     * @param flags - Array of flags to check
     * @returns true if at least one flag is enabled
     */
    const isAnyEnabled = useCallback(
        (flags: FeatureFlag[]): boolean => {
            return flags.some((f) => isEnabled(f));
        },
        [isEnabled]
    );

    /**
     * Check if all of the specified feature flags are enabled.
     * @param flags - Array of flags to check
     * @returns true if all flags are enabled
     */
    const isAllEnabled = useCallback(
        (flags: FeatureFlag[]): boolean => {
            return flags.every((f) => isEnabled(f));
        },
        [isEnabled]
    );

    return {
        isEnabled,
        isAnyEnabled,
        isAllEnabled,
    };
}
