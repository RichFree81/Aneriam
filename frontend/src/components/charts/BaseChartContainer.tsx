import { ResponsiveContainer } from 'recharts';
import { Box, styled } from '@mui/material';
import LoadingState from '../../ui/feedback/LoadingState';
import EmptyState from '../../ui/feedback/EmptyState';
import ErrorState from '../../ui/feedback/ErrorState';

const ChartWrapper = styled(Box)(({ theme }) => ({
    width: '100%',
    height: '100%',
    position: 'relative',
    minHeight: 300,
    '& .recharts-cartesian-grid-horizontal line, & .recharts-cartesian-grid-vertical line': {
        stroke: theme.palette.divider,
    },
    '& .recharts-text': {
        fill: theme.palette.text.secondary,
        fontSize: '0.75rem',
    }
}));

const Overlay = styled(Box)(() => ({
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.8)', // slight fade
    zIndex: 1,
}));

export interface BaseChartContainerProps {
    loading?: boolean;
    error?: string;
    isEmpty?: boolean;
    height?: number | string;
    children: React.ReactNode;
    emptyMessage?: string;
    onRetry?: () => void;
}

export const BaseChartContainer = ({
    loading = false,
    error,
    isEmpty = false,
    height = 300,
    children,
    emptyMessage = 'No data available to display',
    onRetry,
}: BaseChartContainerProps) => {

    if (error) {
        return (
            <Box height={height} width="100%">
                <ErrorState
                    title="Could not load chart"
                    message={error}
                    onRetry={onRetry}
                />
            </Box>
        );
    }

    if (isEmpty && !loading) {
        return (
            <Box height={height} width="100%">
                <EmptyState
                    title="No Data"
                    message={emptyMessage}
                />
            </Box>
        );
    }

    return (
        <ChartWrapper sx={{ height }}>
            {loading && (
                <Overlay>
                    <LoadingState message="Loading chart data..." />
                </Overlay>
            )}
            <ResponsiveContainer width="100%" height="100%">
                {children}
            </ResponsiveContainer>
        </ChartWrapper>
    );
};
