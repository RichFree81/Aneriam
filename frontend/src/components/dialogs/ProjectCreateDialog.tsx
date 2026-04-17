
import { useState } from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    Button,
    Alert,
    CircularProgress
} from '@mui/material';
import { usePortfolio } from '../../context/PortfolioContext';
import { useProjectFilter } from '../../context/ProjectFilterContext';
import { createProject } from '../../api/projects';

interface ProjectCreateDialogProps {
    open: boolean;
    onClose: () => void;
}

export default function ProjectCreateDialog({ open, onClose }: ProjectCreateDialogProps) {
    const { activePortfolio } = usePortfolio();
    const { refreshProjects } = useProjectFilter();

    const [name, setName] = useState('');
    const [description, setDescription] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!activePortfolio) return;

        setIsLoading(true);
        setError(null);

        try {
            await createProject(activePortfolio.id, {
                name,
                description,
                is_active: true
            });
            await refreshProjects(); // specific function to reload project list
            handleClose();
        } catch (err) {
            console.error('Failed to create project', err);
            setError('Failed to create project. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    const handleClose = () => {
        setName('');
        setDescription('');
        setError(null);
        onClose();
    };

    return (
        <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
            <form onSubmit={handleSubmit}>
                <DialogTitle>Create New Project</DialogTitle>
                <DialogContent>
                    {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

                    <TextField
                        autoFocus
                        margin="dense"
                        label="Project Name"
                        fullWidth
                        required
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        disabled={isLoading}
                    />
                    <TextField
                        margin="dense"
                        label="Description"
                        fullWidth
                        multiline
                        rows={3}
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        disabled={isLoading}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleClose} disabled={isLoading}>Cancel</Button>
                    <Button type="submit" variant="contained" disabled={isLoading || !name.trim()}>
                        {isLoading ? <CircularProgress size={24} /> : 'Create'}
                    </Button>
                </DialogActions>
            </form>
        </Dialog>
    );
}
