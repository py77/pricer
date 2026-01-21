'use client';

import React from 'react';

type SearchBarProps = {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
};

export function SearchBar({ id = 'search-instruments', value, onChange, placeholder }: SearchBarProps) {
  return (
    <div className="search-bar">
      <label className="sr-only" htmlFor={id}>
        Search instruments
      </label>
      <span className="search-icon" aria-hidden>
        ⌕
      </span>
      <input
        id={id}
        className="search-input"
        type="search"
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}

type PillButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  active?: boolean;
};

export function PillButton({ active = false, className = '', ...props }: PillButtonProps) {
  return (
    <button
      type="button"
      className={`pill-button ${active ? 'is-active' : ''} ${className}`.trim()}
      {...props}
    />
  );
}

type FrameProps = {
  title?: string;
  subtitle?: string;
  actions?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
};

export function Frame({ title, subtitle, actions, className = '', children }: FrameProps) {
  return (
    <section className={`frame ${className}`.trim()}>
      {(title || subtitle || actions) && (
        <div className="frame-header">
          <div>
            {title && <div className="frame-title">{title}</div>}
            {subtitle && <div className="frame-subtitle">{subtitle}</div>}
          </div>
          {actions && <div className="frame-actions">{actions}</div>}
        </div>
      )}
      <div className="frame-body">{children}</div>
    </section>
  );
}

type GraveCardProps =
  | ({ as?: 'div' } & React.HTMLAttributes<HTMLDivElement>)
  | ({ as: 'button' } & React.ButtonHTMLAttributes<HTMLButtonElement>);

export function GraveCard({ as = 'div', className = '', ...props }: GraveCardProps) {
  if (as === 'button') {
    const buttonProps = props as React.ButtonHTMLAttributes<HTMLButtonElement>;
    return (
      <button
        type="button"
        className={`grave-card grave-card--interactive ${className}`.trim()}
        {...buttonProps}
      />
    );
  }

  const divProps = props as React.HTMLAttributes<HTMLDivElement>;
  return <div className={`grave-card ${className}`.trim()} {...divProps} />;
}

type MetricChipProps = {
  label: string;
  value: string;
};

export function MetricChip({ label, value }: MetricChipProps) {
  return (
    <div className="metric-chip">
      <span className="metric-chip__label">{label}</span>
      <span className="metric-chip__value">{value}</span>
    </div>
  );
}

type BadgeProps = {
  children: React.ReactNode;
  className?: string;
};

export function Badge({ children, className = '' }: BadgeProps) {
  return <span className={`badge ${className}`.trim()}>{children}</span>;
}

type RatingBarsProps = {
  value: number;
  color: 'orange' | 'blue';
  label?: string;
};

export function RatingBars({ value, color, label }: RatingBarsProps) {
  const safeValue = Math.max(0, Math.min(5, Math.round(value)));
  return (
    <div className="rating-bars" role="img" aria-label={label ?? `Rating ${safeValue} out of 5`}>
      {Array.from({ length: 5 }).map((_, index) => (
        <span
          key={index}
          className={`rating-bar ${index < safeValue ? `is-active ${color}` : ''}`.trim()}
        />
      ))}
    </div>
  );
}
