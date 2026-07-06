# Keshepool Frontend

Next.js Telegram Mini App for the Keshepool product catalog, wallet, orders, profile, invite, support, and finance flows.

## Stack

- Next.js App Router
- React 19
- TypeScript
- Tailwind CSS 4
- Shadcn UI, Radix UI, Lucide icons
- npm

## Source Structure

```text
src/
+-- app/                 # Next.js routes, layout, global styles
+-- components/
|   +-- layout/          # App shell components
|   +-- ui/              # Shadcn UI primitives
+-- features/
|   +-- products/        # Product-specific components and types
+-- lib/                 # API client, icons, shared utilities
+-- types/               # Global TypeScript declarations
```

## Commands

```bash
npm run dev
npm run build
npm run lint
```
