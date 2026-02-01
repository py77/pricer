# Pricer Project

A structured products pricer with Monte Carlo simulation for pricing autocallable products.

## Project Structure

```
pricer/
├── backend/          # Python backend (FastAPI)
├── api/              # API layer
├── ui/               # Next.js 14 frontend (App Router)
│   ├── src/
│   │   ├── app/      # Next.js pages
│   │   ├── components/ui/  # shadcn/ui components
│   │   ├── lib/      # Utilities (utils.ts for cn() helper)
│   │   └── api/      # API client
│   └── package.json
├── docs/             # Documentation
└── vercel.json       # Vercel deployment config
```

## Development

### Frontend (ui/)
```bash
cd ui
npm install
npm run dev        # Start dev server on localhost:3000
npm run build      # Production build
```

### Backend (Python)
```bash
# Use Python 3.11+
pip install -r requirements.txt
```

## Deployment

### GitHub
```bash
git add -A && git commit -m "message" && git push origin main
```

### Vercel
- Project: `pricer` (https://vercel.com/py77s-projects/pricer)
- **Root Directory**: Set to `ui` in Vercel project settings (Settings → Build and Deployment → Root Directory)
- Deploys automatically on push to `main` branch

## Key Configuration

### Vercel Settings (IMPORTANT)
- Root Directory must be set to `ui` because the Next.js app lives in a subfolder
- Framework: Next.js (auto-detected)

### .gitignore
- Uses `/lib/` (not `lib/`) to only ignore root-level lib folder
- This allows `ui/src/lib/` to be tracked (contains utils.ts)

## Common Issues

### "Cannot find module '@/lib/utils'"
The `@/` path alias maps to `./src/*` in tsconfig.json. If this error occurs:
1. Ensure `ui/src/lib/utils.ts` exists
2. Ensure `.gitignore` uses `/lib/` not `lib/` (to avoid ignoring subdirectories)

### Vercel build fails with "rootDirectory" error
Don't put `rootDirectory` in vercel.json - set it in Vercel project settings instead.

### Next.js deprecated themeColor warning
Use `viewport` export instead of putting `themeColor` in `metadata`:
```tsx
export const viewport: Viewport = {
    themeColor: '#0a0a0f',
}
```

## Tech Stack

- **Frontend**: Next.js 14.2.x, React 18, TailwindCSS, shadcn/ui
- **Backend**: Python, FastAPI
- **Deployment**: Vercel (frontend), GitHub
