export const runMigrations = (db) => {
    db.exec(\`
        CREATE TABLE IF NOT EXISTS albums (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            date TEXT NOT NULL,
            sort_order INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS photos (
            id TEXT PRIMARY KEY,
            album_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            local_storage_key TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (album_id) REFERENCES albums(id)
        );
    \`);
};
