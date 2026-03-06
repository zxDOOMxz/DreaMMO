# DreaMMO - Интеграция системы позиционирования и боя

## Выполненные изменения

### Backend

#### 1. Схема базы данных (`backend/database/positioning_system.sql`)
✅ Создана и применяется при старте сервера

**Добавлены таблицы:**
- `mob_spawn_zones` - зоны спавна мобов с расстояниями
- `mob_zone_spawns` - связь мобов с зонами
- `parties` - система групп
- `party_members` - участники групп
- `combat_instances` - экземпляры боёв
- `character_ability_slots` - слоты умений (5 + 1 ульта)
- `character_ability_cooldowns` - кулдауны умений
- `exp_penalty_rules` - правила пенальти опыта (Lineage 2 style)

**Добавлены поля:**
- `characters`: position_x, position_y, current_location_id, target_object_id, distance_to_target, is_moving, movement_speed, party_id
- `mobs`: position_x, position_y, spawn_zone_id, is_champion, champion_stars
- `npcs`: position_x, position_y, distance_from_center
- `abilities`: race_id, is_ultimate, tier, crit_chance_bonus, attack_speed_bonus

#### 2. API Endpoints

**Positioning Routes** (`backend/positioning_routes.py`):
- `GET /world/zones/{location_id}` - получить зоны и НПС в локации с расстояниями
- `POST /world/move/{character_id}` - начать движение к цели
- `GET /world/movement-status/{character_id}` - проверить статус движения
- `POST /world/interact/{character_id}` - взаимодействовать с объектом

**Combat Routes** (`backend/combat_routes.py`):
- `POST /combat/attack/{character_id}/{mob_id}` - атаковать моба
- `GET /combat/log/{character_id}` - получить боевой лог
- `GET /combat/stats/{character_id}` - получить боевые характеристики

**Party Routes** (`backend/party_routes.py`):
- `POST /party/create/{character_id}` - создать группу
- `POST /party/invite/{party_id}/{character_id}` - пригласить в группу
- `POST /party/leave/{character_id}` - покинуть группу
- `GET /party/info/{party_id}` - информация о группе
- `GET /party/my-party/{character_id}` - моя группа

**Ability Routes** (`backend/ability_routes.py`):
- `GET /abilities/available/{character_id}` - доступные умения
- `POST /abilities/learn/{character_id}/{ability_id}` - выучить умение
- `GET /abilities/learned/{character_id}` - выученные умения
- `POST /abilities/equip/{character_id}/{ability_id}` - экипировать умение в слот
- `POST /abilities/use/{character_id}/{ability_id}` - использовать умение
- `GET /abilities/cooldowns/{character_id}` - текущие кулдауны

#### 3. Тестовые данные

**Зоны спавна** (в `backend/main.py`):
- "Стая лис" - 75 метров, 1-2 lvl, пассивная
- "Стая волков" - 155 метров, 2-3 lvl, агрессивная
- "Лагерь гоблинов" - 200 метров, 3-4 lvl, агрессивная
- "Логово кроликов" - 30 метров, 1 lvl, пассивная

**Механики:**
- Чемпионы с ⭐ (1-3 звезды), усиленные характеристики
- Система опыта Lineage 2: пенальти за низкоуровневых мобов
- Формулы боя: урон от силы, скорость от ловкости, криты, блоки, промахи
- Взаимодействие в радиусе 10 метров

### Frontend

#### Требуется интеграция в `frontend/src/App.jsx`

**1. Добавить state переменные** (строка ~70, после existующих state):
```javascript
// Positioning & Movement
const [zones, setZones] = useState([]);
const [npcsInLocation, setNpcsInLocation] = useState([]);
const [movement, setMovement] = useState({ is_moving: false, distance_remaining: 0, target_name: '', eta_seconds: 0 });

// Combat & Party
const [combatStats, setCombatStats] = useState(null);
const [partyInfo, setPartyInfo] = useState(null);
```

**2. Добавить функции** (после handleExitWorld, see `frontend/positioning_ui_additions.js`):
- `loadLocationZones()` - загрузить зоны
- `startMovement()` - начать движение
- `checkMovementStatus()` - проверить статус движения
- `startMovementPolling()` - автообновление движения каждую секунду
- `interactWithObject()` - взаимодействие
- `attackMob()` - атака моба
- `loadCombatStats()` - загрузить боевые стаистики
- `createParty()` - создать группу
- `loadPartyInfo()` - загрузить информацию о группе
- `leaveParty()` - покинуть группу

**3. Обновить handleEnterWorld**:
```javascript
const handleEnterWorld = async () => {
  if (!selectedCharId) return;
  setInWorld(true);
  await loadZoneObjects(selectedCharId);
  await loadCharacterAbilities(selectedCharId);
  await loadMobs(selectedCharId);
  await loadQuests(selectedCharId, world?.location?.id || 1);
  await loadActiveQuests(selectedCharId);
  await loadSkillCoins(selectedCharId);
  await loadButcheringSkill(selectedCharId);
  // NEW:
  await loadLocationZones();
  await loadCombatStats();
  await loadPartyInfo();
};
```

**4. Добавить UI компоненты** (в секцию `if (inWorld)`, see `frontend/positioning_ui_components.jsx`):
- Панель движения (progress bar с ETA)
- Таблица зон и НПС с расстояниями
- Кнопки взаимодействия (зависят от расстояния)
- Боевой лог с цветовой кодировкой
- Панель боевых характеристик
- Панель группы

## Как запустить

1. **Перезапустить backend:**
```powershell
cd c:\Projects\Git\DMMO\DreaMMO\backend
python main.py
```

При старте автоматически применятся:
- `database/schema.sql`
- `database/positioning_system.sql`
- Создадутся тестовые зоны и мобы

