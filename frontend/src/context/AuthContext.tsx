import { createContext, useContext, useState, type ReactNode } from 'react';
import { login as apiLogin, logout as apiLogout } from '../api/auth';
import type { LoginRequest, User } from '../types/auth';

import { STORAGE_KEYS } from '../config';

interface AuthContextType {
    isAuthenticated: boolean;
    user: User | null;
    token: string | null;
    login: (credentials: LoginRequest) => Promise<void>;
    logout: () => Promise<void>;
    error: string | null;
    isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {

    const [user, setUser] = useState<User | null>(() => {
        try {
            const storedUser = localStorage.getItem(STORAGE_KEYS.USER);
            return storedUser ? JSON.parse(storedUser) : null;
        } catch (e) {
            console.error("Failed to parse stored user", e);
            localStorage.removeItem(STORAGE_KEYS.USER);
            return null;
        }
    });

    const [token, setToken] = useState<string | null>(() => {
        return localStorage.getItem(STORAGE_KEYS.TOKEN);
    });

    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(false);

    const isAuthenticated = !!user && !!token;

    const login = async (credentials: LoginRequest) => {
        setIsLoading(true);
        setError(null);
        try {
            const data = await apiLogin(credentials);
            setUser(data.user);
            setToken(data.access_token);

            // apiLogin already persists tokens; persist user separately for rehydration.
            localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(data.user));
        } catch (error) {
            console.error("Login error", error);
            setError(error instanceof Error ? error.message : "An unexpected error occurred");
            throw error;
        } finally {
            setIsLoading(false);
        }
    };

    const logout = async () => {
        // Call backend to revoke the access token JTI; also clears localStorage tokens.
        await apiLogout();
        setUser(null);
        setToken(null);
        setError(null);
        // Clear portfolio session state
        sessionStorage.removeItem(STORAGE_KEYS.ACTIVE_PORTFOLIO);
    };

    return (
        <AuthContext.Provider value={{ isAuthenticated, user, token, login, logout, error, isLoading }}>
            {children}
        </AuthContext.Provider>
    );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) throw new Error('useAuth must be used within an AuthProvider');
    return context;
};
