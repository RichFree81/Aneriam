import {
    PieChart,
    Pie,
    Cell,
    Tooltip,
    Legend
} from 'recharts';
import { useChartColors } from '../../config/charts.config';
import { BaseChartContainer, type BaseChartContainerProps } from './BaseChartContainer';
import { ChartTooltip } from './ChartTooltip';
import { useMemo } from 'react';

interface PieChartDataPoint {
    name: string;
    value: number;
    color?: string; // Explicit override
}

interface DistributionPieChartProps extends Omit<BaseChartContainerProps, 'children'> {
    data: PieChartDataPoint[];
    maxSegments?: number; // Default 6, others grouped
    innerRadius?: number; // For donut
}

export const DistributionPieChart = ({
    data,
    maxSegments = 6,
    innerRadius = 0,
    ...wrapperProps
}: DistributionPieChartProps) => {
    const colors = useChartColors();

    const processedData = useMemo(() => {
        if (!data || data.length === 0) return [];

        // Sort by value desc
        const sorted = [...data].sort((a, b) => b.value - a.value);

        if (sorted.length <= maxSegments) {
            return sorted;
        }

        const top = sorted.slice(0, maxSegments - 1);
        const others = sorted.slice(maxSegments - 1);
        const otherSum = others.reduce((sum, item) => sum + item.value, 0);

        return [
            ...top,
            { name: 'Other', value: otherSum, color: colors.semantic.neutral }
        ];
    }, [data, maxSegments, colors.semantic.neutral]);

    if (!data || data.length === 0) {
        return <BaseChartContainer isEmpty {...wrapperProps} children={null} />;
    }

    return (
        <BaseChartContainer {...wrapperProps}>
            <PieChart margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
                <Pie
                    data={processedData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={innerRadius}
                    outerRadius="80%"
                    paddingAngle={2}
                >
                    {processedData.map((entry, index) => (
                        <Cell
                            key={`cell-${index}`}
                            fill={entry.color || colors.primary[index % colors.primary.length]}
                        />
                    ))}
                </Pie>
                <Tooltip content={<ChartTooltip />} />
                <Legend layout="vertical" align="right" verticalAlign="middle" />
            </PieChart>
        </BaseChartContainer>
    );
};
