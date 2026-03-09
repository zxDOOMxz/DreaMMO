export function resolvePassiveIcon(abilityName = '') {
  const lower = String(abilityName).toLowerCase();

  if (lower.includes('кожа') || lower.includes('щит') || lower.includes('вынослив')) {
    return '/icons/passives/defense.svg';
  }
  if (lower.includes('груз') || lower.includes('хребет')) {
    return '/icons/passives/carry.svg';
  }
  if (lower.includes('ярость') || lower.includes('удар')) {
    return '/icons/passives/damage.svg';
  }
  if (lower.includes('кров') || lower.includes('воля')) {
    return '/icons/passives/sustain.svg';
  }
  if (lower.includes('эфир') || lower.includes('маг') || lower.includes('мана')) {
    return '/icons/passives/magic.svg';
  }
  if (lower.includes('глаз') || lower.includes('танец')) {
    return '/icons/passives/agility.svg';
  }
  if (lower.includes('адапт') || lower.includes('кодекс')) {
    return '/icons/passives/adapt.svg';
  }

  return '/icons/passives/default.svg';
}

export function resolveAbilityIcon(abilityName = '', iconsIndex = {}) {
  return iconsIndex?.abilities?.[abilityName] || resolvePassiveIcon(abilityName);
}

export function resolveItemIcon(itemName = '', iconsIndex = {}) {
  const normalized = String(itemName || '').trim().toLowerCase();
  if (normalized === 'учебный меч') {
    return '/icons/items/Weapon/One handed sword/start_sword.png';
  }
  return iconsIndex?.items?.[itemName] || '';
}
