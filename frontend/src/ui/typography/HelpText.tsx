import { Typography, type TypographyProps } from '@mui/material';

type HelpTextProps = Omit<TypographyProps, 'variant'>;

export default function HelpText(props: HelpTextProps) {
    return <Typography variant="caption" {...props} />;
}
