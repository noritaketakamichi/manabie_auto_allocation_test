import sqlite3InitModule from '@sqlite.org/sqlite-wasm';

let db = null;

export const initDB = async () => {
    if (db) return db;

    const sqlite3 = await sqlite3InitModule({
        print: console.log,
        printErr: console.error,
    });

    if ('opfs' in sqlite3) {
        db = new sqlite3.oo1.OpfsDb('/photo_organizer.sqlite3');
        console.log('Using OPFS SQLite');
    } else {
        db = new sqlite3.oo1.DB('/photo_organizer.sqlite3', 'ct');
        console.warn('OPFS not available, using in-memory or alternative storage');
    }
    return db;
};

export const getDB = () => {
    if (!db) throw new Error('Database not initialized. Call initDB() first.');
    return db;
};
