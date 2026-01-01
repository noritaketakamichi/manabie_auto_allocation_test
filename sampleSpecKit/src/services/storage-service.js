import { initDB, getDB } from '../db/sqlite-adapter';
import { runMigrations } from '../db/migrations';

export const StorageService = {
    async init() {
        const db = await initDB();
        runMigrations(db);
        console.log('StorageService initialized');
    }
};
