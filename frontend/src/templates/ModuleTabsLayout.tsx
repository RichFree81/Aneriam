/**
 * ModuleTabsLayout — Standard template for module pages (Projects, Portfolios, Reports).
 *
 * Uses Toolpad `PageContainer` for the page frame (gray background, h4 title auto-rendered).
 * Tabs sit on the gray background with a full-width divider via negative-margin pattern.
 * Content area is white (`background.paper`), edge-to-edge below the tabs.
 *
 * @see page-layout-standard.md — Dual Layout Strategy
 *
 * NOT for settings pages. Settings pages use `PageLayout` with `type="utility"`.
 */
import { useState } from 'react';
import type { ReactNode } from 'react';
import { Box, Tabs, Tab } from '@mui/material';
import { PageContainer } from '@toolpad/core/PageContainer';

export interface TabDefinition {
    label: string;
    content: ReactNode;
}

interface ModuleTabsLayoutProps {
    title?: string;
    tabs: TabDefinition[];
    breadcrumbs?: any[];
}

export default function ModuleTabsLayout({ title = "Home", tabs, breadcrumbs = [] }: ModuleTabsLayoutProps) {
    const [tabIndex, setTabIndex] = useState(0);

    return (
        <PageContainer title={title} breadcrumbs={breadcrumbs} maxWidth={false}>
            {/* Tab bar — sits on the gray page background */}
            <Tabs
                value={tabIndex}
                onChange={(_e, v) => setTabIndex(v)}
                sx={{ borderBottom: 1, borderColor: 'divider', mx: -3, px: 3, mt: -1.5 }}
            >
                {tabs.map((tab, index) => (
                    <Tab key={index} label={tab.label} />
                ))}
            </Tabs>

            {/* Content area — white background, edge-to-edge below tabs */}
            <Box sx={{ bgcolor: 'background.paper', mx: -3, px: 3, py: 3, flexGrow: 1 }}>
                {tabs[tabIndex]?.content}
            </Box>
        </PageContainer>
    );
}
