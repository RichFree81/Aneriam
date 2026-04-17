import { Typography, type TypographyProps } from '@mui/material';

type PageTitleProps = Omit<TypographyProps, 'variant'>;

export default function PageTitle(props: PageTitleProps) {
    return <Typography variant="h6" {...props} />;
}
