export function formatRaceAdvantage(race) {
  const bonuses = race?.bonuses || {};
  const labels = {
    strength: 'Сила',
    dexterity: 'Ловкость',
    constitution: 'Выносливость',
    intelligence: 'Интеллект',
    wisdom: 'Мудрость',
    luck: 'Удача',
    health: 'HP',
    mana: 'MP',
  };

  const topBonuses = Object.entries(bonuses)
    .filter(([, value]) => typeof value === 'number' && value > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([key, value]) => `+${value} ${labels[key] || key}`);

  return topBonuses.length > 0 ? topBonuses.join(', ') : 'Без выраженных бонусов';
}
