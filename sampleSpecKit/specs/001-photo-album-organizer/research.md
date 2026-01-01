# Research: Photo Album Organizer (Local SQLite & Vanilla Vite)

## Decision 1: Storage Architecture (SQLite)
- **Decision**: Use `sqlite-wasm` with **Origin Private File System (OPFS)** for persistence.
- **Rationale**: User requested SQLite and minimal libraries. `sqlite-wasm` is the official WASM build, and OPFS allows native-like persistence in modern browsers without needing a Node.js backend. This keeps the Vite setup truly "vanilla" on the frontend while satisfying the SQLite requirement.
- **Alternatives considered**: 
  - `sql.js`: No built-in persistence (browser only), requires manual loading/saving of the DB file.
  - Node.js + `better-sqlite3`: Requires a separate backend process, increasing complexity.

## Decision 2: Image Management (No Uploads)
- **Decision**: Use **IndexedDB** or **OPFS** to store the actual Image Blobs, and link them via IDs in SQLite.
- **Rationale**: Since images "are not uploaded anywhere", they must stay client-side. Using the File System Access API allows users to "pick" a folder, but persistent access can be tricky. Storing the blobs in the browser's OPFS ensures they are available across sessions without a server.
- **Alternatives considered**:
  - LocalStorage: Too small (5MB limit).
  - External URLs: User said photos are "organized" which implies ownership of the data.

## Decision 3: Drag and Drop
- **Decision**: Native **HTML5 Drag and Drop API**.
- **Rationale**: Fits the "vanilla" requirement. No libraries like `vuedraggable` or `react-beautiful-dnd` needed.
- **Alternatives considered**:
  - `SortableJS`: Lightweight but still an external library. Native is preferred for "as much as possible".

## Decision 4: Build System
- **Decision**: Vite with no framework (Vanilla preset).
- **Rationale**: Explicitly requested in the prompt.
