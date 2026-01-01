# Data Model: Photo Album Organizer

## SQLite Schema (Metadata)

### Table: `albums`
| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID (TEXT) | Primary Key |
| `name` | TEXT | Name of the album |
| `date` | TEXT | Date (YYYY-MM-DD) for grouping |
| `sort_order` | INTEGER | Manual sort position within date group |

### Table: `photos`
| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID (TEXT) | Primary Key |
| `album_id` | TEXT | Foreign Key to `albums.id` |
| `filename` | TEXT | Original filename |
| `local_storage_key` | TEXT | Reference to IndexedDB or OPFS file path |
| `created_at` | DATETIME | Insertion timestamp |

## State Management (Vanilla Store)

The `store/` will maintain a reactive state including:
- `albumsByDate`: A map of `{ 'Year-Month': [Album, ...] }` sorted by `sort_order`.
- `currentAlbum`: The currently opened album object.
- `isLoading`: Boolean for global loading states (DB init, image loading).

## Transitions
1. **Move Album**: Update `sort_order` for affected albums in the same date group.
2. **Add Photo**: Insert into `photos` table and store Blob in binary storage.
