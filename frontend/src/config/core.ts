export const STORAGE_KEYS = {
    TOKEN: 'aneriam_token',
    REFRESH_TOKEN: 'aneriam_refresh_token',
    USER: 'aneriam_user',
    ACTIVE_PORTFOLIO: 'aneriam_active_portfolio',
};

function resolveApiBaseUrl(): string {
    const envUrl = import.meta.env.VITE_API_URL;
    if (envUrl) return envUrl;

    // In production builds, refuse to fall back to plain HTTP localhost.
    if (import.meta.env.PROD) {
        throw new Error(
            'VITE_API_URL environment variable is required in production. ' +
            'Set it to your backend HTTPS URL before building.'
        );
    }

    // Development fallback only.
    return 'http://127.0.0.1:8000';
}

export const API_CONFIG = {
    BASE_URL: resolveApiBaseUrl(),
};
