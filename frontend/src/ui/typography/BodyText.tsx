import { Typography, type TypographyProps } from '@mui/material';

type BodyTextProps = Omit<TypographyProps, 'variant'>;

export default function BodyText(props: BodyTextProps) {
    return <Typography variant="body2" {...props} />;
}
