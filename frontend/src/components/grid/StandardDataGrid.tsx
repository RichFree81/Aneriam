
import {
    DataGridPro,
    GridToolbar,
} from '@mui/x-data-grid-pro';
import type { DataGridProProps } from '@mui/x-data-grid-pro';
import { Box, styled } from '@mui/material';
import { useMemo } from 'react';

// STYLING
const StyledGridWrapper = styled(Box)(({ theme }) => ({
    height: '100%',
    width: '100%',
    '& .MuiDataGrid-root': {
        border: `1px solid ${theme.palette.divider} `,
        borderRadius: theme.shape.borderRadius,
        // Header styling
        '& .MuiDataGrid-columnHeaders': {
            backgroundColor: theme.palette.background.default,
            color: theme.palette.text.secondary,
            fontSize: '0.75rem',
            textTransform: 'uppercase',
            fontWeight: 600,
        },
        // Cell styling
        '& .MuiDataGrid-cell': {
            borderBottom: `1px solid ${theme.palette.divider} `,
        },
        // Pinned columns separator
        '& .MuiDataGrid-pinnedColumns--left, & .MuiDataGrid-pinnedColumns--right': {
            boxShadow: theme.shadows[2],
            zIndex: 3, // Ensure above other cells
        }
    },
}));

export interface StandardDataGridProps extends Omit<DataGridProProps, 'density' | 'autoHeight'> {
    /**
     * If true, enables the toolbar with Filter, Columns, and Export.
     * Export excludes columns marked with `disableExport: true`.
     */
    enableToolbar?: boolean;
    /**
     * If true, enables checkbox selection.
     * When > 0 items selected, the Bulk Actions Toolbar (not implemented here) would activate.
     * Enforces left-pinning of the checkbox column.
     */
    enableSelection?: boolean;
}

/**
 * Standard Data Grid
 * 
 * Enforceable Standards:
 * - Density: 'standard' (fixed)
 * - AutoHeight: true (fits container, but handles internal scroll) - WAIT, DataGridPro usually wants explicit height.
 *   Let's check standards. G-30 says "Virtualization MUST be enabled". autoHeight kills virtualization.
 *   So we MUST NOT use autoHeight for large datasets.
 *   
 *   Standard says: "Virtualization MUST be enabled for datasets >= 500 rows".
 *   Construction: We will default to filling the parent container (height: 100%) rather than autoHeight.
 * 
 * - Pagination: server-side by default encouraged, or client side.
 * - Selection: disableSelectionOnClick: true.
 */
export const StandardDataGrid = ({
    enableToolbar = true,
    enableSelection = false,
    initialState,
    slots,
    slotProps,
    ...props
}: StandardDataGridProps) => {

    const defaultInitialState = useMemo(() => {
        const base = initialState || {};
        return {
            ...base,
            pinnedColumns: {
                left: enableSelection ? ['__check__'] : [], // Checkbox left
                right: ['actions'], // Actions right (if exists, heuristic)
                ...base.pinnedColumns,
            },
        };
    }, [initialState, enableSelection]);

    return (
        <StyledGridWrapper>
            <DataGridPro
                {...props}
                // LOCKED PROPS
                density="standard"
                disableRowSelectionOnClick
                checkboxSelection={enableSelection}
                pagination
                pageSizeOptions={[10, 25, 50, 100]}
                // Virtualization defaults (enabled by default in Pro)
                initialState={defaultInitialState}
                slots={{
                    toolbar: enableToolbar ? GridToolbar : undefined,
                    ...slots,
                }}
                slotProps={{
                    ...slotProps,
                    toolbar: {
                        showQuickFilter: true, // User friendly
                        printOptions: { disableToolbarButton: true }, // Usually not needed
                        csvOptions: { allColumns: false }, // Respect disableExport
                        ...slotProps?.toolbar,
                    }
                }}
                sx={{
                    // Fallback height if wrapper doesn't provide it, though styled wrapper does 100%
                    minHeight: 400,
                    ...props.sx
                }}
            />
        </StyledGridWrapper>
    );
};
