import {
    createContext,
    useContext,
    useState,
    type ReactNode,
    useCallback,
    useEffect,
} from 'react';
import type { Portfolio } from '../types/portfolio';
import { getPortfolios } from '../api/portfolios';
import { useAuth } from './AuthContext';

interface PortfolioContextType {
    /** Currently active portfolio (null if none selected) */
    activePortfolio: Portfolio | null;
    /** Whether a portfolio is currently selected */
    hasActivePortfolio: boolean;
    /** List of available portfolios */
    portfolios: Portfolio[];
    /** Set the active portfolio */
    setActivePortfolio: (portfolio: Portfolio | null) => void;
    /** Clear the active portfolio selection */
    clearActivePortfolio: () => void;
    /** Fetch portfolios from API */
    refreshPortfolios: () => Promise<void>;
    isLoading: boolean;
    error: string | null;
}

const PortfolioContext = createContext<PortfolioContextType | undefined>(undefined);

interface PortfolioProviderProps {
    children: ReactNode;
}

// eslint-disable-next-line react-refresh/only-export-components
export function PortfolioProvider({ children }: PortfolioProviderProps) {
    const { token, isAuthenticated } = useAuth();
    const [activePortfolio, setActivePortfolioState] = useState<Portfolio | null>(() => {
        try {
            // Persist active portfolio in session to avoid loss on refresh
            const stored = sessionStorage.getItem('aneriam_active_portfolio');
            return stored ? JSON.parse(stored) : null;
        } catch {
            return null;
        }
    });

    const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    const setActivePortfolio = useCallback((portfolio: Portfolio | null) => {
        setActivePortfolioState(portfolio);
        if (portfolio) {
            sessionStorage.setItem('aneriam_active_portfolio', JSON.stringify(portfolio));
        } else {
            sessionStorage.removeItem('aneriam_active_portfolio');
        }
    }, []);

    const clearActivePortfolio = useCallback(() => {
        setActivePortfolio(null);
    }, [setActivePortfolio]);

    const refreshPortfolios = useCallback(async () => {
        if (!token) return;
        setIsLoading(true);
        setError(null);
        try {
            const data = await getPortfolios();
            setPortfolios(data);
        } catch (err) {
            console.error("Failed to fetch portfolios", err);
            setError("Failed to load portfolios");
        } finally {
            setIsLoading(false);
        }
    }, [token]);

    // Clear state on logout
    useEffect(() => {
        if (!isAuthenticated) {
            setPortfolios([]);
            setActivePortfolioState(null);
            sessionStorage.removeItem('aneriam_active_portfolio');
        }
    }, [isAuthenticated]);

    const hasActivePortfolio = activePortfolio !== null;

    return (
        <PortfolioContext.Provider
            value={{
                activePortfolio,
                hasActivePortfolio,
                portfolios,
                setActivePortfolio,
                clearActivePortfolio,
                refreshPortfolios,
                isLoading,
                error
            }}
        >
            {children}
        </PortfolioContext.Provider>
    );
}

/**
 * Hook to access portfolio context.
 * Must be used within PortfolioProvider.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function usePortfolio() {
    const context = useContext(PortfolioContext);
    if (!context) {
        throw new Error('usePortfolio must be used within a PortfolioProvider');
    }
    return context;
}
