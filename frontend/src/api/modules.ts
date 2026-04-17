import type { Module } from '../types/module';
import { authenticatedFetch } from './client';

export async function getModules(): Promise<Module[]> {
    // Token arg is kept for compatibility but authenticatedFetch uses localStorage
    const response = await authenticatedFetch('/modules');
    return response.json();
}
