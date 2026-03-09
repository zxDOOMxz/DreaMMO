# DreaMMO World Logic Reference

This file is the canonical gameplay reference for world navigation and zone structure.
Use these rules as the source of truth for future changes.

## 1. Coordinate Model (XYZ)

All world movement and distance checks must use 3D coordinates:
- `x`: horizontal axis
- `y`: vertical axis on map plane
- `z`: height/elevation axis

Distance formula:

`distance = sqrt((dx^2) + (dy^2) + (dz^2))`

Required entities with XYZ:
- Characters: `position_x`, `position_y`, `position_z`
- Zones: `position_x`, `position_y`, `position_z`
- NPCs: `position_x`, `position_y`, `position_z`
- Mobs: `position_x`, `position_y`, `position_z`

Interaction rule:
- Character can interact only if 3D distance <= `10` meters.

Movement rule:
- Movement vector is computed in XYZ and applied per tick by movement speed.

## 2. Zone Taxonomy (Only 3 Types)

Allowed zone types are strictly:
- `city`: settlements (city/village areas, social hubs)
- `hunting`: combat zones for mob hunting
- `resource`: gathering/mining zones (plants, wood, ore, stone)

No other runtime zone categories should be used in gameplay UI.
If legacy values appear (for example `pack`), they must be normalized to `hunting`.

## 3. Location Design Rules

- Main social gameplay belongs to `city` zones.
- Mob farming belongs to `hunting` zones only.
- Resource collection belongs to `resource` zones only.
- Zone lists in UI should group by zone type, not by fuzzy name matching.

## 4. Wolf Progression Pack

Hunting content includes wolf progression tiers:
- `Старый волк` (weak)
- `Молодой волк` (medium)
- `Матерый волк` (strong)
- `Вожак волков` (very strong, intended for party/group)

Design intent:
- Higher tier wolves have higher HP, damage, rewards, and threat.
- `Вожак волков` should be dangerous enough to motivate group play.

## 5. Asset Rule: Starter Sword Icon

Item:
- `Учебный меч`

Icon path:
- `/icons/items/Weapon/One handed sword/start_sword.png`

Frontend should resolve this icon explicitly to avoid missing icon mapping.
