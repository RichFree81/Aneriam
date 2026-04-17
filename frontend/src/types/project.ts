export interface Project {
    id: number;
    portfolio_id: number;
    name: string;
    description?: string;
    is_active: boolean;
    created_at: string;
    updated_at: string;
}
