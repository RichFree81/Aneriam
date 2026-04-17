import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend
} from 'recharts';
import { useChartColors } from '../../config/charts.config';
import { formatDate, formatUnit } from '../../utils/format';
import { BaseChartContainer, type BaseChartContainerProps } from './BaseChartContainer';
import { ChartTooltip } from './ChartTooltip';

export interface TimeSeriesDataPoint {
    date: string | number | Date;
    [key: string]: any;
}

export interface TimeSeriesSeries {
    dataKey: string;
    name: string;
    unit?: string;
    color?: string; // Optional override, defaults to theme
}

interface TimeSeriesChartProps extends Omit<BaseChartContainerProps, 'children'> {
    data: TimeSeriesDataPoint[];
    series: TimeSeriesSeries[];
    xAxisLabel?: string;
    yAxisLabel?: string;
}

export const TimeSeriesChart = ({
    data,
    series,
    xAxisLabel,
    yAxisLabel,
    ...wrapperProps
}: TimeSeriesChartProps) => {
    const colors = useChartColors();

    // Safety: ensure data exists
    if (!data || data.length === 0) {
        return <BaseChartContainer isEmpty {...wrapperProps} children={null} />;
    }

    return (
        <BaseChartContainer {...wrapperProps}>
            <LineChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray={colors.grid.strokeDasharray} stroke={colors.grid.stroke} vertical={false} />
                <XAxis
                    dataKey="date"
                    tickFormatter={(val) => formatDate(val, { dateStyle: 'short' })}
                    stroke={colors.grid.stroke}
                    tick={{ fill: colors.tooltip.color, fontSize: 12 }}
                    label={xAxisLabel ? { value: xAxisLabel, position: 'insideBottom', offset: -5 } : undefined}
                />
                <YAxis
                    stroke={colors.grid.stroke}
                    tick={{ fill: colors.tooltip.color, fontSize: 12 }}
                    tickFormatter={(val) => formatUnit(val, '', 0)} // Default compact number
                    label={yAxisLabel ? { value: yAxisLabel, angle: -90, position: 'insideLeft' } : undefined}
                />
                <Tooltip content={<ChartTooltip />} />
                <Legend wrapperStyle={{ paddingTop: '10px' }} />

                {series.map((s, index) => (
                    <Line
                        key={s.dataKey}
                        type="monotone"
                        dataKey={s.dataKey}
                        name={s.name}
                        stroke={s.color || colors.primary[index % colors.primary.length]}
                        strokeWidth={2}
                        dot={{ r: 3, strokeWidth: 1 }}
                        activeDot={{ r: 6 }}
                    />
                ))}
            </LineChart>
        </BaseChartContainer>
    );
};
