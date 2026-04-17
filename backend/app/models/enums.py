from enum import Enum


class UserRole(str, Enum):
    ADMIN = "Admin"
    COMPANY_ADMIN = "CompanyAdmin"
    USER = "User"


class PortfolioRole(str, Enum):
    PORTFOLIO_ADMIN = "PortfolioAdmin"
    COMMERCIAL_MANAGER = "CommercialManager"
    COST_ENGINEER = "CostEngineer"
    VIEWER = "Viewer"

class WorkflowStatus(str, Enum):
    DRAFT = "Draft"
    SUBMITTED = "Submitted"
    APPROVED = "Approved"
    LOCKED = "Locked"
    CANCELLED = "Cancelled"
