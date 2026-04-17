// @ts-expect-error - TypographyOptions import compatibility
import type { TypographyOptions } from '@mui/material/styles/createTypography';

// PageContainer title uses h4 — uppercase, 30% smaller than MUI default
const typography: TypographyOptions = {
    h4: {
        fontSize: '1.19rem',
    },
};

export default typography;
