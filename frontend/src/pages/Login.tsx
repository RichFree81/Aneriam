import { useState } from 'react';
import { Box, Button, Card, TextField, Alert, CircularProgress, Typography } from '@mui/material';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { useEffect } from 'react';
import BodyText from '../ui/typography/BodyText';
import PublicLayout from '../layouts/PublicLayout';
import logoImg from '../assets/logo.png';

export default function Login() {
    const { login, isAuthenticated, error: authError, isLoading } = useAuth();
    const navigate = useNavigate();

    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [localError, setLocalError] = useState<string | null>(null);

    useEffect(() => {
        if (isAuthenticated) {
            navigate('/select-portfolio');
        }
    }, [isAuthenticated, navigate]);

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setLocalError(null);

        if (!email || !password) {
            setLocalError("Please enter both email and password.");
            return;
        }

        try {
            await login({ username: email, password });
            // Navigation handled by useEffect
        } catch (err) {
            // Error handling is managed by AuthContext but we can catch here if specific UI logic needed
            console.error("Login failed", err);
        }
    };

    return (
        <PublicLayout>
            <Card sx={{ p: 4, width: '100%', maxWidth: 400, textAlign: 'center', mx: 'auto' }}>
                <Box component="img" src={logoImg} alt="Aneriam Logo" sx={{ width: '80%', maxWidth: 200, mb: 3, mx: 'auto', display: 'block' }} />

                <Typography variant="h5" component="h1" gutterBottom sx={{ fontWeight: 600 }}>
                    Welcome Back
                </Typography>

                <BodyText color="text.secondary" paragraph sx={{ mb: 3 }}>
                    Sign in to continue to Aneriam
                </BodyText>

                <form onSubmit={handleLogin}>
                    <TextField
                        label="Email Address"
                        type="email"
                        fullWidth
                        margin="normal"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        disabled={isLoading}
                        autoFocus
                    />
                    <TextField
                        label="Password"
                        type="password"
                        fullWidth
                        margin="normal"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        disabled={isLoading}
                    />

                    {(authError || localError) && (
                        <Alert severity="error" sx={{ mt: 2, mb: 2, textAlign: 'left' }}>
                            {localError || authError}
                        </Alert>
                    )}

                    <Button
                        type="submit"
                        variant="contained"
                        size="large"
                        fullWidth
                        sx={{ mt: 3, mb: 2 }}
                        disabled={isLoading}
                    >
                        {isLoading ? <CircularProgress size={24} color="inherit" /> : 'Log In'}
                    </Button>
                </form>
            </Card>
        </PublicLayout>
    );
}
