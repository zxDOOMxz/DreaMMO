-- Party Invitations System
CREATE TABLE IF NOT EXISTS party_invitations (
    id SERIAL PRIMARY KEY,
    party_id INTEGER NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
    inviter_character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    invited_character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'pending', -- pending, accepted, rejected, expired
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '5 minutes'),
    responded_at TIMESTAMP,
    UNIQUE(party_id, invited_character_id, status) -- Prevent duplicate pending invitations
);

CREATE INDEX IF NOT EXISTS idx_party_invitations_invited ON party_invitations(invited_character_id, status);
CREATE INDEX IF NOT EXISTS idx_party_invitations_party ON party_invitations(party_id);
