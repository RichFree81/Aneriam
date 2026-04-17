import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const SRC_DIR = path.resolve(__dirname, '../src');
const EXCLUDE_FILES = ['palette.ts', 'vite-env.d.ts', 'setupTests.ts'];

// Regex patterns to find violations
const PATTERNS = [
    {
        name: 'Raw Hex Color',
        regex: /#[0-9a-fA-F]{3,8}\b(?!.*url)/g, // Avoids url(#id) but matches colors
        message: 'Use theme.palette instead of raw hex codes.'
    },
    {
        name: 'Raw RGB/RGBA',
        regex: /rgba?\(\d+,\s*\d+,\s*\d+/g,
        message: 'Use theme.palette or alpha() helper.'
    },
    {
        name: 'Custom Box Shadow',
        regex: /boxShadow:\s*['"`]\d+px/g,
        message: 'Use theme.shadows[] or elevation.'
    },
    {
        name: 'Hardcoded Pixel Spacing (margin/padding)',
        regex: /[mp][xytrlb]?:\s*['"]\d+px['"]/g,
        message: 'Use theme.spacing() or plain numbers (which are multiplied by 4px).'
    },
    {
        name: 'Ad-hoc Formatting',
        regex: /\.toLocale(Date|Time)?String\(|\.toLocaleString\(/g,
        message: 'Use utils/format.ts (formatDate, formatCurrency, etc) instead of native toLocaleString.'
    },
    {
        name: 'Banned Chart Library',
        regex: /from\s+['"](chart\.js|react-chartjs-2|胜利|d3)['"]/g,
        message: 'Recharts is the only allowed charting library.'
    }
];

// File-specific import restrictions
const IMPORT_RESTRICTIONS = [
    {
        module: 'recharts',
        allowedPath: 'components/charts', // Normalized relative path segment
        message: 'Recharts components must be wrapped in src/components/charts.'
    },
    {
        module: '@mui/x-data-grid-pro',
        allowedPath: 'components/grid', // Normalized relative path segment
        message: 'DataGridPro must be wrapped in src/components/grid.'
    }
];

function isPathAllowed(relativePath, allowedSegment) {
    const normalized = relativePath.split(path.sep).join('/');
    return normalized.startsWith(allowedSegment) || normalized.includes(`/${allowedSegment}/`);
}

function scanDirectory(dir) {
    let results = [];
    const files = fs.readdirSync(dir);

    for (const file of files) {
        const fullPath = path.join(dir, file);
        const stat = fs.statSync(fullPath);

        if (stat.isDirectory()) {
            results = results.concat(scanDirectory(fullPath));
        } else if (file.endsWith('.ts') || file.endsWith('.tsx')) {
            if (EXCLUDE_FILES.includes(file)) continue;

            const content = fs.readFileSync(fullPath, 'utf-8');
            const lines = content.split('\n');
            const relativePath = path.relative(SRC_DIR, fullPath);

            lines.forEach((line, index) => {
                // Check General Patterns
                PATTERNS.forEach(pattern => {
                    if (pattern.regex.test(line)) {
                        if (!line.trim().startsWith('//') && !line.includes('eslint-disable')) {
                            results.push({
                                file: relativePath,
                                line: index + 1,
                                type: pattern.name,
                                content: line.trim(),
                                message: pattern.message
                            });
                        }
                    }
                });

                // Check Import Restrictions
                IMPORT_RESTRICTIONS.forEach(restriction => {
                    if (line.includes(`from '${restriction.module}'`) || line.includes(`from "${restriction.module}"`)) {
                        if (!isPathAllowed(relativePath, restriction.allowedPath)) {
                            results.push({
                                file: relativePath,
                                line: index + 1,
                                type: 'Restricted Import',
                                content: line.trim(),
                                message: restriction.message
                            });
                        }
                    }
                });
            });
        }
    }
    return results;
}

console.log('Running Standards Verification...');
try {
    const violations = scanDirectory(SRC_DIR);

    if (violations.length > 0) {
        console.log('\n❌ Standards Violations Found:');
        violations.forEach(v => {
            console.log(`  [${v.type}] ${v.file}:${v.line}`);
            console.log(`    Code: ${v.content}`);
            console.log(`    Fix: ${v.message}`);
        });
        console.log(`\nTotal Violations: ${violations.length}`);
        process.exit(1);
    } else {
        console.log('\n✅ No Standards Violations Found.');
    }
} catch (error) {
    console.error('Error running verification:', error);
    process.exit(1);
}
