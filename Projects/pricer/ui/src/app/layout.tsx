import './globals.css'
import type { Metadata } from 'next'

export const metadata: Metadata = {
    title: 'Structured Products Pricer',
    description: 'Price and analyze autocallable structured products',
}

export default function RootLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <html lang="en">
            <body>
                <header className="header">
                    <div className="container header-content">
                        <div className="logo">📊 Pricer</div>
                        <nav className="nav">
                            <a href="/" className="nav-link">Pricing</a>
                            <a href="/risk" className="nav-link">Risk</a>
                        </nav>
                    </div>
                </header>
                <main className="container">
                    {children}
                </main>
            </body>
        </html>
    )
}
