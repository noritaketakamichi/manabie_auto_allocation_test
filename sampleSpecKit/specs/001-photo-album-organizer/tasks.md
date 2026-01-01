# Tasks: Photo Album Organizer

**Input**: Design documents from `/specs/001-photo-album-organizer/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are included as Vitest is part of the implementation plan to ensure core logic integrity per the Constitution.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Initialize Vite project with Vanilla JS preset in `/`
- [ ] T002 [P] Install dependencies: `@sqlite.org/sqlite-wasm`, `vitest`
- [ ] T003 [P] Configure Vitest in `vitest.config.js`
- [ ] T004 [P] Initialize design system tokens and basic CSS in `src/styles/base.css` [III]
- [ ] T005 [P] Setup performance budget and monitoring tools [IV]

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

- [ ] T006 Implement SQLite WASM wrapper with OPFS support in `src/db/sqlite-adapter.js`
- [ ] T007 [P] Create database schema migrations for `albums` and `photos` tables in `src/db/migrations.js`
- [ ] T008 [P] Implement reactive Vanilla store in `src/store/index.js`
- [ ] T009 Implement base `StorageService.init()` and table creation in `src/services/storage-service.js`
- [ ] T010 [P] Implement UUID utility in `src/utils/uuid.js`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 2 - Date-Based Album Grouping (Priority: P2 -> Promoted to first for data flow) 🎯 MVP

**Goal**: Display albums grouped by month/year headers

**Independent Test**: Create two albums with different dates via JS console. Verify they appear under separate month/year headings on the UI.

### Implementation for User Story 2

- [ ] T011 [P] [US2] Implement `getAlbumsGroupedByDate` in `src/services/storage-service.js`
- [ ] T012 [P] [US2] Create helper to format dates into Group Headers (e.g. "January 2026") in `src/utils/date-helpers.js`
- [ ] T013 [US2] Create `AlbumItem` vanilla component in `src/components/AlbumItem.js`
- [ ] T014 [US2] Create `AlbumList` vanilla component with date-grouping logic in `src/components/AlbumList.js`
- [ ] T015 [US2] Implement album creation form/logic to populate data in `src/main.js`

**Checkpoint**: User Story 2 is functional - albums can be created and viewed in date groups.

---

## Phase 4: User Story 1 - Drag-and-Drop Album Reordering (Priority: P1)

**Goal**: Manually reorder photo albums via drag-and-drop

**Independent Test**: Drag an album to a new position. Refresh page. Verify position is maintained.

### Implementation for User Story 1

- [ ] T016 [US1] Implement native HTML5 Drag and Drop handlers in `src/utils/drag-drop.js`
- [ ] T017 [US1] Integrate `reorderAlbum` method in `src/services/storage-service.js` to update `sort_order`
- [ ] T018 [US1] Update `AlbumList.js` to support draggable attributes and handle drop events
- [ ] T019 [P] [US1] Add visual drag feedback (ghosting/placeholders) in `src/styles/components.css` [III]

**Checkpoint**: User Story 1 is functional - albums can be reordered within groups.

---

## Phase 5: User Story 3 - Tile-View Photo Preview (Priority: P3)

**Goal**: View photos in a tile grid within an album

**Independent Test**: Select an album, add 5 files. Verify 5 tiles appear in a responsive grid.

### Implementation for User Story 3

- [ ] T020 [US3] Implement `addPhoto` (Blob storage in OPFS + metadata in SQLite) in `src/services/storage-service.js`
- [ ] T021 [P] [US3] Implement `getPhotosInAlbum` in `src/services/storage-service.js`
- [ ] T022 [US3] Create `PhotoTile` component in `src/components/PhotoTile.js`
- [ ] T023 [US3] Create `PhotoGrid` layout in `src/components/PhotoGrid.js` using CSS Grid
- [ ] T024 [P] [US3] Add "No Photos" empty state in `PhotoGrid.js`
- [ ] T025 [US3] Implement routing/view switching between Album List and Photo Grid in `src/main.js`

**Checkpoint**: All user stories functional.

---

## Phase N: Polish & Cross-Cutting Concerns

- [ ] T026 [P] Documentation updates in `quickstart.md`
- [ ] T027 Code cleanup and refactoring
- [ ] T028 Performance optimization across all stories (SQLite indexing check) [IV]
- [ ] T029 [P] Accessibility (a11y) audit and aria-label updates [III]
- [ ] T030 Final validation of SQLite persistence in OPFS

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup
- **User Story 2 (P2)**: Depends on Foundational. Promoted to first implementation as it provides the base list view.
- **User Story 1 (P1)**: Depends on US2 completion (need list to reorder).
- **User Story 3 (P3)**: Depends on US2 completion (need album to add photos to).

### Parallel Opportunities

- T002-T005 can run in parallel
- T007-T008 can run in parallel
- T011-T012 can run in parallel
- T021 can run in parallel with UI tasks in US3

---

## Implementation Strategy

### MVP First (User Story 2)
1. Complete Setup + Foundational
2. Implement Album creation and Date-grouped list
3. Validate persistence

### Incremental Delivery
1. Add Drag-and-Drop Reordering (US1)
2. Add Photo Upload and Grid View (US3)
3. Final polish and performance check

---

## Notes
- [P] tasks = different files, no dependencies
- [Story] label mapping for traceability
- SQLite WASM requires OPFS which demands specific COOP/COEP headers; Vite configuration in T001 must account for this.
