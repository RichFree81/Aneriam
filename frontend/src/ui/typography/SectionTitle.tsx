import { Typography, type TypographyProps } from '@mui/material';

type SectionTitleProps = Omit<TypographyProps, 'variant'>;

export default function SectionTitle(props: SectionTitleProps) {
    return <Typography variant="subtitle1" {...props} />;
}
