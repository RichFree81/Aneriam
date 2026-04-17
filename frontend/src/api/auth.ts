import type { LoginRequest, LoginResponse } from '../types/auth';
import { API_CONFIG, STORAGE_KEYS } from '../config';
import { authenticatedFetch } from './client';

export async function login(credentials: LoginRequest): Promise<LoginResponse> {
    const response = await fetch(`${API_CONFIG.BASE_URL}/auth/login`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(credentials),
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Login failed');
    }

    const data: LoginResponse = await response.json();

    // Persist both tokens so the client can silently refresh.
    localStorage.setItem(STORAGE_KEYS.TOKEN, data.access_token);
    localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, data.refresh_token);

    return data;
}

/**
 * Call the backend logout endpoint to revoke the current access token JTI,
 * then remove all locally-stored session data.
 * Errors are swallowed — local session is always cleared regardless.
 */
export async function logout(): Promise<void> {
    try {
        await authenticatedFetch('/auth/logout', { method: 'POST' });
    } catch {
        // Best-effort: always clear local state even if the server call fails.
    } finally {
        localStorage.removeItem(STORAGE_KEYS.TOKEN);
        localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
        localStorage.removeItem(STORAGE_KEYS.USER);
    }
}
