# Pricer UI

Next.js web interface for the structured products pricer.

## Installation

```bash
npm install
```

## Development

```bash
# Start dev server on port 3000
npm run dev
```

## Build

```bash
npm run build
npm start
```

## Generate API Types

Regenerate TypeScript types from the API OpenAPI schema:

```bash
# Ensure API is running first
npm run generate-types
```

## Features

- **Pricing Page**: Run Monte Carlo pricing with configurable paths, seed, block size
- **Risk Page**: Greeks calculation with Delta, Vega, optional Rho
- **Monaco Editor**: Full JSON editor for term sheets
- **Load Example**: Fetch example term sheet from API
- **Results Display**: Summary cards, cashflow tables, PV decomposition

## Requirements

- API server running on http://localhost:8000
- Node.js 18+
