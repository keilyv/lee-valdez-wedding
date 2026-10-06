-- Run this in your Cloudflare D1 database before uploading private invitations.
CREATE TABLE IF NOT EXISTS invitations (
  token_hash TEXT PRIMARY KEY,
  household_name TEXT NOT NULL,
  max_guests INTEGER NOT NULL CHECK (max_guests BETWEEN 1 AND 20),
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  attendance TEXT CHECK (attendance IN ('attending', 'declined')),
  guest_count INTEGER CHECK (guest_count BETWEEN 0 AND 20),
  guest_names TEXT NOT NULL DEFAULT '',
  dietary_notes TEXT NOT NULL DEFAULT '',
  message TEXT NOT NULL DEFAULT '',
  responded_at TEXT,
  CHECK (guest_count IS NULL OR guest_count <= max_guests),
  CHECK (attendance IS NULL OR (attendance = 'declined' AND guest_count = 0) OR (attendance = 'attending' AND guest_count >= 1))
);
