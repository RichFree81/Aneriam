import { Typography, Grid, Card, CardActionArea, CardContent, Avatar } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import FolderSpecialIcon from '@mui/icons-material/FolderSpecial';
import PageLayout from '../../components/layout/PageLayout';

export default function ModuleSettings() {
    const navigate = useNavigate();

    const modules = [
        {
            id: 'portfolios',
            name: 'Portfolios',
            path: '/settings/modules/portfolios',
            icon: <FolderSpecialIcon fontSize="large" />,
            color: 'success.main', // Use theme token
        },
        {
            id: 'projects',
            name: 'Projects',
            path: '/settings/modules/projects',
            icon: <AccountTreeIcon fontSize="large" />,
            color: 'primary.main', // Use theme token, not hex
        },
    ].sort((a, b) => a.name.localeCompare(b.name));

    return (
        <PageLayout title="Module Configuration" type="utility">
            {/* 
                Strict Spacing Implementation:
                - PageLayout provides outer padding (16px).
                - Grid spacing={2} ensures 16px gap between cards.
                - No extra margins/paddings on container.
            */}
            <Grid container spacing={2}>
                {modules.map((mod) => (
                    <Grid size={{ xs: 12, sm: 6, md: 4, lg: 3 }} key={mod.id}>
                        <Card variant="outlined" sx={{ height: '100%' }}>
                            <CardActionArea
                                onClick={() => navigate(mod.path)}
                                sx={{
                                    height: '100%',
                                    p: 3, // Internal card padding (24px) for breathing room
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    textAlign: 'center'
                                }}
                            >
                                <Avatar
                                    sx={{
                                        bgcolor: mod.color,
                                        width: 64,
                                        height: 64,
                                        mb: 2
                                    }}
                                >
                                    {mod.icon}
                                </Avatar>
                                <CardContent sx={{ p: 0 }}>
                                    <Typography variant="h6" component="div" gutterBottom>
                                        {mod.name}
                                    </Typography>
                                </CardContent>
                            </CardActionArea>
                        </Card>
                    </Grid>
                ))}
            </Grid>
        </PageLayout>
    );
}
