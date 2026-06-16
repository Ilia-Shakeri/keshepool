import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

// Utility to merge tailwind classes
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Converts any standard number or string digit to its Persian equivalent
export function toPersianDigits(num: number | string): string {
  if (num === null || num === undefined) return '';
  const persianDigits = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
  return num.toString().replace(/\d/g, (x) => persianDigits[parseInt(x)]);
}

// Formats numeric values to standard currency format with Persian numerals
export function formatPrice(num: number | string): string {
  if (num === null || num === undefined) return toPersianDigits('0');
  const numStr = typeof num === 'number' ? num.toLocaleString('en-US') : num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return toPersianDigits(numStr);
}