import { STORAGE_KEYS, API_CONFIG } from '../config';

export class ApiError extends Error {
    status: number;
    constructor(message: string, status: number) {
        super(message);
        this.status = status;
    }
}

/** How long (ms) before a fetch is automatically aborted. */
const REQUEST_TIMEOUT_MS = 30_000;

/**
 * Attempt to exchange the stored refresh token for a new access token.
 * Returns the new access token string on success, or null on failure.
 */
async function tryRefreshAccessToken(): Promise<string | null> {
    const refreshToken = localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN);
    if (!refreshToken) return null;

    try {
        const response = await fetch(`${API_CONFIG.BASE_URL}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken }),
            signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
        });
        if (!response.ok) return null;

        const data = await response.json();
        const newAccess: string = data.access_token;
        const newRefresh: string = data.refresh_token;

        localStorage.setItem(STORAGE_KEYS.TOKEN, newAccess);
        localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, newRefresh);
        return newAccess;
    } catch {
        return null;
    }
}

function clearSession(): void {
    localStorage.removeItem(STORAGE_KEYS.TOKEN);
    localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
    localStorage.removeItem(STORAGE_KEYS.USER);
}

/**
 * Authenticated fetch wrapper.
 * - Injects the Bearer token from localStorage.
 * - Aborts after REQUEST_TIMEOUT_MS milliseconds.
 * - On 401, attempts a single token refresh before giving up and redirecting.
 */
export async function authenticatedFetch(
    endpoint: string,
    options: RequestInit = {},
    _isRetry = false,
): Promise<Response> {
    const token = localStorage.getItem(STORAGE_KEYS.TOKEN);

    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...(options.headers as Record<string, string>),
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    let response: Response;
    try {
        response = await fetch(`${API_CONFIG.BASE_URL}${endpoint}`, {
            ...options,
            headers,
            // Respect caller-provided signal if present; otherwise use timeout signal.
            signal: options.signal ?? controller.signal,
        });
    } finally {
        clearTimeout(timeoutId);
    }

    if (response.status === 401 && !_isRetry) {
        // Attempt token refresh once before failing.
        const newToken = await tryRefreshAccessToken();
        if (newToken) {
            return authenticatedFetch(endpoint, options, true);
        }
        // Refresh failed — end the session.
        clearSession();
        window.location.href = '/login';
        throw new ApiError('Unauthorized', 401);
    }

    if (!response.ok) {
        throw new ApiError(response.statusText || 'request failed', response.status);
    }

    return response;
}
