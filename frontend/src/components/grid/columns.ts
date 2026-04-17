import type { GridColDef } from '@mui/x-data-grid-pro';
import {
    formatDate,
    formatCurrency,
    formatUnit,
    formatPercent,
    truncateId
} from '../../utils/format';

// Re-export type for consumers
export type ColumnDef = GridColDef;

/**
 * Creates a standard text column.
 * Left-aligned.
 */
export const createStringColumn = (
    field: string,
    headerName: string,
    flex: number = 1,
    options?: Partial<GridColDef>
): GridColDef => ({
    field,
    headerName,
    flex,
    align: 'left',
    headerAlign: 'left',
    minWidth: 100,
    ...options
});

/**
 * Creates an ID column.
 * Left-aligned, monospace, truncated.
 */
export const createIdColumn = (
    field: string = 'id',
    headerName: string = 'ID',
    options?: Partial<GridColDef>
): GridColDef => ({
    field,
    headerName,
    width: 120,
    align: 'left',
    headerAlign: 'left',
    valueFormatter: (value: string) => truncateId(value),
    ...options
});

/**
 * Creates a numeric column.
 * Right-aligned.
 */
export const createNumberColumn = (
    field: string,
    headerName: string,
    unit: string = '',
    flex: number = 1,
    options?: Partial<GridColDef>
): GridColDef => ({
    field,
    headerName,
    flex,
    align: 'right',
    headerAlign: 'right',
    valueFormatter: (value: number) => formatUnit(value, unit),
    ...options
});

/**
 * Creates a currency column.
 * Right-aligned.
 */
export const createCurrencyColumn = (
    field: string,
    headerName: string,
    currencyCode: string = 'USD',
    flex: number = 1,
    options?: Partial<GridColDef>
): GridColDef => ({
    field,
    headerName,
    flex,
    align: 'right',
    headerAlign: 'right',
    valueFormatter: (value: number) => formatCurrency(value, currencyCode),
    ...options
});

/**
 * Creates a percentage column.
 * Right-aligned.
 */
export const createPercentColumn = (
    field: string,
    headerName: string,
    flex: number = 1,
    options?: Partial<GridColDef>
): GridColDef => ({
    field,
    headerName,
    flex,
    align: 'right',
    headerAlign: 'right',
    valueFormatter: (value: number) => formatPercent(value),
    ...options
});

/**
 * Creates a date column.
 * Left-aligned.
 */
export const createDateColumn = (
    field: string,
    headerName: string,
    flex: number = 1,
    options?: Partial<GridColDef>
): GridColDef => ({
    field,
    headerName,
    flex,
    align: 'left',
    headerAlign: 'left',
    valueFormatter: (value: string | Date) => formatDate(value),
    ...options
});

/**
 * Creates an actions column.
 * Right-pinned (enforced by Grid config), fixed width, not sortable/filterable.
 */
export const createActionColumn = (
    renderCell: GridColDef['renderCell'],
    width: number = 100
): GridColDef => ({
    field: 'actions',
    type: 'actions',
    headerName: 'Actions',
    width,
    sortable: false,
    filterable: false,
    disableExport: true, // Rule G-35
    renderCell,
    align: 'center',
    headerAlign: 'center',
});
