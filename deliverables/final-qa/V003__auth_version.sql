-- Existing users and tokens start with version 0. No data is deleted.
ALTER TABLE users ADD COLUMN auth_version INTEGER NOT NULL DEFAULT 0
    CHECK (auth_version >= 0);
