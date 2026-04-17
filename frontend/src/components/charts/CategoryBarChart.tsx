import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend
} from 'recharts';
import { useChartColors } from '../../config/charts.config';
import { formatUnit } from '../../utils/format';
import { BaseChartContainer, type BaseChartContainerProps } from './BaseChartContainer';
import { ChartTooltip } from './ChartTooltip';

export interface BarChartSeries {
    dataKey: string;
    name: string;
    stackId?: string; // If present, stacks bars
    color?: string;
}

interface CategoryBarChartProps extends Omit<BaseChartContainerProps, 'children'> {
    data: any[];
    categoryKey: string; // The field to group by (x-axis)
    series: BarChartSeries[];
    layout?: 'vertical' | 'horizontal';
}

export const CategoryBarChart = ({
    data,
    categoryKey,
    series,
    layout = 'horizontal',
    ...wrapperProps
}: CategoryBarChartProps) => {
    const colors = useChartColors();

    if (!data || data.length === 0) {
        return <BaseChartContainer isEmpty {...wrapperProps} children={null} />;
    }

    const isVertical = layout === 'vertical';

    return (
        <BaseChartContainer {...wrapperProps}>
            <BarChart
                data={data}
                layout={layout}
                margin={{ top: 10, right: 30, left: 20, bottom: 5 }}
            >
                <CartesianGrid strokeDasharray={colors.grid.strokeDasharray} stroke={colors.grid.stroke} vertical={!isVertical} horizontal={isVertical} />

                {isVertical ? (
                    <>
                        {/* Vertical: X is Number, Y is Category */}
                        <XAxis type="number" stroke={colors.grid.stroke} tickFormatter={(val) => formatUnit(val, '', 0)} />
                        <YAxis dataKey={categoryKey} type="category" stroke={colors.grid.stroke} width={100} />
                    </>
                ) : (
                    <>
                        {/* Horizontal: X is Category, Y is Number */}
                        <XAxis dataKey={categoryKey} stroke={colors.grid.stroke} />
                        <YAxis stroke={colors.grid.stroke} tickFormatter={(val) => formatUnit(val, '', 0)} />
                    </>
                )}

                <Tooltip content={<ChartTooltip />} />
                <Legend wrapperStyle={{ paddingTop: '10px' }} />

                {series.map((s, index) => (
                    <Bar
                        key={s.dataKey}
                        dataKey={s.dataKey}
                        name={s.name}
                        stackId={s.stackId}
                        fill={s.color || colors.primary[index % colors.primary.length]}
                        radius={s.stackId ? [0, 0, 0, 0] : [4, 4, 0, 0]}
                    />
                ))}
            </BarChart>
        </BaseChartContainer>
    );
};
