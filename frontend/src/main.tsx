import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import { ThemeProvider, CssBaseline } from '@mui/material'
import theme from './theme/index'
import {
  AuthProvider,
  PortfolioProvider,
  ProjectFilterProvider,
  ActionRegistryProvider,
  NotificationProvider,
} from './context'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AuthProvider>
        <PortfolioProvider>
          <ProjectFilterProvider>
            <ActionRegistryProvider>
              <NotificationProvider>
                <App />
              </NotificationProvider>
            </ActionRegistryProvider>
          </ProjectFilterProvider>
        </PortfolioProvider>
      </AuthProvider>
    </ThemeProvider>
  </React.StrictMode>,
)
