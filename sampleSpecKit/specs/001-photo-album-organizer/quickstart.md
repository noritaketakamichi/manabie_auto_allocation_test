# Quickstart: Photo Album Organizer

This project uses Vite with Vanilla JS and SQLite WASM.

## Prerequisites
- Node.js 18+
- Modern browser (Chrome/Edge/Safari) with OPFS support.

## Setup
1. Clone the repository.
2. Install dependencies:
   ```bash
   npm install
   ```

## Development
Run the dev server:
```bash
npm run dev
```

## Testing
Run unit and integration tests:
```bash
npm run test
```

## Project Structure Highlights
- `/src/db/`: Contains the `sqlite-wasm` initialization logic.
- `/src/utils/drag-drop.js`: Native implementation of the Drag and Drop API.
- `/src/main.js`: Main application loop and DOM rendering.
