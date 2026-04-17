import type { Portfolio, PortfolioCreate, PortfolioUpdate } from '../types/portfolio';
import { authenticatedFetch } from './client';

// NOTE: Request/response shapes are hand-typed to mirror the backend Pydantic
// schemas (PortfolioCreate / PortfolioUpdate / Portfolio response). These should
// be replaced by types generated from `openapi-typescript` once that tooling is
// wired up. See TASK_RESULT_portfolio_contract_fix.md.

export async function getPortfolios(): Promise<Portfolio[]> {
    const response = await authenticatedFetch('/portfolios');
    return response.json();
}

export async function getPortfolio(id: number): Promise<Portfolio> {
    const response = await authenticatedFetch(`/portfolios/${id}`);
    return response.json();
}

export async function createPortfolio(body: PortfolioCreate): Promise<Portfolio> {
    const response = await authenticatedFetch('/portfolios', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    return response.json();
}

export async function updatePortfolio(id: number, body: PortfolioUpdate): Promise<Portfolio> {
    const response = await authenticatedFetch(`/portfolios/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    return response.json();
}

export async function deletePortfolio(id: number): Promise<void> {
    await authenticatedFetch(`/portfolios/${id}`, { method: 'DELETE' });
}
