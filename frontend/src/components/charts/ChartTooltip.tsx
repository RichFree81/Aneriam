import { Paper, Typography, Box, styled } from '@mui/material';
import type { TooltipProps } from 'recharts';
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent';
import { useChartColors } from '../../config/charts.config';

const TooltipPaper = styled(Paper)(({ theme }) => ({
    padding: theme.spacing(1.5),
    backgroundColor: theme.palette.background.paper,
    boxShadow: theme.shadows[4],
    border: `1px solid ${theme.palette.divider}`,
}));

const TooltipRow = styled(Box)({
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
    '&:last-child': {
        marginBottom: 0
    }
});

const ColorIndicator = styled(Box)<{ color: string }>(({ color }) => ({
    width: 10,
    height: 10,
    borderRadius: '50%',
    backgroundColor: color,
}));

// Re-export type for specific charts
export type CustomTooltipProps = TooltipProps<ValueType, NameType> & {
    payload?: any[];
    label?: string;
    active?: boolean;
};

export const ChartTooltip = ({ active, payload, label }: CustomTooltipProps) => {
    const colors = useChartColors(); // Access generic config if needed, but payload has color

    if (active && payload && payload.length) {
        return (
            <TooltipPaper>
                {label && (
                    <Typography variant="subtitle2" sx={{ mb: 1, borderBottom: 1, borderColor: 'divider' }}>
                        {label}
                    </Typography>
                )}
                {payload.map((item, index) => (
                    <TooltipRow key={index}>
                        <ColorIndicator color={item.color || colors.primary[index % colors.primary.length]} />
                        <Typography variant="body2" color="text.secondary">
                            {item.name}:
                        </Typography>
                        <Typography variant="body2" fontWeight={600}>
                            {/* Value is already formatted by the chart axis/formatter before reaching here? 
                                Actually Recharts passed the 'formatter' output to 'value' if set, 
                                but raw value if not. We should rely on the Chart passing formatted prop, 
                                OR we trust the 'formatter' function passed to the Series.
                                
                                Recharts payload item has `value` and `payload`.
                                If the Series used `formatter`, item.value might be string or number.
                                We will render it as is, assuming Series did the job.
                             */}
                            {item.value}
                        </Typography>
                    </TooltipRow>
                ))}
            </TooltipPaper>
        );
    }

    return null;
};
