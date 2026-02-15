'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export function AppNav() {
    const pathname = usePathname();

    return (
        <nav className="app-nav">
            <Link href="/" className="app-nav-brand">
                <span className="app-nav-sigma">&Sigma;</span>
                Pricer
            </Link>
            <div className="app-nav-links">
                <Link
                    href="/"
                    className={`app-nav-link${pathname === '/' ? ' app-nav-link--active' : ''}`}
                >
                    Pricing
                </Link>
                <Link
                    href="/risk"
                    className={`app-nav-link${pathname === '/risk' ? ' app-nav-link--active' : ''}`}
                >
                    Risk
                </Link>
            </div>
        </nav>
    );
}
