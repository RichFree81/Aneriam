import { UserRole } from './enums';

export interface LoginRequest {
    username: string; // email
    password: string;
}

export interface User {
    id: number;
    email: string;
    full_name?: string;
    role: UserRole;
    is_active: boolean;
    company_id?: number;
    company_name?: string;
}

export interface LoginResponse {
    access_token: string;
    refresh_token: string;
    token_type: string;
    user: User;
}
