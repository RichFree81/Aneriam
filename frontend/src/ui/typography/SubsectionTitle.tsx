import { Typography, type TypographyProps } from '@mui/material';

type SubsectionTitleProps = Omit<TypographyProps, 'variant'>;

export default function SubsectionTitle(props: SubsectionTitleProps) {
    return <Typography variant="subtitle2" {...props} />;
}
