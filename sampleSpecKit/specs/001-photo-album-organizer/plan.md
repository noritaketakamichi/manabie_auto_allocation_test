# Implementation Plan: Photo Album Organizer

**Branch**: `001-photo-album-organizer` | **Date**: 2026-01-01 | **Spec**: [specs/001-photo-album-organizer/spec.md]
**Input**: Vite, Vanilla JS, Local SQLite, Drag-and-Drop, Tile Interface.

## Summary
Build a local-first photo album organizer using Vite and Vanilla JavaScript. Metadata will be persisted in a client-side SQLite database (WASM/OPFS), and images will be managed via the browser's storage APIs to avoid remote uploads. Drag-and-drop reordering will be implemented using the native HTML5 API.

## Technical Context

**Language/Version**: JavaScript (ES2022+)  
**Primary Dependencies**: Vite (Build), `@sqlite.org/sqlite-wasm` (Storage)  
**Storage**: SQLite (WASM) with OPFS for persistence; Blobs for image storage.  
**Testing**: Vitest  
**Target Platform**: Modern Web Browsers (Chrome/Edge/Safari with OPFS support)  
**Project Type**: Single Page Application (SPA)  
**Performance Goals**: < 1.0s Initial Load, 60fps drag-and-drop animations.  
**Constraints**: No external server-side persistence; Minimal libraries; Vanilla JS only.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Code Quality**: Modular Vanilla JS (ES Modules). No framework overhead.
- [x] **Testing**: Core database logic and sorting algorithms will have 100% Vitest coverage.
- [x] **UX**: Native drag-and-drop and CSS Grid for the tile interface.
- [x] **Performance**: SQLite indexing for fast date-based grouping.
- [x] **Documentation**: All logic documented in `specs/`.

## Project Structure

### Documentation (this feature)

```text
specs/001-photo-album-organizer/
├── plan.md              # This file
├── research.md          # Storage and D&D research
├── data-model.md        # DB Schema and State
├── quickstart.md        # Setup instructions
├── contracts/           # Internal Service Interfaces
└── tasks.md             # Implementation tasks
```

### Source Code (repository root)

```text
src/
├── db/                  # SQLite initialization and Migrations
├── components/          # Vanilla component functions (AlbumList, PhotoGrid)
├── store/               # State management (Custom Vanilla Store)
├── styles/              # Vanilla CSS (layout.css, grid.css)
├── utils/               # DragDrop, DateHelpers
└── main.js              # Entry point

tests/
├── unit/                # DB and Store tests
└── integration/         # Drag-and-drop workflow tests
```

**Structure Decision**: Single project (Vanilla JS + Vite). Uses ES Modules to keep code clean and modular without a framework.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| SQLite in Browser | User requirement | IndexedDB is simpler but does not satisfy the "SQLite" request. |
