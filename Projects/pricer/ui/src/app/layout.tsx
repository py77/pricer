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
                <main className="container app-main">
                    {children}
                </main>
            </body>
        </html>
    )
}
