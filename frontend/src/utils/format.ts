/**
 * Data Formatting Standards
 * 
 * Policy:
 * - Dates: Default to browser locale. Timezone defaults to local.
 * - Currency: Default currency is 'USD'. Default locale is browser locale.
 * - Numbers: Use Intl.NumberFormat for consistent separator/decimal handling.
 * - Deps: NO external date/formatting libraries (date-fns, moment, etc).
 */

// Default configuration
const DEFAULT_CURRENCY = 'USD';
const DEFAULT_LOCALE = undefined; // defaults to browser locale

/**
 * Formats a date string or Date object.
 * 
 * @param date - The date to format (Date object or ISO string).
 * @param options - Intl.DateTimeFormatOptions. Defaults to medium date/time style.
 * @param locale - BCP 47 language tag. Defaults to browser locale.
 */
export const formatDate = (
    date: Date | string | number,
    options: Intl.DateTimeFormatOptions = { dateStyle: 'medium', timeStyle: 'short' },
    locale: string | undefined = DEFAULT_LOCALE
): string => {
    try {
        const d = new Date(date);
        if (isNaN(d.getTime())) return 'Invalid Date';
        return new Intl.DateTimeFormat(locale, options).format(d);
    } catch (error) {
        console.error('formatDate error', error);
        return String(date);
    }
};

/**
 * Formats a number as currency.
 * 
 * @param amount - The number to format.
 * @param currency - ISO 4217 currency code. Defaults to 'USD'.
 * @param locale - BCP 47 language tag. Defaults to browser locale.
 */
export const formatCurrency = (
    amount: number,
    currency: string = DEFAULT_CURRENCY,
    locale: string | undefined = DEFAULT_LOCALE
): string => {
    if (isNaN(amount)) return 'NaN';
    try {
        return new Intl.NumberFormat(locale, {
            style: 'currency',
            currency,
        }).format(amount);
    } catch (error) {
        console.error('formatCurrency error', error);
        return `${amount} ${currency}`;
    }
};

/**
 * Formats a number as a percentage.
 * 
 * @param value - The value to format (e.g., 0.5 for 50%).
 * @param decimals - Number of decimal places. Defaults to 0.
 * @param locale - BCP 47 language tag. Defaults to browser locale.
 */
export const formatPercent = (
    value: number,
    decimals: number = 0,
    locale: string | undefined = DEFAULT_LOCALE
): string => {
    if (isNaN(value)) return 'NaN';
    try {
        return new Intl.NumberFormat(locale, {
            style: 'percent',
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        }).format(value);
    } catch (error) {
        console.error('formatPercent error', error);
        return `${value}%`;
    }
};

/**
 * Formats a number as a decimal with optional unit.
 * 
 * @param value - The number to format.
 * @param unit - Optional string suffix (e.g., "kg", "m").
 * @param decimals - Max decimal places. Defaults to 2.
 */
export const formatUnit = (
    value: number,
    unit: string = '',
    decimals: number = 2,
    locale: string | undefined = DEFAULT_LOCALE
): string => {
    if (isNaN(value)) return 'NaN';
    try {
        const formatted = new Intl.NumberFormat(locale, {
            maximumFractionDigits: decimals,
        }).format(value);
        return unit ? `${formatted} ${unit}` : formatted;
    } catch (error) {
        console.error('formatUnit error', error);
        return `${value} ${unit}`;
    }
};

/**
 * Truncates an ID or hash string for display.
 * 
 * @param id - The string to truncate.
 * @param length - How many characters to show at start/end. Defaults to 8 (e.g. 1234...5678).
 */
export const truncateId = (id: string, startLength: number = 4, endLength: number = 4): string => {
    if (!id) return '';
    if (id.length <= startLength + endLength) return id;
    return `${id.slice(0, startLength)}...${id.slice(-endLength)}`;
};
