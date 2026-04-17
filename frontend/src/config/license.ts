import { LicenseInfo } from '@mui/x-license';

/**
 * Configure MUI X Data Grid Pro License
 * 
 * This should be imported at the application root (App.tsx or main.tsx).
 * 
 * Note: A valid license key is required for production use.
 * In development, this may log a watermark warning if the key is missing or invalid.
 */
export const configureDataGridLicense = () => {
    const key = import.meta.env.VITE_MUI_LICENSE_KEY;
    if (key) {
        LicenseInfo.setLicenseKey(key);
    }
};
