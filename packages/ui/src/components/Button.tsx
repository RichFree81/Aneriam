"use client";

import clsx from "clsx";
import type { ButtonHTMLAttributes, DetailedHTMLProps, ReactNode } from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost";

export interface ButtonProps
  extends DetailedHTMLProps<ButtonHTMLAttributes<HTMLButtonElement>, HTMLButtonElement> {
  readonly variant?: ButtonVariant;
  readonly leadingIcon?: ReactNode;
  readonly trailingIcon?: ReactNode;
}

const baseStyles =
  "inline-flex items-center justify-center gap-2 rounded-md font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed";

const variantStyles: Record<ButtonVariant, string> = {
  primary: "bg-slate-900 text-white hover:bg-slate-800 focus-visible:ring-slate-500",
  secondary:
    "bg-slate-100 text-slate-900 hover:bg-slate-200 focus-visible:ring-slate-400 dark:bg-slate-800 dark:text-white dark:hover:bg-slate-700",
  ghost: "text-slate-900 hover:bg-slate-100 focus-visible:ring-slate-300"
};

export function buttonClasses(variant: ButtonVariant = "primary", className?: string) {
  return clsx(baseStyles, variantStyles[variant], className);
}

export function Button({
  variant = "primary",
  leadingIcon,
  trailingIcon,
  className,
  children,
  type,
  ...rest
}: ButtonProps) {
  return (
    <button className={buttonClasses(variant, className)} type={type ?? "button"} {...rest}>
      {leadingIcon}
      {children}
      {trailingIcon}
    </button>
  );
}
