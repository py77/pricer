'use client';

import { ReactNode } from 'react';
import { Tooltip } from './Tooltip';

interface FormFieldProps {
    label: string;
    tooltip?: string;
    error?: string;
    success?: boolean;
    required?: boolean;
    children: ReactNode;
    htmlFor?: string;
}

export function FormField({
    label,
    tooltip,
    error,
    success,
    required,
    children,
    htmlFor
}: FormFieldProps) {
    return (
        <div className="form-group">
            <label className="form-label" htmlFor={htmlFor}>
                {label}
                {required && <span className="text-orange-500 ml-1">*</span>}
                {tooltip && (
                    <Tooltip content={tooltip}>
                        <span className="ml-2 inline-flex items-center justify-center w-4 h-4 text-xs rounded-full bg-gray-700 text-gray-300 cursor-help">
                            ?
                        </span>
                    </Tooltip>
                )}
            </label>
            <div className="relative">
                {children}
                {success && !error && (
                    <div className="absolute right-3 top-1/2 -translate-y-1/2 text-green-500 animate-fade-in">
                        ✓
                    </div>
                )}
            </div>
            {error && (
                <div className="text-red-400 text-sm mt-1 animate-slide-down">
                    {error}
                </div>
            )}
        </div>
    );
}
