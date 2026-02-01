export default function NotFound() {
    return (
        <div style={{ textAlign: 'center', padding: '4rem' }}>
            <h2 style={{ fontSize: '2rem', marginBottom: '1rem' }}>Page Not Found</h2>
            <p style={{ color: '#888' }}>The page you're looking for doesn't exist.</p>
            <a href="/" style={{ color: '#667eea', marginTop: '1rem', display: 'inline-block' }}>
                Return Home
            </a>
        </div>
    )
}
