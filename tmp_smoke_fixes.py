import json
import random
import string
import sys

import httpx

BASE = "http://127.0.0.1:8000/api"


def rnd(prefix: str) -> str:
    return f"{prefix}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=8))}"


def register_and_login(username: str, email: str, password: str = "TestPass123"):
    with httpx.Client(timeout=15.0) as c:
        r = c.post(f"{BASE}/auth/register", json={"username": username, "email": email, "password": password})
        r.raise_for_status()
        t = c.post(f"{BASE}/auth/login", json={"username": username, "password": password})
        t.raise_for_status()
        token = t.json()["access_token"]
        return token


def create_character(token: str, user_id: int, name: str, race_id: int, class_id: int):
    with httpx.Client(timeout=15.0, headers={"Authorization": f"Bearer {token}"}) as c:
        r = c.post(
            f"{BASE}/characters/create",
            json={
                "name": name,
                "user_id": user_id,
                "race_id": race_id,
                "class_id": class_id,
            },
        )
        r.raise_for_status()
        return int(r.json()["data"]["character"]["id"])


def decode_sub(token: str) -> int:
    payload = token.split(".")[1]
    padding = "=" * (-len(payload) % 4)
    import base64

    data = json.loads(base64.urlsafe_b64decode(payload + padding).decode("utf-8"))
    return int(data["sub"])


def main():
    out = {"ok": True, "checks": {}}
    try:
        with httpx.Client(timeout=10.0) as c:
            health = c.get(f"{BASE}/health")
            out["checks"]["health_200"] = health.status_code == 200

            races = c.get(f"{BASE}/races").json().get("races", [])
            classes = c.get(f"{BASE}/classes").json().get("classes", [])
            race_id = int(races[0]["id"])
            class_id = int(classes[0]["id"])

        user1 = rnd("u1")
        user2 = rnd("u2")
        token1 = register_and_login(user1, f"{user1}@example.com")
        token2 = register_and_login(user2, f"{user2}@example.com")
        uid1 = decode_sub(token1)
        uid2 = decode_sub(token2)

        char1 = create_character(token1, uid1, rnd("char1"), race_id, class_id)
        char2 = create_character(token2, uid2, rnd("char2"), race_id, class_id)

        with httpx.Client(timeout=15.0, headers={"Authorization": f"Bearer {token1}"}) as c1:
            inv = c1.get(f"{BASE}/characters/{char1}/inventory")
            inv.raise_for_status()
            inv_data = inv.json()
            out["checks"]["test_wallet_bootstrap"] = inv_data.get("gold", 0) >= 100 and inv_data.get("silver", 0) >= 100
            names = {i["name"]: i["quantity"] for i in inv_data.get("inventory", [])}
            out["checks"]["starter_items_present"] = (
                names.get("Учебный меч", 0) >= 1
                and names.get("Потрепанная куртка", 0) >= 1
                and names.get("Малое зелье лечения", 0) >= 3
            )

            ensure = c1.post(f"{BASE}/characters/{char1}/starter-items/ensure")
            ensure.raise_for_status()
            out["checks"]["starter_ensure_endpoint"] = isinstance(ensure.json().get("granted", []), list)

            # Open merchant shop and buy one item
            zones = c1.get(f"{BASE}/world/zones/1", params={"character_id": char1})
            zones.raise_for_status()
            merchants = [n for n in zones.json().get("npcs", []) if n.get("type") == "merchant"]
            merchant_id = merchants[0]["npc_id"] if merchants else None
            if merchant_id:
                interact = c1.post(
                    f"{BASE}/world/interact/{char1}",
                    params={"target_type": "npc", "target_id": merchant_id, "action": "buy"},
                )
                interact.raise_for_status()
                shop_items = interact.json().get("items", [])
                out["checks"]["shop_window_payload"] = len(shop_items) >= 9
                if shop_items:
                    buy_resp = c1.post(
                        f"{BASE}/shop/buy/{char1}",
                        params={"npc_id": merchant_id, "item_id": shop_items[0]["item_id"], "quantity": 1},
                    )
                    buy_resp.raise_for_status()
                    out["checks"]["shop_buy_endpoint"] = buy_resp.json().get("success") is True
                else:
                    out["checks"]["shop_buy_endpoint"] = False
            else:
                out["checks"]["shop_window_payload"] = False
                out["checks"]["shop_buy_endpoint"] = False

            sword = next((i for i in inv_data.get("inventory", []) if i.get("name") == "Учебный меч"), None)
            if sword:
                eq = c1.post(f"{BASE}/characters/{char1}/inventory/equip", json={"item_id": sword["item_id"]})
                eq.raise_for_status()
                slot = eq.json().get("slot")
                out["checks"]["equip_to_hand_slot"] = slot in {"right_hand", "both_hands"}

                un = c1.post(f"{BASE}/characters/{char1}/inventory/unequip", json={"slot": "right_hand"})
                un.raise_for_status()
                out["checks"]["unequip_hand"] = un.json().get("status") == "unequipped"
            else:
                out["checks"]["equip_to_hand_slot"] = False
                out["checks"]["unequip_hand"] = False

            party = c1.post(
                f"{BASE}/party/create/{char1}",
                params={"party_name": "Smoke Party", "is_public": False},
            )
            party.raise_for_status()
            party_id = int(party.json()["party_id"])

            invite = c1.post(
                f"{BASE}/party/invite/{party_id}/{char2}",
                params={"inviter_id": char1},
            )
            invite.raise_for_status()
            out["checks"]["invite_sent"] = invite.json().get("success") is True

            invite_repeat = c1.post(
                f"{BASE}/party/invite/{party_id}/{char2}",
                params={"inviter_id": char1},
            )
            out["checks"]["invite_cooldown_works"] = invite_repeat.status_code == 429

        with httpx.Client(timeout=15.0, headers={"Authorization": f"Bearer {token2}"}) as c2:
            pending = c2.get(f"{BASE}/party/invitations/pending/{char2}")
            pending.raise_for_status()
            invitations = pending.json().get("invitations", [])
            out["checks"]["pending_invite_visible"] = len(invitations) >= 1
            if invitations:
                first = invitations[0]
                out["checks"]["pending_invite_fields"] = all(
                    k in first for k in ["inviter_name", "inviter_level", "inviter_location"]
                )
                rej = c2.post(
                    f"{BASE}/party/invitations/{first['invitation_id']}/reject",
                    params={"character_id": char2},
                )
                rej.raise_for_status()
                out["checks"]["reject_invite"] = rej.json().get("success") is True
            else:
                out["checks"]["pending_invite_fields"] = False
                out["checks"]["reject_invite"] = False

        out["ok"] = all(out["checks"].values())
    except Exception as exc:
        out["ok"] = False
        out["error"] = str(exc)

    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(0 if out.get("ok") else 1)


if __name__ == "__main__":
    main()
