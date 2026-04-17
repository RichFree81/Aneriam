/**
 * Shared Enums
 * 
 * MIRRORS BACKEND: app/models/enums.py
 * 
 * These enums must match exactly the string values returned by the backend.
 */

export const UserRole = {
    ADMIN: "Admin",
    COMPANY_ADMIN: "CompanyAdmin",
    USER: "User",
} as const;
export type UserRole = typeof UserRole[keyof typeof UserRole];

export const PortfolioRole = {
    PORTFOLIO_ADMIN: "PortfolioAdmin",
    COMMERCIAL_MANAGER: "CommercialManager",
    COST_ENGINEER: "CostEngineer",
    VIEWER: "Viewer",
} as const;
export type PortfolioRole = typeof PortfolioRole[keyof typeof PortfolioRole];

export const WorkflowStatus = {
    DRAFT: "Draft",
    SUBMITTED: "Submitted",
    APPROVED: "Approved",
    LOCKED: "Locked",
    CANCELLED: "Cancelled",
} as const;
export type WorkflowStatus = typeof WorkflowStatus[keyof typeof WorkflowStatus];
