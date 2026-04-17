import { useState, useMemo } from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    List,
    ListItem,
    ListItemButton,
    ListItemIcon,
    ListItemText,
    Checkbox,
    TextField,
    Box,
    Typography,
    InputAdornment,
    Chip
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import { useProjectFilter } from '../../context/ProjectFilterContext';

interface ProjectSelectionDialogProps {
    open: boolean;
    onClose: () => void;
}

export default function ProjectSelectionDialog({ open, onClose }: ProjectSelectionDialogProps) {
    const {
        projects,
        selectedProjectIds,
        toggleProjectSelection,
        selectAllProjects,
        clearProjectSelection,
        filterMode
    } = useProjectFilter();

    const [searchTerm, setSearchTerm] = useState('');

    const filteredProjects = useMemo(() => {
        return projects.filter(p => p.name.toLowerCase().includes(searchTerm.toLowerCase()));
    }, [projects, searchTerm]);

    const isAllSelected = filterMode === 'ALL';
    const selectedCount = isAllSelected ? projects.length : selectedProjectIds.length;

    const handleToggle = (id: number) => {
        toggleProjectSelection(id);
    };

    return (
        <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
            <DialogTitle>
                Select Projects
            </DialogTitle>
            <DialogContent dividers sx={{ p: 0 }}>
                {/* Search Bar */}
                <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
                    <TextField
                        fullWidth
                        size="small"
                        placeholder="Search projects..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        InputProps={{
                            startAdornment: (
                                <InputAdornment position="start">
                                    <SearchIcon color="action" />
                                </InputAdornment>
                            ),
                        }}
                    />
                </Box>

                {/* Quick Actions */}
                <Box sx={{ px: 2, py: 1, display: 'flex', gap: 1, alignItems: 'center', bgcolor: 'background.default' }}>
                    <Chip
                        label="Select All"
                        onClick={selectAllProjects}
                        color={isAllSelected ? "primary" : "default"}
                        variant={isAllSelected ? "filled" : "outlined"}
                        size="small"
                    />
                    <Chip
                        label="Clear Selection"
                        onClick={clearProjectSelection}
                        variant="outlined"
                        size="small"
                    />
                    <Box sx={{ flexGrow: 1 }} />
                    <Typography variant="caption" color="text.secondary">
                        {selectedCount} selected
                    </Typography>
                </Box>

                {/* Project List */}
                <List sx={{ maxHeight: 400, overflow: 'auto' }}>
                    {filteredProjects.length === 0 ? (
                        <ListItem>
                            <ListItemText primary="No projects found" sx={{ textAlign: 'center', color: 'text.secondary' }} />
                        </ListItem>
                    ) : (
                        filteredProjects.map((project) => {
                            const isSelected = isAllSelected || selectedProjectIds.includes(project.id);
                            return (
                                <ListItem
                                    key={project.id}
                                    disablePadding
                                >
                                    <ListItemButton onClick={() => handleToggle(project.id)} dense>
                                        <ListItemIcon>
                                            <Checkbox
                                                edge="start"
                                                checked={isSelected}
                                                tabIndex={-1}
                                                disableRipple
                                            />
                                        </ListItemIcon>
                                        <ListItemText primary={project.name} secondary={project.description} />
                                    </ListItemButton>
                                </ListItem>
                            );
                        })
                    )}
                </List>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Close</Button>
            </DialogActions>
        </Dialog>
    );
}
