// NOTE: These types are hand-edited to match the backend Pydantic schemas.
// TASK_portfolio_contract_fix adds `code` (required) and the
// PortfolioCreate / PortfolioUpdate shapes. These types should be regenerated
// from backend/openapi.json via `openapi-typescript` as soon as that tooling
// is wired up. See TASK_RESULT_portfolio_contract_fix.md.

export interface Portfolio {
    id: number;
    name: string;
    code: string;
    description?: string;
    logo?: string;
    company_id: number;
    is_active: boolean;
    created_at: string;
    updated_at: string;
}

export interface PortfolioCreate {
    name: string;
    code: string;
    description?: string;
    logo?: string;
}

export interface PortfolioUpdate {
    name?: string;
    is_active?: boolean;
    description?: string;
    logo?: string;
}
