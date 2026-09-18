# Dolphin UI

Frontend application for **Dolphin AI**, built with **React 19**, **Tailwind CSS v4**, and **Vite**.

---

## Tech Stack

- **Framework**: [React 19](https://react.dev/)
- **Build Tool / Dev Server**: [Vite 6](https://vite.dev/)
- **Styling**: [Tailwind CSS v4](https://tailwindcss.com/) (`@tailwindcss/vite`)
- **Icons**: [Lucide React](https://lucide.dev/) & Custom SVG icons
- **Routing**: [React Router v7](https://reactrouter.com/) (Data router with session-based dynamic routes)
- **Testing**: [Vitest](https://vitest.dev/) & [React Testing Library](https://testing-library.com/)
- **PDF & Media**: `react-pdf`, `pdfjs-dist`, `react-player` (lazy-loaded on demand)
- **Markdown & Sanitization**: `marked`, `dompurify`
- **HTTP Client**: `axios`

---

## Getting Started

### Prerequisites

- **Node.js**: v18+ (tested on Node v20/v24)
- **Package Manager**: `npm` (or `yarn`)

### Installation

```bash
npm install
```

### Environment Configuration

Create or update your `.env` file in the root directory:

```env
# Backend API Base URL (both REACT_APP_ and VITE_ prefixes are supported)
REACT_APP_BASE_URL=https://dolphin.marinerskills.com/dolphin-rb/api
# Or for local development:
# REACT_APP_BASE_URL=http://localhost:8000

# Optional: Override production base path (defaults to /dolphin-rb/ui/ in production, / in dev)
# VITE_BASE_PATH=/dolphin-rb/ui/
```

> **Note**: Vite is configured with `envPrefix: ['VITE_', 'REACT_APP_']`, so both prefixes work seamlessly.

---

## Available Scripts

In the project directory, you can run:

### `npm run dev` (or `npm start`)
Starts the local development server at **[http://localhost:3000](http://localhost:3000)** with Hot Module Replacement (HMR).

### `npm run build`
Compiles and bundles the application for production into the **`build/`** folder:
- Automatic route-based code-splitting (`React.lazy` + `Suspense`).
- Isolated vendor chunking (`vendor-react`, `vendor-markdown`, `vendor-icons`, `vendor-pdf`).
- Dynamic base path support (`/dolphin-rb/ui/` for subpath deployments).

### `npm run preview`
Locally previews the production build created in `build/`.

### `npm test`
Runs the automated unit test suite using **Vitest** in run mode (`vitest run`).

---

## Project Structure

```
dolphin-ui/
├── public/                 # Static assets (favicons, logos, manifests)
├── src/
│   ├── api/                # API client, auth, and streaming fetchers
│   ├── assets/             # Images and SVG icon components
│   ├── components/         # Reusable UI components (chat, admin, header, etc.)
│   ├── config/             # Environment and API base configuration
│   ├── context/            # React Context providers (ThemeMode)
│   ├── layouts/            # Page layouts
│   ├── pages/              # App routes & views (Chatpage, AdminPage, LoginSignup)
│   ├── theme/              # Color palettes and theme tokens
│   ├── App.jsx             # Main router and auth state handler (code-split)
│   ├── index.jsx           # Application entry point
│   └── setupTests.js       # Test runner setup and polyfills
├── index.html              # Vite entry HTML
├── vite.config.js          # Vite build, vendor chunking & test configuration
├── todo.md                 # Project backlog & TypeScript migration plan
└── package.json
```

---

## Deployment

Running `npm run build` outputs static production files to the `build/` directory:

- Ready to be served by **Nginx**, **Apache**, or any static hosting/CDN.
- Configured by default for subpath deployment at `/dolphin-rb/ui/`.
- Single-page application routing requires fallback to `/dolphin-rb/ui/index.html` (or `/index.html` if root-deployed).
