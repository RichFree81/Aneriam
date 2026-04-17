import {
    createContext,
    useContext,
    useState,
    useEffect,
    useCallback,
    type ReactNode
} from 'react';
import type { Project } from '../types/project';
import { getProjects } from '../api/projects';
import { usePortfolio } from './PortfolioContext';

export type ProjectFilterMode = 'ALL' | 'SPECIFIC';

interface ProjectFilterContextType {
    projects: Project[];
    isLoading: boolean;
    error: string | null;

    // Selection State
    filterMode: ProjectFilterMode;
    selectedProjectIds: number[];

    // Actions
    setFilterMode: (mode: ProjectFilterMode) => void;
    toggleProjectSelection: (projectId: number) => void;
    selectAllProjects: () => void;
    clearProjectSelection: () => void;
    refreshProjects: () => Promise<void>;
}

const ProjectFilterContext = createContext<ProjectFilterContextType | undefined>(undefined);

export function ProjectFilterProvider({ children }: { children: ReactNode }) {
    const { activePortfolio } = usePortfolio();

    const [projects, setProjects] = useState<Project[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Filter State
    const [filterMode, setFilterMode] = useState<ProjectFilterMode>('ALL');
    const [selectedProjectIds, setSelectedProjectIds] = useState<number[]>([]);

    const refreshProjects = useCallback(async () => {
        if (!activePortfolio) {
            setProjects([]);
            return;
        }

        setIsLoading(true);
        setError(null);
        try {
            const data = await getProjects(activePortfolio.id);
            setProjects(data);
        } catch (err) {
            console.error("Failed to fetch projects", err);
            setError("Failed to load projects");
        } finally {
            setIsLoading(false);
        }
    }, [activePortfolio]);

    // Fetch projects when active portfolio changes
    useEffect(() => {
        refreshProjects();
        // Reset selection on portfolio change
        setFilterMode('ALL');
        setSelectedProjectIds([]);
    }, [refreshProjects]);

    const toggleProjectSelection = useCallback((projectId: number) => {
        setSelectedProjectIds(prev => {
            const isSelected = prev.includes(projectId);
            let newSelection: number[];

            if (isSelected) {
                newSelection = prev.filter(id => id !== projectId);
            } else {
                newSelection = [...prev, projectId];
            }
            return newSelection;
        });

        if (projects.length > 0) {
            setFilterMode('SPECIFIC');
        }
    }, [projects.length]);

    const selectAllProjects = useCallback(() => {
        setFilterMode('ALL');
        setSelectedProjectIds([]);
    }, []);

    const clearProjectSelection = useCallback(() => {
        if (projects.length === 0) {
            setFilterMode('ALL');
            return;
        }
        setFilterMode('SPECIFIC');
        setSelectedProjectIds([]);
    }, [projects.length]);

    return (
        <ProjectFilterContext.Provider value={{
            projects,
            isLoading,
            error,
            filterMode,
            selectedProjectIds,
            setFilterMode,
            toggleProjectSelection,
            selectAllProjects,
            clearProjectSelection,
            refreshProjects
        }}>
            {children}
        </ProjectFilterContext.Provider>
    );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useProjectFilter() {
    const context = useContext(ProjectFilterContext);
    if (!context) {
        throw new Error('useProjectFilter must be used within a ProjectFilterProvider');
    }
    return context;
}
