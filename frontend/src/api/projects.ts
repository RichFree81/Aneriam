import { authenticatedFetch } from './client';
import type { Project } from '../types/project';

export async function getProjects(portfolioId: number): Promise<Project[]> {
    const response = await authenticatedFetch(`/projects/portfolios/${portfolioId}/projects`);
    return response.json();
}

export async function createProject(portfolioId: number, data: Partial<Project>): Promise<Project> {
    const response = await authenticatedFetch(`/projects/portfolios/${portfolioId}/projects`, {
        method: 'POST',
        body: JSON.stringify(data),
    });
    return response.json();
}
