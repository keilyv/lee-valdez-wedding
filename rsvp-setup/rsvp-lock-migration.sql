-- Run once on the wedding-rsvps D1 database BEFORE deploying the updated Worker.
-- Existing confirmed RSVPs remain saved and become read-only by default.
ALTER TABLE invitations ADD COLUMN editable INTEGER NOT NULL DEFAULT 0 CHECK (editable IN (0, 1));
