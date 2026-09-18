# TODO

## Completed Features
- [x] Add router for chat session (`/session/:sessionId` and `/session=:sessionSlug` with persistent state)
- [x] Chat item dropdown context menu (working Save/Unsave Chat API integration)
- [x] Auto-reset textarea height on Enter and Send
- [x] Code-splitting & bundle optimization (reduced main chat bundle by 90% from 916 kB to 91 kB)
- [x] Disable textarea and input controls during streaming
- [x] Dynamic production base path configuration (`/dolphin-rb/ui/` in production, `/` in dev)

---

## Active & Upcoming Tasks
- [ ] Git branch regularization

---

## TypeScript Migration Plan (Estimated Effort: 1 to 1.5 Days / 8–12 Hours)

Progressive migration strategy using Vite's hybrid `.js` / `.ts` support (`allowJs: true`), ensuring zero downtime or broken builds during migration.

### Phase 1: Setup & Tooling (~30 mins)
- [ ] Install dev dependencies: `typescript`, `@types/react`, `@types/react-dom`, `@types/node`
- [ ] Initialize `tsconfig.json` with `"allowJs": true`, `"jsx": "react-jsx"`, and `"moduleResolution": "bundler"`
- [ ] Add npm script: `"type-check": "tsc --noEmit"`
- [ ] Ensure Vite continues compiling and hot-reloading smoothly

### Phase 2: Core Data Types & Models (`src/types/`) (~1.5–2 hours)
- [ ] `src/types/chat.ts`:
  - `Message` (role, content, isThinking, isStreaming, status, statusText, timestamp, sections, suggestions, etc.)
  - `Session` (id, title, updated_at, isSaved, category, etc.)
  - `StreamChunk` (type, token, content, topic_codes, video_suggestions, etc.)
  - `MediaItem` (Video, Image, PDF preview models)
  - `TopicCourse` (CourseName, CourseCode, topicName, matched)
- [ ] `src/types/user.ts`:
  - `UserProfile`, `UserRole`, `LoginResponse`
- [ ] `src/types/theme.ts`:
  - `ThemeMode` ("light" | "dark")

### Phase 3: API & Context Layer Migration (~1.5 hours)
- [ ] Convert `src/api/client.js` -> `client.ts` (typed Axios instance & interceptors)
- [ ] Convert `src/api/apiAuth.js` -> `apiAuth.ts`
- [ ] Convert `src/api/fetchApi.js` -> `fetchApi.ts` (strongly-typed streaming callbacks & payload helpers)
- [ ] Convert `src/config/env.js` -> `env.ts`
- [ ] Convert `src/context/ThemeModeContext.jsx` -> `ThemeModeContext.tsx`

### Phase 4: Icons & UI Components (~4–5 hours)
- [ ] Convert `src/assets/svgIcons/*.jsx` -> `*.tsx` (reusable `IconProps` interface)
- [ ] Convert `src/components/chat/`:
  - [ ] `MediaPreviewModal.jsx` -> `MediaPreviewModal.tsx`
  - [ ] `SecurePdfViewer.jsx` -> `SecurePdfViewer.tsx`
  - [ ] `QuizDisplay.jsx` -> `QuizDisplay.tsx`
  - [ ] `WelcomeChatScreen.jsx` -> `WelcomeChatScreen.tsx`
  - [ ] `ChatItem.jsx` -> `ChatItem.tsx`
  - [ ] `ChatSideBar.jsx` -> `ChatSideBar.tsx`
  - [ ] `ChatMessage.jsx` -> `ChatMessage.tsx`
  - [ ] `ChatWindow.jsx` -> `ChatWindow.tsx`
- [ ] Convert Header and Admin components:
  - [ ] `src/components/header/Header.jsx` -> `Header.tsx`
  - [ ] `src/components/admin/AdminSidebar.jsx` -> `AdminSidebar.tsx`

### Phase 5: Pages, Routing & Entrypoint (~2 hours)
- [ ] Convert `src/pages/admin/` (`AdminPage.jsx`, `Members.jsx`) -> `.tsx`
- [ ] Convert `src/pages/ChatHistoryAdmin.jsx` -> `.tsx`
- [ ] Convert `src/pages/LoginSignup.jsx` -> `.tsx`
- [ ] Convert `src/pages/chatpage/Chatpage.jsx` -> `Chatpage.tsx`
- [ ] Convert `src/App.jsx` -> `App.tsx`
- [ ] Convert `src/index.jsx` -> `index.tsx`

### Phase 6: Strict Mode & Verification (~1 hour)
- [ ] Run `npm run type-check` (verify 0 type errors)
- [ ] Enable `"strict": true` in `tsconfig.json`
- [ ] Convert test files (`*.test.jsx` -> `*.test.tsx`)
- [ ] Run `npm test -- --run` (verify all tests pass)
- [ ] Run `npm run build` (verify production build outputs clean bundles)
