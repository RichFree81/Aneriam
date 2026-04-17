import { Card, CardContent, Typography, Box } from '@mui/material';
import { TrendingUp, TrendingDown, TrendingFlat } from '@mui/icons-material';
import { formatCurrency, formatPercent, formatUnit } from '../../utils/format';

export type KpiTrendDirection = 'up' | 'down' | 'neutral';
export type KpiTrendIntent = 'positive' | 'negative' | 'neutral';

export interface KpiTrend {
    value: number; // The textual value (e.g. 12%)
    direction: KpiTrendDirection;
    intent: KpiTrendIntent; // Meaning: Good, Bad, Neutral
    label?: string; // e.g. "vs last month"
}

export interface KpiCardProps {
    title: string;
    value: number;
    format?: 'currency' | 'percent' | 'number';
    /** Optional currency code if format='currency' */
    currencyCode?: string;
    /** Optional unit if format='number' */
    unit?: string;
    trend?: KpiTrend;
    actions?: React.ReactNode;
}

const getTrendColor = (intent: KpiTrendIntent) => {
    switch (intent) {
        case 'positive': return 'success.main';
        case 'negative': return 'error.main';
        default: return 'text.secondary';
    }
};

const getTrendIcon = (direction: KpiTrendDirection) => {
    switch (direction) {
        case 'up': return <TrendingUp fontSize="small" />;
        case 'down': return <TrendingDown fontSize="small" />;
        default: return <TrendingFlat fontSize="small" />;
    }
};

export const KpiCard = ({
    title,
    value,
    format = 'number',
    currencyCode,
    unit,
    trend,
    actions
}: KpiCardProps) => {

    const formattedValue = () => {
        switch (format) {
            case 'currency': return formatCurrency(value, currencyCode);
            case 'percent': return formatPercent(value, 1); // 1 decimal for KPI usually good
            default: return formatUnit(value, unit);
        }
    };

    return (
        <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                        {title}
                    </Typography>
                    {actions && <Box>{actions}</Box>}
                </Box>

                <Typography variant="h4" component="div" sx={{ fontWeight: 600, my: 1 }}>
                    {formattedValue()}
                </Typography>

                {trend && (
                    <Box display="flex" alignItems="center" gap={1}>
                        <Box display="flex" alignItems="center" color={getTrendColor(trend.intent)}>
                            {getTrendIcon(trend.direction)}
                            <Typography variant="body2" fontWeight="bold" ml={0.5} color="inherit">
                                {formatPercent(Math.abs(trend.value))}
                            </Typography>
                        </Box>
                        {trend.label && (
                            <Typography variant="caption" color="text.secondary">
                                {trend.label}
                            </Typography>
                        )}
                    </Box>
                )}
            </CardContent>
        </Card>
    );
};
