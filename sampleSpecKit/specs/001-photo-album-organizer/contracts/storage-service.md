# Contract: Storage Service (Internal Interface)

The application will use a unified `StorageService` to handle both SQLite metadata and Binary (Blob) storage.

## Methods

### `init()`
- **Purpose**: Initialize SQLite WASM and OPFS. Create tables if they don't exist.
- **Returns**: `Promise<void>`

### `getAlbumsGroupedByDate()`
- **Purpose**: Fetch all albums sorted by date then `sort_order`.
- **Returns**: `Promise<Record<string, Album[]>>`

### `reorderAlbum(albumId, newIndex)`
- **Purpose**: Update `sort_order` in the database.
- **Arguments**:
  - `albumId`: UUID
  - `newIndex`: Integer position within the group.
- **Returns**: `Promise<void>`

### `addPhoto(albumId, fileBlob)`
- **Purpose**: Store the physical file and link it to the album in SQLite.
- **Arguments**:
  - `albumId`: UUID
  - `fileBlob`: File/Blob object
- **Returns**: `Promise<PhotoMetadata>`

### `getPhotosInAlbum(albumId)`
- **Purpose**: Fetch all photo metadata for a specific album.
- **Returns**: `Promise<PhotoMetadata[]>`
