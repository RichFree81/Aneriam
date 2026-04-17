
import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

export interface GlobalAction {
    id: string;
    label: string;
    onClick: () => void;
    icon?: ReactNode;
    priority?: number;
}

interface ActionRegistryContextType {
    actions: GlobalAction[];
    registerAction: (action: GlobalAction) => void;
    unregisterAction: (id: string) => void;
}

const ActionRegistryContext = createContext<ActionRegistryContextType | undefined>(undefined);

export function ActionRegistryProvider({ children }: { children: ReactNode }) {
    const [actions, setActions] = useState<GlobalAction[]>([]);

    const registerAction = useCallback((action: GlobalAction) => {
        setActions(prev => {
            // Prevent duplicates
            if (prev.some(a => a.id === action.id)) return prev;

            const newActions = [...prev, action];
            // Sort by priority (desc)
            return newActions.sort((a, b) => (b.priority || 0) - (a.priority || 0));
        });
    }, []);

    const unregisterAction = useCallback((id: string) => {
        setActions(prev => prev.filter(a => a.id !== id));
    }, []);

    return (
        <ActionRegistryContext.Provider value={{ actions, registerAction, unregisterAction }}>
            {children}
        </ActionRegistryContext.Provider>
    );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useActionRegistry() {
    const context = useContext(ActionRegistryContext);
    if (!context) {
        throw new Error('useActionRegistry must be used within an ActionRegistryProvider');
    }
    return context;
}
