import { useEffect } from 'react';
import { useActionRegistry, type GlobalAction } from '../context/ActionRegistryContext';

/**
 * Hook to register a global action while the component is mounted.
 * Automatically unregisters the action when the component unmounts.
 */
export function useRegisterAction(action: GlobalAction) {
    const { registerAction, unregisterAction } = useActionRegistry();

    useEffect(() => {
        registerAction(action);
        return () => unregisterAction(action.id);
    }, [registerAction, unregisterAction, action.id, action.label, action.priority]); // Dependencies to re-register if changed
}