2. **Проверить endpoints:**
```powershell
# Получить зоны в локации 1
curl "http://localhost:8000/api/world/zones/1?character_id=1"

# Начать движение к зоне
curl -X POST "http://localhost:8000/api/world/move/1?target_type=zone&target_id=1"

# Проверить статус движения
curl "http://localhost:8000/api/world/movement-status/1"

# Атаковать моба
curl -X POST "http://localhost:8000/api/combat/attack/1/2"

# Создать группу
curl -X POST "http://localhost:8000/api/party/create/1?party_name=MyParty"
```

3. **Интегрировать frontend код:**
- Скопировать state из `frontend/positioning_ui_additions.js`
- Скопировать функции из того же файла
- Скопировать JSX компоненты из `frontend/positioning_ui_components.jsx`
- Вставить в соответствующие места в `App.jsx`

## Текущее состояние

### ✅ Полностью реализовано (Backend):
1. Схема БД с позиционированием
2. Зоны спавна мобов
3. Система движения с расстояниями
4. Боевая система с формулами Lineage 2
5. Система опыта и пенальти
6. Система групп/пати
7. Система умений (5 активных + 1 ульта)
8. API endpoints для всего вышеперечисленного

### ⏳ Требует интеграции (Frontend):
1. UI для зон и расстояний
2. Счетчик движения к цели
3. Боевой лог с форматированием
4. Панель боевых характеристик
5. Панель группы

### 📝 Для доработки:
1. Система лута (таблицы есть, нужно добавить в API)
2. Магазины (НПС-продавцы)
3. Аукцион (НПС-брокер)
4. Полная система квестов с взаимодействием через НПС
5. Балансировка характеристик человеческой расы

## Новые возможности

### Пользователи могут:
1. **Видеть зоны с мобами** с точным расстоянием (75м, 155м и т.д.)
2. **Двигаться к целям** - кнопка "Идти" запускает движение со счётчиком
3. **Взаимодействовать только вблизи** - радиус 10 метров
4. **Видеть мобов в зонах** с уровнями, агрессией, чемпионскими звёздами
5. **Атаковать мобов** с реалистичным боем:
   - Шанс попадания (зависит от ловкости)
   - Шанс крита (зависит от удачи)
   - Шанс блока
   - Урон от силы
   - Скорость атаки от ловкости
6. **Получать опыт по правилам Lineage 2**:
   - Полный опыт если моб = уровню или выше
   - -25% если моб на 3-5 lvl ниже
   - -50% если на 6-10 lvl ниже
   - 0% опыта если 11+ lvl ниже (только лут)
7. **Создавать группы** и приглашать других игроков
8. **Взаимодействовать с НПС**:
   - Квестодатели - взять/сдать квест
   - Продавцы - купить/продать
   - Брокеры - аукцион
9. **Использовать умения** (5 активных + 1 ульта)

## Изменения в UI/UX

### Старое:
- Статус: "ok"
- База данных в списке
- Простая таблица объектов без расстояний
- Простой бой без механик

### Новое:
- Статус: "online"
- База данных убрана
- Таблично-иерархическое отображение:
  - Зоны (с расстоянием)
    - ↳ Мобы в зоне (уровень, агрессия, чемпионы)
  - НПС (с расстоянием и типом взаимодействия)
- Динамическое движение с ETA
- Детальный боевой лог (крит, промах, блок)
- Панель характеристик (урон, шансы, скорость)
- Система групп

## API Примеры

### Получить зоны локации:
```json
GET /api/world/zones/1?character_id=1

Response:
{
  "location_id": 1,
  "character_position": {"x": 0, "y": 0},
  "zones": [
    {
      "zone_id": 1,
      "name": "Стая лис",
      "type": "pack",
      "distance": 75.0,
      "level_range": "1-2",
      "is_aggressive": false,
      "can_interact": false,
      "mobs": [
        {
          "id": 6,
          "name": "Лис",
          "level": 1,
          "aggression": "ПАС",
          "is_champion": false,
          "stars": 0
        }
      ]
    }
  ],
  "npcs": [
    {
      "npc_id": 5,
      "name": "Охотник Раймонд",
      "type": "quest_giver",
      "level": 5,
      "distance": 0.0,
      "can_interact": true,
      "interaction_options": ["Квесты", "Сдать квест"]
    }
  ]
}
```

### Начать движение:
```json
POST /api/world/move/1?target_type=zone&target_id=1

Response:
{
  "status": "moving",
  "target_name": "Стая лис",
  "target_type": "zone",
  "distance": 75.0,
  "speed": 5.0,
  "eta_seconds": 15.0
}
```

### Атаковать моба:
```json
POST /api/combat/attack/1/2

Response:
{
  "success": true,
  "combat_log": [
    "⚔️ Герой нанёс 12 урона Волк",
    "💥 Волк нанёс 6 урона Герой"
  ],
  "damage_dealt": 12,
  "damage_taken": 6,
  "is_critical": false,
  "is_miss": false,
  "mob_killed": false,
  "exp_gained": 0,
  "gold_gained": 0,
  "character_hp": 94,
  "character_max_hp": 100,
  "mob_hp": 23,
  "mob_max_hp": 35
}
```

## Следующие шаги

1. **Немедленно:** Интегрировать frontend код в App.jsx
2. **Краткосрочно:** 
   - Добавить балансировку расы "Человек"
   - Создать подземелье/канализацию
   - Доработать систему лута
3. **Среднесрочно:**
   - Полная система торговли
   - Аукцион
   - Расширенная система квестов
4. **Долгосрочно:**
   - PvP система
   - Гильдии
   - Рейды

---

**Автор:** GitHub Copilot  
**Дата:** 2026-03-06  
**Версия:** 1.0
