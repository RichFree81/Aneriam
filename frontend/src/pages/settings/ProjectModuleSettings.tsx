import { useState } from 'react';
import { Typography, Grid, TextField, MenuItem } from '@mui/material';
import PageLayout from '../../components/layout/PageLayout';
import SettingsSection from '../../components/common/SettingsSection';
import TabPanel from '../../components/common/TabPanel';

export default function ProjectModuleSettings() {
    const [value, setValue] = useState(0);

    // Section Edit States
    const [editIdentity, setEditIdentity] = useState(false);
    const [editGovernance, setEditGovernance] = useState(false);

    const handleChange = (_event: React.SyntheticEvent, newValue: number) => {
        setValue(newValue);
    };

    return (
        <PageLayout
            title="Project Settings"
            type="utility"
            tabs={{
                value,
                onChange: handleChange,
                items: [
                    { label: 'General' },
                    { label: 'Fields' },
                    { label: 'Input Forms' }
                ]
            }}
        >
            {/* General Tab */}
            <TabPanel idPrefix="project" value={value} index={0}>
                {/* 
                   Strict Spacing: 
                   - PageLayout gives 16px outer padding.
                   - Grid container spacing={2} gives 16px gaps between items.
                   - Maximum width 'md' to prevent lines from becoming unreadably long.
                */}
                <Grid container spacing={2}>


                    {/* Section: Module Identity */}
                    <Grid size={{ xs: 12 }}>
                        <SettingsSection
                            title="Module Identity"
                            isEditing={editIdentity}
                            onEdit={() => setEditIdentity(true)}
                            onSave={() => setEditIdentity(false)}
                            onCancel={() => setEditIdentity(false)}
                        >
                            <Grid container spacing={2}>
                                <Grid size={{ xs: 12, sm: 6 }}>
                                    <TextField
                                        fullWidth
                                        label="Module Name (Singular)"
                                        defaultValue="Project"
                                        sx={{ bgcolor: editIdentity ? 'background.paper' : 'transparent' }}
                                        inputProps={{ readOnly: !editIdentity }}
                                    />
                                </Grid>
                                <Grid size={{ xs: 12, sm: 6 }}>
                                    <TextField
                                        fullWidth
                                        label="Module Name (Plural)"
                                        defaultValue="Projects"
                                        sx={{ bgcolor: editIdentity ? 'background.paper' : 'transparent' }}
                                        inputProps={{ readOnly: !editIdentity }}
                                    />
                                </Grid>
                                <Grid size={{ xs: 12 }}>
                                    <TextField
                                        fullWidth
                                        multiline
                                        rows={3}
                                        label="Module Description"
                                        defaultValue="Manage your organization's projects, engagements, and jobs."
                                        sx={{ bgcolor: editIdentity ? 'background.paper' : 'transparent' }}
                                        inputProps={{ readOnly: !editIdentity }}
                                    />
                                </Grid>
                            </Grid>
                        </SettingsSection>
                    </Grid>

                    {/* Section: Numbering & Governance */}
                    <Grid size={{ xs: 12 }}>
                        <SettingsSection
                            title="Governance & Defaults"
                            isEditing={editGovernance}
                            onEdit={() => setEditGovernance(true)}
                            onSave={() => setEditGovernance(false)}
                            onCancel={() => setEditGovernance(false)}
                        >
                            <Grid container spacing={2}>
                                <Grid size={{ xs: 12, sm: 6 }}>
                                    <TextField
                                        fullWidth
                                        label="Project ID Prefix"
                                        defaultValue="PRJ-"
                                        sx={{ bgcolor: editGovernance ? 'background.paper' : 'transparent' }}
                                        inputProps={{ readOnly: !editGovernance }}
                                    />
                                </Grid>
                                <Grid size={{ xs: 12, sm: 6 }}>
                                    <TextField
                                        select
                                        fullWidth
                                        label="Default Status"
                                        defaultValue="draft"
                                        sx={{ bgcolor: editGovernance ? 'background.paper' : 'transparent' }}
                                        inputProps={{ readOnly: !editGovernance }}
                                    >
                                        <MenuItem value="draft">Draft</MenuItem>
                                        <MenuItem value="planning">Planning</MenuItem>
                                        <MenuItem value="active">Active</MenuItem>
                                    </TextField>
                                </Grid>
                            </Grid>
                        </SettingsSection>
                    </Grid>

                </Grid>
            </TabPanel>

            {/* Fields Tab */}
            <TabPanel idPrefix="project" value={value} index={1}>
                <Typography variant="body2" color="text.secondary">
                    {/* Fields Content to be rebuilt */}
                </Typography>
            </TabPanel>

            {/* Forms Tab */}
            <TabPanel idPrefix="project" value={value} index={2}>
                <Typography variant="body2" color="text.secondary">
                    {/* Forms Content to be rebuilt */}
                </Typography>
            </TabPanel>
        </PageLayout>
    );
}
