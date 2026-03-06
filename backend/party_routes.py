"""
Party system routes for group gameplay
"""

from fastapi import APIRouter, HTTPException
from database.connection import fetch_all, fetch_one, execute, fetch_val
from datetime import datetime

party_router = APIRouter()

# ===== PARTY SYSTEM API =====

@party_router.post("/party/create/{character_id}")
async def create_party(character_id: int, party_name: str = None, is_public: bool = False):
    """
    Create a new party with character as leader
    """
    try:
        # Check if character already in a party
        existing = fetch_one("SELECT party_id FROM characters WHERE id = %s", character_id)
        if existing and existing[0]:
            raise HTTPException(status_code=400, detail="Already in a party")
        
        # Create party
        party_id = fetch_val("""
            INSERT INTO parties (party_name, leader_character_id, is_public)
            VALUES (%s, %s, %s)
            RETURNING id
        """, party_name or f"Party {character_id}", character_id, is_public)
        
        # Add leader as member
        execute("""
            INSERT INTO party_members (party_id, character_id, role)
            VALUES (%s, %s, 'leader')
        """, party_id, character_id)
        
        # Update character
        execute("UPDATE characters SET party_id = %s WHERE id = %s", party_id, character_id)
        
        return {
            "success": True,
            "party_id": party_id,
            "party_name": party_name,
            "role": "leader"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@party_router.post("/party/invite/{party_id}/{character_id}")
async def invite_to_party(party_id: int, character_id: int, inviter_id: int):
    """
    Send party invitation to a character (leader only)
    """
    try:
        # Check if inviter is party leader
        party = fetch_one("""
            SELECT leader_character_id, max_members, party_name
            FROM parties WHERE id = %s
        """, party_id)
        
        if not party:
            raise HTTPException(status_code=404, detail="Party not found")
        
        leader_id, max_members, party_name = party
        if leader_id != inviter_id:
            raise HTTPException(status_code=403, detail="Only party leader can invite")
        
        # Check party size
        current_size = fetch_val("SELECT COUNT(*) FROM party_members WHERE party_id = %s", party_id)
        if current_size >= max_members:
            raise HTTPException(status_code=400, detail="Party is full")
        
        # Check if character already in a party
        target_party = fetch_one("SELECT party_id FROM characters WHERE id = %s", character_id)
        if target_party and target_party[0]:
            raise HTTPException(status_code=400, detail="Character already in a party")
        
        # Check if invitation already exists
        existing_invite = fetch_one("""
            SELECT id FROM party_invitations 
            WHERE party_id = %s AND invited_character_id = %s AND status = 'pending'
            AND expires_at > CURRENT_TIMESTAMP
        """, party_id, character_id)
        
        if existing_invite:
            raise HTTPException(status_code=400, detail="Invitation already sent")
        
        # Get inviter name
        inviter_name = fetch_val("SELECT name FROM characters WHERE id = %s", inviter_id)
        
        # Create invitation
        invite_id = fetch_val("""
            INSERT INTO party_invitations (party_id, inviter_character_id, invited_character_id, status)
            VALUES (%s, %s, %s, 'pending')
            RETURNING id
        """, party_id, inviter_id, character_id)
        
        return {
            "success": True,
            "message": f"Invitation sent",
            "invitation_id": invite_id,
            "inviter_name": inviter_name,
            "party_name": party_name
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@party_router.post("/party/invitations/{invitation_id}/accept")
async def accept_invitation(invitation_id: int, character_id: int):
    """
    Accept a party invitation
    """
    try:
        # Get invitation details
        invite = fetch_one("""
            SELECT party_id, inviter_character_id, invited_character_id, status, expires_at
            FROM party_invitations WHERE id = %s
        """, invitation_id)
        
        if not invite:
            raise HTTPException(status_code=404, detail="Invitation not found")
        
        party_id, inviter_id, invited_id, status, expires_at = invite
        
        # Verify character
        if invited_id != character_id:
            raise HTTPException(status_code=403, detail="This invitation is not for you")
        
        # Check if expired
        if expires_at < datetime.now():
            execute("UPDATE party_invitations SET status = 'expired' WHERE id = %s", invitation_id)
            raise HTTPException(status_code=400, detail="Invitation expired")
        
        # Check status
        if status != 'pending':
            raise HTTPException(status_code=400, detail=f"Invitation already {status}")
        
        # Check if character already in a party
        char_party = fetch_one("SELECT party_id FROM characters WHERE id = %s", character_id)
        if char_party and char_party[0]:
            raise HTTPException(status_code=400, detail="Already in a party")
        
        # Check party size
        party = fetch_one("SELECT max_members FROM parties WHERE id = %s", party_id)
        if not party:
            raise HTTPException(status_code=404, detail="Party no longer exists")
        
        max_members = party[0]
        current_size = fetch_val("SELECT COUNT(*) FROM party_members WHERE party_id = %s", party_id)
        if current_size >= max_members:
            raise HTTPException(status_code=400, detail="Party is full")
        
        # Add to party
        execute("""
            INSERT INTO party_members (party_id, character_id, role)
            VALUES (%s, %s, 'member')
        """, party_id, character_id)
        
        execute("UPDATE characters SET party_id = %s WHERE id = %s", party_id, character_id)
        
        # Update invitation status
        execute("""
            UPDATE party_invitations 
            SET status = 'accepted', responded_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, invitation_id)
        
        return {
            "success": True,
            "message": "Joined party",
            "party_id": party_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@party_router.post("/party/invitations/{invitation_id}/reject")
async def reject_invitation(invitation_id: int, character_id: int):
    """
    Reject a party invitation
    """
    try:
        # Get invitation details
        invite = fetch_one("""
            SELECT invited_character_id, status
            FROM party_invitations WHERE id = %s
        """, invitation_id)
        
        if not invite:
            raise HTTPException(status_code=404, detail="Invitation not found")
        
        invited_id, status = invite
        
        # Verify character
        if invited_id != character_id:
            raise HTTPException(status_code=403, detail="This invitation is not for you")
        
        # Check status
        if status != 'pending':
            raise HTTPException(status_code=400, detail=f"Invitation already {status}")
        
        # Update invitation status
        execute("""
            UPDATE party_invitations 
            SET status = 'rejected', responded_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, invitation_id)
        
        return {
            "success": True,
            "message": "Invitation rejected"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@party_router.get("/party/invitations/pending/{character_id}")
async def get_pending_invitations(character_id: int):
    """
    Get pending party invitations for a character
    """
    try:
        # Mark expired invitations
        execute("""
            UPDATE party_invitations 
            SET status = 'expired' 
            WHERE invited_character_id = %s 
            AND status = 'pending' 
            AND expires_at < CURRENT_TIMESTAMP
        """, character_id)
        
        # Get active invitations
        invites = fetch_all("""
            SELECT pi.id, pi.party_id, pi.inviter_character_id, pi.created_at, pi.expires_at,
                   p.party_name, c.name as inviter_name, c.level as inviter_level
            FROM party_invitations pi
            JOIN parties p ON p.id = pi.party_id
            JOIN characters c ON c.id = pi.inviter_character_id
            WHERE pi.invited_character_id = %s 
            AND pi.status = 'pending'
            AND pi.expires_at > CURRENT_TIMESTAMP
            ORDER BY pi.created_at DESC
        """, character_id)
        
        return {
            "invitations": [
                {
                    "invitation_id": inv[0],
                    "party_id": inv[1],
                    "inviter_character_id": inv[2],
                    "created_at": inv[3].isoformat() if inv[3] else None,
                    "expires_at": inv[4].isoformat() if inv[4] else None,
                    "party_name": inv[5],
                    "inviter_name": inv[6],
                    "inviter_level": inv[7]
                } for inv in invites
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@party_router.post("/party/leave/{character_id}")
async def leave_party(character_id: int):
    """
    Leave current party
    """
    try:
        # Get character's party
        char = fetch_one("SELECT party_id FROM characters WHERE id = %s", character_id)
        if not char or not char[0]:
            raise HTTPException(status_code=400, detail="Not in a party")
        
        party_id = char[0]
        
        # Check if leader
        party = fetch_one("SELECT leader_character_id FROM parties WHERE id = %s", party_id)
        if party and party[0] == character_id:
            # Leader leaving - disband party
            execute("DELETE FROM party_members WHERE party_id = %s", party_id)
            execute("UPDATE characters SET party_id = NULL WHERE party_id = %s", party_id)
            execute("DELETE FROM parties WHERE id = %s", party_id)
            return {"success": True, "message": "Party disbanded"}
        else:
            # Regular member leaving
            execute("DELETE FROM party_members WHERE party_id = %s AND character_id = %s", party_id, character_id)
            execute("UPDATE characters SET party_id = NULL WHERE id = %s", character_id)
            return {"success": True, "message": "Left party"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@party_router.get("/party/info/{party_id}")
async def get_party_info(party_id: int):
    """
    Get party information and member list
    """
    try:
        party = fetch_one("""
            SELECT p.party_name, p.leader_character_id, p.max_members, p.is_public, 
                   p.experience_share_type, p.loot_distribution,
                   c.name as leader_name
            FROM parties p
            JOIN characters c ON c.id = p.leader_character_id
            WHERE p.id = %s
        """, party_id)
        
        if not party:
            raise HTTPException(status_code=404, detail="Party not found")
        
        party_name, leader_id, max_members, is_public, exp_share, loot_dist, leader_name = party
        
        # Get members
        members = fetch_all("""
            SELECT c.id, c.name, c.level, c.health_points, c.max_health_points, 
                   c.magic_points, c.max_magic_points, pm.role
            FROM party_members pm
            JOIN characters c ON c.id = pm.character_id
            WHERE pm.party_id = %s
            ORDER BY pm.role DESC, pm.joined_at
        """, party_id)
        
        return {
            "party_id": party_id,
            "party_name": party_name,
            "leader": {"id": leader_id, "name": leader_name},
            "max_members": max_members,
            "current_members": len(members),
            "is_public": is_public,
            "experience_share": exp_share,
            "loot_distribution": loot_dist,
            "members": [
                {
                    "character_id": m[0],
                    "name": m[1],
                    "level": m[2],
                    "hp": m[3],
                    "max_hp": m[4],
                    "mp": m[5],
                    "max_mp": m[6],
                    "role": m[7]
                } for m in members
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@party_router.get("/party/nearby-players/{character_id}")
async def get_nearby_players(character_id: int):
    """
    Get list of nearby players in the same location (for inviting to party)
    """
    try:
        # Get character's location
        char = fetch_one("""
            SELECT current_location_id, party_id, name 
            FROM characters WHERE id = %s
        """, character_id)
        
        if not char:
            raise HTTPException(status_code=404, detail="Character not found")
        
        location_id, char_party_id, char_name = char
        
        if not location_id:
            return {"nearby_players": []}
        
        # Get other characters in same location (excluding self and those in parties)
        players = fetch_all("""
            SELECT c.id, c.name, c.level, r.name as race, cc.name as class,
                   c.party_id
            FROM characters c
            JOIN races r ON r.id = c.race_id
            JOIN character_classes cc ON cc.id = c.class_id
            WHERE c.current_location_id = %s 
            AND c.id != %s
            AND c.user_id IN (SELECT DISTINCT user_id FROM characters)
            ORDER BY c.name
        """, location_id, character_id)
        
        return {
            "nearby_players": [
                {
                    "character_id": p[0],
                    "name": p[1],
                    "level": p[2],
                    "race": p[3],
                    "class": p[4],
                    "in_party": p[5] is not None
                } for p in players
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@party_router.get("/party/my-party/{character_id}")
async def get_my_party(character_id: int):
    """
    Get character's current party info
    """
    try:
        party_id = fetch_val("SELECT party_id FROM characters WHERE id = %s", character_id)
        if not party_id:
            return {"in_party": False}
        
        # Reuse get_party_info
        party_info = await get_party_info(party_id)
        party_info["in_party"] = True
        return party_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
