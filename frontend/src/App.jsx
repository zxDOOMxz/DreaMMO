import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import './styles.css';

function resolveApiBaseUrl() {
  const raw = (import.meta.env.VITE_API_URL || 'http://localhost:8000/api').trim();
  const noTrailingSlash = raw.replace(/\/+$/, '');

  if (/\/api$/i.test(noTrailingSlash)) {
    return noTrailingSlash;
  }

  return `${noTrailingSlash}/api`;
}

const API_URL = resolveApiBaseUrl();
const api = axios.create({ baseURL: API_URL });
function decodeJwt(token) {
  try {
    const payload = token.split('.')[1];
    const json = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(decodeURIComponent(escape(json)));
  } catch (e) {
    return null;
  }
}

function App() {
  // Server
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);

  // Auth
  const [authMode, setAuthMode] = useState('login');
  const [reg, setReg] = useState({ username: '', email: '', password: '', confirmPassword: '' });
  const [login, setLogin] = useState({ username: '', password: '' });
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [userId, setUserId] = useState(null);
  const [authLoading, setAuthLoading] = useState(false);

  // Characters / World
  const [characters, setCharacters] = useState([]);
  const [characterName, setCharacterName] = useState('');
  const [selectedCharId, setSelectedCharId] = useState(null);
  const [showCreateCharModal, setShowCreateCharModal] = useState(false);
  const [createCharLoading, setCreateCharLoading] = useState(false);

  const [world, setWorld] = useState(null);
  const [worldLoading, setWorldLoading] = useState(false);

  // World Interface
  const [inWorld, setInWorld] = useState(false);
  const [zoneObjects, setZoneObjects] = useState([]);
  const [characterRaces, setCharacterRaces] = useState([]);
  const [racesLoading, setRacesLoading] = useState(false);
  const [racesLoadError, setRacesLoadError] = useState('');
  const [selectedRaceId, setSelectedRaceId] = useState(null);
  const [characterClasses, setCharacterClasses] = useState([]);
  const [classesLoading, setClassesLoading] = useState(false);
  const [classesLoadError, setClassesLoadError] = useState('');
  const [selectedClassId, setSelectedClassId] = useState(null);
  const [characterAbilities, setCharacterAbilities] = useState([]);
  const [mobs, setMobs] = useState([]);
  const [currentCombat, setCurrentCombat] = useState(null);
  const [combatLog, setCombatLog] = useState([]);

  // Quests & Crafting
  const [availableQuests, setAvailableQuests] = useState([]);
  const [activeQuests, setActiveQuests] = useState([]);
  const [skillCoins, setSkillCoins] = useState(0);
  const [butcheringSkill, setButcheringSkill] = useState({ skill_level: 0, experience: 0, items_butchered: 0 });
  const [showQuestPanel, setShowQuestPanel] = useState(false);
  const [showButcherPanel, setShowButcherPanel] = useState(false);

  // Positioning & Movement
  const [zones, setZones] = useState([]);
  const [npcsInLocation, setNpcsInLocation] = useState([]);
  const [movement, setMovement] = useState({ is_moving: false, distance_remaining: 0, target_name: '', eta_seconds: 0 });
  
  // Combat & Party
  const [combatStats, setCombatStats] = useState(null);
  const [partyInfo, setPartyInfo] = useState(null);
  const [nearbyPlayers, setNearbyPlayers] = useState([]);
  const [pendingInvitations, setPendingInvitations] = useState([]);
  const [showInviteSentModal, setShowInviteSentModal] = useState(false);
  const [inviteSentTo, setInviteSentTo] = useState(null);
  const [showInviteReceivedModal, setShowInviteReceivedModal] = useState(false);
  const [currentInvitation, setCurrentInvitation] = useState(null);

  // Inventory & Currency
  const [inventory, setInventory] = useState([]);
  const [gold, setGold] = useState(0);
  const [honorCoins, setHonorCoins] = useState(0);

  // UI State
  const [activeTab, setActiveTab] = useState('zones'); // zones, inventory, character, abilities, quests, party

  // Derived
  const selectedCharacter = useMemo(
    () => characters.find((c) => c.id === selectedCharId) || null,
    [characters, selectedCharId]
  );

  const selectedRace = useMemo(
    () => characterRaces.find((r) => r.id === selectedRaceId) || null,
    [characterRaces, selectedRaceId]
  );

  const formatRaceAdvantage = (race) => {
    const bonuses = race?.bonuses || {};
    const labels = {
      strength: 'Сила',
      dexterity: 'Ловкость',
      constitution: 'Выносливость',
      intelligence: 'Интеллект',
      wisdom: 'Мудрость',
      luck: 'Удача',
      health: 'HP',
      mana: 'MP'
    };

    const topBonuses = Object.entries(bonuses)
      .filter(([, value]) => typeof value === 'number' && value > 0)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([key, value]) => `+${value} ${labels[key] || key}`);

    return topBonuses.length > 0 ? topBonuses.join(', ') : 'Без выраженных бонусов';
  };

  const getPassiveIcon = (abilityName = '') => {
    const lower = abilityName.toLowerCase();

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
  };

  // Init
  useEffect(() => {
    checkHealth();
    loadCharacterRaces();
    loadCharacterClasses();
    if (token) {
      api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      const payload = decodeJwt(token);
      if (payload && payload.sub) setUserId(parseInt(payload.sub, 10));
    }
  }, []);

  // When userId available, load characters
  useEffect(() => {
    if (!userId) return;
    (async () => {
      const list = await loadCharacters();
      let id = selectedCharId;
      if (!id && list && list.length > 0) id = list[0].id;
      if (id) {
        setSelectedCharId(id);
        await loadWorld(id);
      }
    })();
  }, [userId]);

  // Poll for pending invitations when in world
  useEffect(() => {
    if (!inWorld || !selectedCharId) return;
    
    const interval = setInterval(() => {
      loadPendingInvitations();
      loadNearbyPlayers();
    }, 5000); // Check every 5 seconds
    
    return () => clearInterval(interval);
  }, [inWorld, selectedCharId]);

  // Server health
  const checkHealth = async () => {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);
      
      const { data } = await api.get(`/health`, {
        signal: controller.signal
      });
      clearTimeout(timeoutId);
      setHealth(data);
      setLoading(false);
      setError(null);
    } catch (err) {
      setError(`Ошибка подключения к серверу (${API_URL}). Проверьте, запущен ли бэкенд на http://localhost:8000`);
      setLoading(false);
      setHealth(null);
    }
  };

  // Auth handlers
  const handleRegister = async (e) => {
    e.preventDefault();
    if (!reg.username || !reg.email || !reg.password) {
      return setError('Заполните все поля');
    }
    if (reg.password !== reg.confirmPassword) {
      return setError('Пароли не совпадают');
    }
    setAuthLoading(true);
    try {
      await api.post('/auth/register', {
        username: reg.username,
        email: reg.email,
        password: reg.password
      });
      setError(null);
      setAuthMode('login');
      setReg({ username: '', email: '', password: '', confirmPassword: '' });
    } catch (e) {
      setError(`Ошибка регистрации: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!login.username || !login.password) {
      return setError('Введите логин и пароль');
    }
    setAuthLoading(true);
    try {
      const { data } = await api.post('/auth/login', login);
      const t = data?.access_token;
      if (!t) throw new Error('Нет токена в ответе');
      localStorage.setItem('token', t);
      setToken(t);
      api.defaults.headers.common['Authorization'] = `Bearer ${t}`;
      const payload = decodeJwt(t);
      if (payload && payload.sub) {
        setUserId(parseInt(payload.sub, 10));
      }
      setError(null);
      setLogin({ username: '', password: '' });
    } catch (e) {
      setError(`Ошибка входа: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      if (userId) {
        try {
          await api.post('/auth/logout', null, { params: { user_id: userId } });
        } catch {}
      }
    } catch {}
    localStorage.removeItem('token');
    delete api.defaults.headers.common['Authorization'];
    setToken('');
    setUserId(null);
    setCharacters([]);
    setSelectedCharId(null);
    setWorld(null);
    setError(null);
    setShowCreateCharModal(false);
    await checkHealth();
  };

  // Characters
  const loadCharacters = async () => {
    if (!userId) return [];
    try {
      const { data } = await api.get('/characters', { params: { user_id: userId } });
      const list = data?.characters || [];
      setCharacters(list);
      if (list.length > 0 && !list.find((c) => c.id === selectedCharId)) {
        setSelectedCharId(list[0].id);
      }
      return list;
    } catch (e) {
      console.error('loadCharacters error:', e);
      return [];
    }
  };

  const handleCreateCharacter = async (e) => {
    e.preventDefault();
    if (!userId) return setError('Сначала выполните вход');
    const name = characterName.trim();
    if (!name) return setError('Введите имя персонажа');
    if (!selectedRaceId) return setError('Выберите расу персонажа');
    if (!selectedClassId) return setError('Выберите класс персонажа');

    setCreateCharLoading(true);
    try {
      const { data } = await api.post('/characters/create', { 
        user_id: userId, 
        name,
        race_id: selectedRaceId,
        class_id: selectedClassId 
      });
      const created = data?.data?.character;
      await loadCharacters();
      if (created?.id) {
        setSelectedCharId(created.id);
        await loadWorld(created.id);
      }
      setCharacterName('');
      setSelectedRaceId(null);
      setSelectedClassId(null);
      setShowCreateCharModal(false);
      setError(null);
    } catch (e) {
      const detail = e?.response?.data?.detail || e.message;
      setError(`Ошибка создания персонажа: ${detail}`);
    } finally {
      setCreateCharLoading(false);
    }
  };

  const handleDeleteCharacter = async (charId) => {
    if (!confirm('Вы уверены, что хотите удалить этого персонажа? Это действие нельзя отменить.')) {
      return;
    }
    
    try {
      await api.delete(`/characters/${charId}`);
      await loadCharacters();
      if (selectedCharId === charId) {
        setSelectedCharId(null);
        setWorld(null);
      }
      setError(null);
    } catch (e) {
      setError(`Ошибка удаления: ${e?.response?.data?.detail || e.message}`);
    }
  };

  // World
  const loadWorld = async (charId) => {
    setWorldLoading(true);
    try {
      const { data } = await api.get('/world/current', { params: { character_id: charId } });
      setWorld(data);
      setError(null);
    } catch (e) {
      setWorld(null);
      console.warn('world load failed:', e);
    } finally {
      setWorldLoading(false);
    }
  };

  const loadZoneObjects = async (charId) => {
    try {
      const { data } = await api.get('/world/objects', { params: { character_id: charId } });
      setZoneObjects(data?.objects || []);
      setError(null);
    } catch (e) {
      setZoneObjects([]);
      console.warn('zone objects load failed:', e);
    }
  };

  const loadCharacterRaces = async () => {
    setRacesLoading(true);
    setRacesLoadError('');
    try {
      const { data } = await api.get('/races');
      setCharacterRaces(data?.races || []);
      if (!data?.races?.length) {
        setRacesLoadError('Расы не найдены на сервере');
      }
    } catch (e) {
      console.warn('races load failed:', e);
      setCharacterRaces([]);
      setRacesLoadError(`Не удалось загрузить расы: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setRacesLoading(false);
    }
  };

  const loadCharacterClasses = async () => {
    setClassesLoading(true);
    setClassesLoadError('');
    try {
      const { data } = await api.get('/classes');
      setCharacterClasses(data?.classes || []);
      if (!data?.classes?.length) {
        setClassesLoadError('Классы не найдены на сервере');
      }
    } catch (e) {
      console.warn('classes load failed:', e);
      setCharacterClasses([]);
      setClassesLoadError(`Не удалось загрузить классы: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setClassesLoading(false);
    }
  };

  const loadCharacterAbilities = async (charId) => {
    try {
      const { data } = await api.get(`/characters/${charId}/abilities`);
      setCharacterAbilities(data?.abilities || []);
    } catch (e) {
      console.warn('abilities load failed:', e);
    }
  };

  const loadMobs = async (charId) => {
    try {
      const { data } = await api.get('/world/mobs', { params: { character_id: charId } });
      setMobs(data?.mobs || []);
    } catch (e) {
      console.warn('mobs load failed:', e);
    }
  };

  const loadQuests = async (charId, locationId) => {
    try {
      const { data } = await api.get('/quests/available', { params: { character_id: charId, location_id: locationId } });
      setAvailableQuests(data?.quests || []);
    } catch (e) {
      console.warn('quests load failed:', e);
    }
  };

  const loadActiveQuests = async (charId) => {
    try {
      const { data } = await api.get(`/quests/${charId}/active`);
      setActiveQuests(data?.quests || []);
    } catch (e) {
      console.warn('active quests load failed:', e);
    }
  };

  const loadSkillCoins = async (charId) => {
    try {
      const { data } = await api.get(`/skill_coins/${charId}`);
      setSkillCoins(data?.balance || 0);
    } catch (e) {
      console.warn('skill coins load failed:', e);
    }
  };

  const loadButcheringSkill = async (charId) => {
    try {
      const { data } = await api.get(`/butchering/${charId}/skill`);
      setButcheringSkill(data);
    } catch (e) {
      console.warn('butchering skill load failed:', e);
    }
  };

  const acceptQuest = async (questId) => {
    if (!selectedCharId) return;
    try {
      const { data } = await api.post(`/quests/${questId}/accept`, null, { params: { character_id: selectedCharId } });
      setError(null);
      const { data: currentWorld } = await api.get('/world/current', { params: { character_id: selectedCharId } });
      await loadQuests(selectedCharId, currentWorld?.location?.id || 1);
      await loadActiveQuests(selectedCharId);
    } catch (e) {
      setError(`Ошибка принятия квеста: ${e?.response?.data?.detail || e.message}`);
    }
  };

  const butcherMob = async (mobId) => {
    if (!selectedCharId) return;
    try {
      const { data } = await api.post(`/butchering/butcher_mob`, null, { params: { character_id: selectedCharId, mob_id: mobId } });
      setError(null);
      setCombatLog([...combatLog, `✅ ${data.obtained_items.map(i => `${i.name}x${i.quantity}`).join(', ')}`]);
      await loadButcheringSkill(selectedCharId);
    } catch (e) {
      setError(`Ошибка разделки: ${e?.response?.data?.detail || e.message}`);
    }
  };

  const completeQuest = async (questId) => {
    if (!selectedCharId) return;
    try {
      const { data } = await api.post(`/quests/${selectedCharId}/complete`, null, { params: { quest_id: questId } });
      setError(null);
      await loadActiveQuests(selectedCharId);
      await loadSkillCoins(selectedCharId);
      setCombatLog([...combatLog, `🎉 Квест завершен! +${data.skill_coins_reward} коинов`]);
    } catch (e) {
      setError(`Ошибка завершения квеста: ${e?.response?.data?.detail || e.message}`);
    }
  };

  const startCombat = async (mobId) => {
    if (!selectedCharId) return;
    try {
      // For now, simulate combat start
      const mob = mobs.find(m => m.id === mobId);
      if (mob) {
        setCurrentCombat({
          mob: mob,
          character_health: selectedCharacter?.health_points || 100,
          mob_health: mob.health,
          turn: 'character',
          status: 'active'
        });
        setCombatLog([`Бой начат с ${mob.name}!`]);
      }
    } catch (e) {
      setError(`Ошибка начала боя: ${e?.response?.data?.detail || e.message}`);
    }
  };

  const useAbility = async (abilityId) => {
    if (!currentCombat || !selectedCharId) return;
    
    try {
      const ability = characterAbilities.find(a => a.id === abilityId);
      if (!ability) return;
      
      // Simulate ability use
      let damage = 0;
      let healing = 0;
      let newMobHealth = currentCombat.mob_health;
      let newCharHealth = currentCombat.character_health;
      
      if (ability.effect_type === 'damage') {
        damage = Math.floor(Math.random() * (ability.damage_max - ability.damage_min + 1)) + ability.damage_min;
        newMobHealth = Math.max(0, currentCombat.mob_health - damage);
      } else if (ability.effect_type === 'heal') {
        healing = ability.healing;
        newCharHealth = Math.min(selectedCharacter?.max_health_points || 100, currentCombat.character_health + healing);
      }
      
      const newLog = [...combatLog];
      newLog.push(`${selectedCharacter?.name} использует ${ability.name}${damage > 0 ? ` и наносит ${damage} урона!` : healing > 0 ? ` и восстанавливает ${healing} здоровья!` : '!'}`);
      
      if (newMobHealth <= 0) {
        newLog.push(`${currentCombat.mob.name} побежден!`);
        setCurrentCombat(null);
        // Award experience
        newLog.push(`Получено ${currentCombat.mob.exp_reward} опыта и ${currentCombat.mob.gold_reward} золота!`);
      } else {
        // Mob counterattack
        const mobDamage = Math.floor(Math.random() * (currentCombat.mob.damage_max - currentCombat.mob.damage_min + 1)) + currentCombat.mob.damage_min;
        newCharHealth = Math.max(0, newCharHealth - mobDamage);
        newLog.push(`${currentCombat.mob.name} атакует и наносит ${mobDamage} урона!`);
        
        if (newCharHealth <= 0) {
          newLog.push(`${selectedCharacter?.name} побежден!`);
          setCurrentCombat(null);
        }
      }
      
      setCombatLog(newLog);
      if (currentCombat) {
        setCurrentCombat({
          ...currentCombat,
          mob_health: newMobHealth,
          character_health: newCharHealth
        });
      }
      
    } catch (e) {
      setError(`Ошибка использования умения: ${e?.response?.data?.detail || e.message}`);
    }
  };

  const handleEnterWorld = async () => {
    if (!selectedCharId) return;
    setInWorld(true);
    try {
      // First get current location
      const { data: worldData } = await api.get('/world/current', { params: { character_id: selectedCharId } });
      const locationId = worldData?.location?.id || 1;
      setWorld(worldData);
      setAvailableQuests([]);
      setShowQuestPanel(false);
      
      // Load all data
      await loadLocationZones(locationId);
      await loadCharacterAbilities(selectedCharId);
      await loadCombatStats();
      await loadPartyInfo();
      await loadNearbyPlayers();
      await loadPendingInvitations();
      await loadActiveQuests(selectedCharId);
      await loadSkillCoins(selectedCharId);
      await loadButcheringSkill(selectedCharId);
      await loadInventory();
    } catch (err) {
      setError('Ошибка входа в мир: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleExitWorld = () => {
    setInWorld(false);
    setZones([]);
    setNpcsInLocation([]);
    setAvailableQuests([]);
    setShowQuestPanel(false);
    setMovement({ is_moving: false, distance_remaining: 0, target_name: '', eta_seconds: 0 });
    setZoneObjects([]);
    setNearbyPlayers([]);
    setPendingInvitations([]);
    setShowInviteSentModal(false);
    setShowInviteReceivedModal(false);
    setCurrentInvitation(null);
  };

  // ===== POSITIONING FUNCTIONS =====

  const loadLocationZones = async (locationId) => {
    if (!selectedCharId || !locationId) return;
    try {
      const { data } = await api.get(`/world/zones/${locationId}?character_id=${selectedCharId}`);
      setZones(data.zones || []);
      setNpcsInLocation(data.npcs || []);
      setError(null);
    } catch (err) {
      console.error('Failed to load zones:', err);
      setZones([]);
      setNpcsInLocation([]);
    }
  };

  const startMovement = async (targetType, targetId, targetName) => {
    try {
      const { data } = await api.post(`/world/move/${selectedCharId}`, null, {
        params: { target_type: targetType, target_id: targetId }
      });
      setMovement({
        is_moving: true,
        distance_remaining: data.distance,
        target_name: targetName,
        eta_seconds: data.eta_seconds
      });
      startMovementPolling();
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка движения');
    }
  };

  let movementIntervalId = null;
  const startMovementPolling = () => {
    if (movementIntervalId) clearInterval(movementIntervalId);
    movementIntervalId = setInterval(async () => {
      const stillMoving = await checkMovementStatus();
      if (!stillMoving) {
        clearInterval(movementIntervalId);
        movementIntervalId = null;
      }
    }, 1000);
  };

  const checkMovementStatus = async () => {
    if (!selectedCharId) return false;
    try {
      const { data } = await api.get(`/world/movement-status/${selectedCharId}`);
      setMovement({
        is_moving: data.is_moving,
        distance_remaining: data.distance_remaining || 0,
        target_name: data.target_name || '',
        eta_seconds: data.eta_seconds || 0,
        arrived: data.arrived || false
      });
      
      if (data.arrived) {
        setError(`✓ Прибыли к цели: ${data.target_name}`);
        // Get current location and reload zones
        const { data: locData } = await api.get('/world/current', { params: { character_id: selectedCharId } });
        const locId = locData?.location?.id || 1;
        await loadLocationZones(locId);
        return false;
      }
      return data.is_moving;
    } catch (err) {
      return false;
    }
  };

  const interactWithObject = async (targetType, targetId, action) => {
    try {
      const { data } = await api.post(`/world/interact/${selectedCharId}`, null, {
        params: { target_type: targetType, target_id: targetId, action }
      });
      
      if (data.success) {
        setError(data.message || 'Взаимодействие успешно');
        if (data.action === 'quest_list' && data.quests) {
          setAvailableQuests(data.quests);
          setShowQuestPanel(true);
        }
      } else {
        setError(data.message);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка взаимодействия');
    }
  };

  // ===== COMBAT FUNCTIONS =====

  const attackMob = async (mobId) => {
    try {
      const { data } = await api.post(`/combat/attack/${selectedCharId}/${mobId}`);
      
      const newLog = [...combatLog];
      data.combat_log.forEach(msg => newLog.unshift(msg));
      setCombatLog(newLog.slice(0, 50));
      
      if (data.mob_killed) {
        setError(`☠️ +${data.exp_gained} опыта, +${data.gold_gained} золота`);
        await loadLocationZones();
        await loadCharacters();
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка атаки');
    }
  };

  const loadCombatStats = async () => {
    if (!selectedCharId) return;
    try {
      const { data } = await api.get(`/combat/stats/${selectedCharId}`);
      setCombatStats(data);
    } catch (err) {
      console.error('Failed to load combat stats:', err);
    }
  };

  // ===== PARTY FUNCTIONS =====

  const createParty = async (partyName) => {
    try {
      await api.post(`/party/create/${selectedCharId}`, null, {
        params: { party_name: partyName, is_public: false }
      });
      setError('✓ Группа создана');
      await loadPartyInfo();
      await loadNearbyPlayers();
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка создания группы');
    }
  };

  const loadPartyInfo = async () => {
    if (!selectedCharId) return;
    try {
      const { data } = await api.get(`/party/my-party/${selectedCharId}`);
      setPartyInfo(data.in_party ? data : null);
    } catch (err) {
      console.error('Failed to load party:', err);
      setPartyInfo(null);
    }
  };

  const leaveParty = async () => {
    try {
      await api.post(`/party/leave/${selectedCharId}`);
      setPartyInfo(null);
      setError('✓ Покинули группу');
      await loadNearbyPlayers();
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка выхода из группы');
    }
  };

  const loadNearbyPlayers = async () => {
    if (!selectedCharId) return;
    try {
      const { data } = await api.get(`/party/nearby-players/${selectedCharId}`);
      setNearbyPlayers(data.nearby_players || []);
    } catch (err) {
      console.error('Failed to load nearby players:', err);
      setNearbyPlayers([]);
    }
  };

  const loadPendingInvitations = async () => {
    if (!selectedCharId) return;
    try {
      const { data } = await api.get(`/party/invitations/pending/${selectedCharId}`);
      setPendingInvitations(data.invitations || []);
      
      // Show modal for first pending invitation
      if (data.invitations && data.invitations.length > 0 && !showInviteReceivedModal) {
        setCurrentInvitation(data.invitations[0]);
        setShowInviteReceivedModal(true);
      }
    } catch (err) {
      console.error('Failed to load invitations:', err);
      setPendingInvitations([]);
    }
  };

  const inviteToParty = async (targetCharacterId, targetCharacterName) => {
    if (!partyInfo) {
      setError('Сначала создайте группу');
      return;
    }
    
    try {
      const { data } = await api.post(
        `/party/invite/${partyInfo.party_id}/${targetCharacterId}`,
        null,
        { params: { inviter_id: selectedCharId } }
      );
      
      setInviteSentTo(targetCharacterName);
      setShowInviteSentModal(true);
      setError('✓ Приглашение отправлено');
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка отправки приглашения');
    }
  };

  const acceptInvitation = async (invitationId) => {
    try {
      await api.post(`/party/invitations/${invitationId}/accept`, null, {
        params: { character_id: selectedCharId }
      });
      
      setShowInviteReceivedModal(false);
      setCurrentInvitation(null);
      setError('✓ Вы присоединились к группе');
      
      await loadPartyInfo();
      await loadPendingInvitations();
      await loadNearbyPlayers();
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка принятия приглашения');
      setShowInviteReceivedModal(false);
      await loadPendingInvitations();
    }
  };

  const rejectInvitation = async (invitationId) => {
    try {
      await api.post(`/party/invitations/${invitationId}/reject`, null, {
        params: { character_id: selectedCharId }
      });
      
      setShowInviteReceivedModal(false);
      setCurrentInvitation(null);
      setError('Приглашение отклонено');
      
      await loadPendingInvitations();
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка отклонения приглашения');
      setShowInviteReceivedModal(false);
      await loadPendingInvitations();
    }
  };

  // ===== INVENTORY & CURRENCY FUNCTIONS =====

  const loadInventory = async () => {
    if (!selectedCharId) return;
    try {
      const { data } = await api.get(`/characters/${selectedCharId}/inventory`);
      setInventory(data?.inventory || []);
      setGold(data?.gold ?? selectedCharacter?.gold ?? 0);
      
      // Load honor coins (renamed from skill_coins)
      const coins = await loadSkillCoins(selectedCharId);
      setHonorCoins(coins);
    } catch (err) {
      console.error('Failed to load inventory:', err);
    }
  };

  // Group zones by type (EVE Online style)
  const groupedZones = useMemo(() => {
    const groups = {
      city: { name: 'Город', icon: '🏛️', zones: [] },
      hunting: { name: 'Охота', icon: '⚔️', zones: [] },
      gathering: { name: 'Сбор ресурсов', icon: '🌾', zones: [] },
      mining: { name: 'Добыча', icon: '⛏️', zones: [] },
      dungeon: { name: 'Подземелья', icon: '🏰', zones: [] },
      other: { name: 'Прочее', icon: '📍', zones: [] }
    };

    zones.forEach(zone => {
      const name = (zone.name || zone.zone_name || '').toLowerCase();
      if (name.includes('площадь') || name.includes('город') || name.includes('таверна')) {
        groups.city.zones.push(zone);
      } else if (name.includes('охотничь') || name.includes('волк') || name.includes('медвед')) {
        groups.hunting.zones.push(zone);
      } else if (name.includes('лес') || name.includes('поляна') || name.includes('трав')) {
        groups.gathering.zones.push(zone);
      } else if (name.includes('гор') || name.includes('руд') || name.includes('камен') || name.includes('шахт')) {
        groups.mining.zones.push(zone);
      } else if (name.includes('данж') || name.includes('подземель') || name.includes('пещер')) {
        groups.dungeon.zones.push(zone);
      } else {
        groups.other.zones.push(zone);
      }
    });

    return Object.entries(groups).filter(([_, group]) => group.zones.length > 0);
  }, [zones]);

  if (loading) {
    return (
      <div className="app loading-screen">
        <div className="loader"></div>
        <h2>Загрузка Codex Online...</h2>
      </div>
    );
  }

  if (inWorld) {
    const hpPercent = selectedCharacter ? (selectedCharacter.health_points / selectedCharacter.max_health_points) * 100 : 100;
    const mpPercent = selectedCharacter ? (selectedCharacter.magic_points / selectedCharacter.max_magic_points) * 100 : 100;

    // Tab content render helper
    const renderTabContent = () => {
      switch(activeTab) {
        case 'zones':
          return (
            <div>
              {groupedZones.map(([type, group]) => (
                <div key={type} className="zone-group">
                  <div className="zone-group-header">
                    <span className="zone-group-icon">{group.icon}</span>
                    <span className="zone-group-title">{group.name}</span>
                    <span className="zone-group-count">{group.zones.length}</span>
                  </div>
                  <div className="zone-list">
                    {group.zones.map((zone) => (
                      <div key={zone.zone_id} className="zone-item">
                        <div className="zone-info">
                          <div className="zone-name">{zone.name}</div>
                          <div className="zone-details">
                            <span>{zone.is_aggressive ? '⚔️ Агрессивная' : '🌿 Мирная'}</span>
                            <span>📏 {zone.distance}м</span>
                            <span>⭐ {zone.level_range}</span>
                          </div>
                        </div>
                        <div className="zone-actions">
                          {zone.can_interact ? (
                            <button className="btn-small btn-success" onClick={() => interactWithObject('zone', zone.zone_id, 'enter')}>
                              Войти
                            </button>
                          ) : (
                            <button className="btn-small" onClick={() => startMovement('zone', zone.zone_id, zone.name)}>
                              Идти
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}

              {/* NPCs Section */}
              {npcsInLocation.length > 0 && (
                <div className="zone-group" style={{marginTop: '30px'}}>
                  <div className="zone-group-header">
                    <span className="zone-group-icon">👥</span>
                    <span className="zone-group-title">НПС и игроки</span>
                    <span className="zone-group-count">{npcsInLocation.length}</span>
                  </div>
                  <div className="zone-list">
                    {npcsInLocation.map((npc) => {
                      const npcId = npc.npc_id;
                      const npcType = npc.type;
                      const npcAction = npcType === 'quest_giver'
                        ? 'quest'
                        : npcType === 'merchant'
                          ? 'buy'
                          : npcType === 'broker'
                            ? 'auction'
                            : null;

                      return (
                        <div key={npcId} className="zone-item">
                          <div className="zone-info">
                            <div className="zone-name">👤 {npc.name}</div>
                            <div className="zone-details">
                              <span>📏 {npc.distance}м</span>
                              {npc.interaction_options?.length > 0 && <span>{npc.interaction_options.join(', ')}</span>}
                            </div>
                          </div>
                          <div className="zone-actions">
                            {npc.can_interact && npcAction ? (
                              <button className="btn-small btn-primary" onClick={() => interactWithObject('npc', npcId, npcAction)}>
                                {npcAction === 'quest' ? 'Квесты' : npcAction === 'buy' ? 'Купить' : 'Аукцион'}
                              </button>
                            ) : (
                              <button className="btn-small" onClick={() => startMovement('npc', npcId, npc.name)}>
                                Идти
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          );

        case 'inventory':
          return (
            <div>
              <div style={{marginBottom: '20px'}}>
                <h3>💰 Валюта</h3>
                <div style={{display: 'flex', gap: '15px', marginTop: '10px'}}>
                  <div className="currency-item">
                    <span>🪙 Золото:</span>
                    <strong>{gold}</strong>
                  </div>
                  <div className="currency-item">
                    <span>🎖️ Коины Чести:</span>
                    <strong>{honorCoins}</strong>
                  </div>
                </div>
              </div>

              <h3>🎒 Инвентарь</h3>
              <div className="inventory-grid">
                {Array.from({length: 40}).map((_, idx) => {
                  const item = inventory[idx];
                  return (
                    <div key={idx} className={`inventory-slot ${!item ? 'empty' : ''}`}>
                      {item ? (
                        <>
                          <div className="item-icon">{item.icon || '📦'}</div>
                          {item.count > 1 && <div className="item-count">{item.count}</div>}
                        </>
                      ) : (
                        <div style={{opacity: 0.3}}>□</div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );

        case 'character':
          return (
            <div>
              {combatStats && (
                <div>
                  <h3>⚔️ Боевые характеристики</h3>
                  <table className="compact-table">
                    <tbody>
                      <tr><td>Урон:</td><td>{combatStats.combat.damage_min}-{combatStats.combat.damage_max}</td></tr>
                      <tr><td>Защита:</td><td>{combatStats.combat.armor_value}</td></tr>
                      <tr><td>Крит. шанс:</td><td>{combatStats.combat.crit_chance}%</td></tr>
                      <tr><td>Шанс блока:</td><td>{combatStats.combat.block_chance}%</td></tr>
                      <tr><td>Скорость атаки:</td><td>{combatStats.combat.attack_speed} атак/мин</td></tr>
                    </tbody>
                  </table>

                  <h3 style={{marginTop: '20px'}}>📊 Характеристики</h3>
                  <table className="compact-table">
                    <tbody>
                      <tr><td>💪 Сила:</td><td>{combatStats.stats.strength}</td></tr>
                      <tr><td>🏃 Ловкость:</td><td>{combatStats.stats.dexterity}</td></tr>
                      <tr><td>🛡️ Выносливость:</td><td>{combatStats.stats.constitution}</td></tr>
                      <tr><td>🎲 Удача:</td><td>{combatStats.stats.luck}</td></tr>
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          );

        case 'abilities':
          return (
            <div>
              <h3>⚡ Умения</h3>
              <div className="abilities-grid" style={{marginTop: '15px'}}>
                {characterAbilities.filter(a => a.type === 'skill').map((ability) => (
                  <button 
                    key={ability.id}
                    className="btn-action"
                    onClick={() => useAbility(ability.id)}
                    disabled={currentCombat === null || ability.cooldown_remaining > 0}
                  >
                    ⚡ {ability.name}<br/>
                    <small>{ability.mana_cost} маны</small>
                  </button>
                ))}
              </div>

              <h3 style={{marginTop: '20px'}}>🔮 Заклинания</h3>
              <div className="abilities-grid" style={{marginTop: '15px'}}>
                {characterAbilities.filter(a => a.type === 'spell').map((ability) => (
                  <button 
                    key={ability.id}
                    className="btn-action"
                    onClick={() => useAbility(ability.id)}
                    disabled={currentCombat === null || ability.cooldown_remaining > 0}
                  >
                    🔮 {ability.name}<br/>
                    <small>{ability.mana_cost} маны</small>
                  </button>
                ))}
              </div>

              <h3 style={{marginTop: '20px'}}>💎 Коины Умений</h3>
              <p>Доступно: <strong>{honorCoins}</strong> коинов</p>
              
              <h3 style={{marginTop: '20px'}}>🔪 Разделка</h3>
              <table className="compact-table">
                <tbody>
                  <tr><td>Уровень:</td><td>{butcheringSkill.skill_level}</td></tr>
                  <tr><td>Опыт:</td><td>{butcheringSkill.experience}/100</td></tr>
                  <tr><td>Разобрано:</td><td>{butcheringSkill.items_butchered}</td></tr>
                </tbody>
              </table>
            </div>
          );

        case 'quests':
          return (
            <div>
              <h3>📜 Доступные квесты</h3>
              {availableQuests.length === 0 ? (
                <p style={{color: '#888', marginTop: '10px'}}>Нет доступных квестов. Поговорите с НПС с пометкой "Квесты".</p>
              ) : (
                <div className="quests-list">
                  {availableQuests.map((quest) => (
                    <div key={quest.id} className="quest-card">
                      <div className="quest-info">
                        <h4>{quest.title}</h4>
                        <p>{quest.description}</p>
                        <div className="quest-rewards">
                          <span>⭐ Опыт: {quest.reward_experience}</span>
                          <span>💰 Золото: {quest.reward_gold}</span>
                        </div>
                      </div>
                      <button className="btn btn-success" onClick={() => acceptQuest(quest.id)}>
                        Принять
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <h3 style={{marginTop: '30px'}}>📖 Активные квесты</h3>
              {activeQuests.length === 0 ? (
                <p style={{color: '#888', marginTop: '10px'}}>Нет активных квестов</p>
              ) : (
                <div className="quests-list">
                  {activeQuests.map((quest) => (
                    <div key={quest.quest_id} className="quest-card active">
                      <div className="quest-info">
                        <h4>{quest.title}</h4>
                        <p>{quest.description}</p>
                      </div>
                      <button className="btn btn-success" onClick={() => completeQuest(quest.quest_id)}>
                        Завершить
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );

        case 'party':
          return (
            <div>
              {!partyInfo ? (
                <div>
                  <p style={{marginBottom: '15px', color: '#aaa'}}>Вы не в группе</p>
                  <button 
                    className="btn btn-primary" 
                    onClick={() => createParty(`Группа ${selectedCharacter?.name}`)}
                    style={{width: '100%'}}
                  >
                    Создать группу
                  </button>
                </div>
              ) : (
                <div>
                  <h3>{partyInfo.party_name}</h3>
                  <p style={{color: '#aaa', marginBottom: '15px'}}>
                    Лидер: {partyInfo.leader.name} | {partyInfo.current_members}/{partyInfo.max_members}
                  </p>
                  
                  {partyInfo.members.map((member) => {
                    const mHpPercent = (member.hp / member.max_hp) * 100;
                    const mMpPercent = member.max_mp > 0 ? (member.mp / member.max_mp) * 100 : 0;
                    return (
                      <div key={member.character_id} style={{
                        padding: '10px',
                        background: '#1a1a1a',
                        borderRadius: '4px',
                        border: '1px solid #333',
                        marginBottom: '10px'
                      }}>
                        <div style={{display: 'flex', justifyContent: 'space-between', marginBottom: '8px'}}>
                          <span>
                            {member.role === 'leader' ? '👑 ' : ''}
                            <strong>{member.name}</strong>
                          </span>
                          <span style={{color: '#aaa'}}>Lvl {member.level}</span>
                        </div>
                        <div style={{marginBottom: '5px'}}>
                          <div className="stat-bar">
                            <div className="stat-bar-fill hp" style={{width: `${mHpPercent}%`}}></div>
                            <span className="stat-bar-text">{member.hp}/{member.max_hp}</span>
                          </div>
                        </div>
                        {member.max_mp > 0 && (
                          <div>
                            <div className="stat-bar">
                              <div className="stat-bar-fill mp" style={{width: `${mMpPercent}%`}}></div>
                              <span className="stat-bar-text">{member.mp}/{member.max_mp}</span>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}

                  {partyInfo.leader.id === selectedCharId && nearbyPlayers.filter(p => !p.in_party).length > 0 && (
                    <div style={{marginTop: '20px'}}>
                      <h4>Пригласить:</h4>
                      {nearbyPlayers.filter(p => !p.in_party).map((player) => (
                        <div key={player.character_id} style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          padding: '8px',
                          background: '#1a1a1a',
                          borderRadius: '4px',
                          marginTop: '8px'
                        }}>
                          <div>
                            <strong>{player.name}</strong>
                            <div style={{fontSize: '0.85em', color: '#aaa'}}>
                              Lvl {player.level} • {player.race} {player.class}
                            </div>
                          </div>
                          <button 
                            className="btn-small btn-primary"
                            onClick={() => inviteToParty(player.character_id, player.name)}
                          >
                            Пригласить
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  <button 
                    className="btn btn-danger" 
                    onClick={leaveParty}
                    style={{width: '100%', marginTop: '15px'}}
                  >
                    Покинуть группу
                  </button>
                </div>
              )}
            </div>
          );

        default:
          return <div>Выберите вкладку</div>;
      }
    };

    return (
      <div className="app">
        <header className="header">
          <div className="header-content">
            <div className="logo">
              <h1>Мир Codex Online</h1>
              <p>{selectedCharacter?.name} - {world?.location?.name}</p>
            </div>
            <div className="user-info">
              <button onClick={handleExitWorld} className="btn-secondary">⬅️ Назад к персонажам</button>
            </div>
          </div>
        </header>

        {error && (
          <div className="error-banner">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="error-close">✕</button>
          </div>
        )}

        {/* Compact Top Bar with Character Stats and Currency */}
        <div className="world-top-bar">
          <div className="character-stats-compact">
            <div className="stat-compact">
              <span>❤️</span>
              <div className="stat-bar">
                <div className="stat-bar-fill hp" style={{width: `${hpPercent}%`}}></div>
                <span className="stat-bar-text">{selectedCharacter?.health_points}/{selectedCharacter?.max_health_points}</span>
              </div>
            </div>
            <div className="stat-compact">
              <span>💧</span>
              <div className="stat-bar">
                <div className="stat-bar-fill mp" style={{width: `${mpPercent}%`}}></div>
                <span className="stat-bar-text">{selectedCharacter?.magic_points}/{selectedCharacter?.max_magic_points}</span>
              </div>
            </div>
            <div className="stat-compact">
              <span>⭐ Lvl {selectedCharacter?.level}</span>
            </div>
          </div>

          <div className="currency-compact">
            <div className="currency-item">
              <span>🪙</span>
              <strong>{gold}</strong>
            </div>
            <div className="currency-item">
              <span>🎖️</span>
              <strong>{honorCoins}</strong>
            </div>
          </div>
        </div>

        {/* Movement Status (if moving) */}
        {movement.is_moving && (
          <div style={{background: '#2a4a2a', padding: '10px 20px', borderBottom: '2px solid #4CAF50'}}>
            <strong>🏃 Движение:</strong> {movement.target_name} • {movement.distance_remaining.toFixed(1)}м • 
            {movement.eta_seconds.toFixed(0)} сек
            <div style={{marginTop: '5px', background: '#1a1a1a', height: '6px', borderRadius: '3px', overflow: 'hidden'}}>
              <div style={{
                width: `${Math.max(5, 100 - (movement.distance_remaining / (movement.distance_remaining + movement.eta_seconds * 5) * 100))}%`,
                height: '100%',
                background: '#4CAF50',
                transition: 'width 1s linear'
              }}></div>
            </div>
          </div>
        )}

        {/* Tab Navigation */}
        <div className="game-tabs">
          <button 
            className={`game-tab ${activeTab === 'zones' ? 'active' : ''}`}
            onClick={() => setActiveTab('zones')}
          >
            🗺️ Зоны
          </button>
          <button 
            className={`game-tab ${activeTab === 'inventory' ? 'active' : ''}`}
            onClick={() => setActiveTab('inventory')}
          >
            🎒 Инвентарь
          </button>
          <button 
            className={`game-tab ${activeTab === 'character' ? 'active' : ''}`}
            onClick={() => setActiveTab('character')}
          >
            👤 Персонаж
          </button>
          <button 
            className={`game-tab ${activeTab === 'abilities' ? 'active' : ''}`}
            onClick={() => setActiveTab('abilities')}
          >
            ⚡ Умения
          </button>
          <button 
            className={`game-tab ${activeTab === 'quests' ? 'active' : ''}`}
            onClick={() => setActiveTab('quests')}
          >
            📜 Квесты{activeQuests.length > 0 && ` (${activeQuests.length})`}
          </button>
          <button 
            className={`game-tab ${activeTab === 'party' ? 'active' : ''}`}
            onClick={() => setActiveTab('party')}
          >
            👥 Группа{partyInfo && ` (${partyInfo.current_members})`}
          </button>
        </div>

        {/* Tab Content */}
        <div className="tab-content">
          {renderTabContent()}
        </div>

        {/* Combat Side Panel (if in combat) */}
        {currentCombat && (
          <div className="side-panel">
            <div className="card">
              <div className="card-header">
                <h2>⚔️ Бой</h2>
              </div>
              <div className="card-content">
                <h4>{currentCombat.mob_name}</h4>
                <div className="stat-bar" style={{marginTop: '10px', width: '100%'}}>
                  <div 
                    className="stat-bar-fill" 
                    style={{
                      width: `${(currentCombat.mob_health / currentCombat.mob_max_health) * 100}%`,
                      background: '#ef4444'
                    }}
                  ></div>
                  <span className="stat-bar-text">{currentCombat.mob_health}/{currentCombat.mob_max_health}</span>
                </div>
                
                <div style={{marginTop: '15px'}}>
                  <h5>Лог боя:</h5>
                  <div style={{maxHeight: '200px', overflow: 'auto', fontSize: '12px', marginTop: '5px'}}>
                    {combatLog.map((log, idx) => (
                      <div key={idx} style={{marginBottom: '3px'}}>{log}</div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Modals */}
        {showInviteSentModal && (
          <div className="modal-overlay" onClick={() => setShowInviteSentModal(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <h3>✓ Приглашение отправлено</h3>
              <p style={{marginTop: '15px', marginBottom: '20px'}}>
                Игрок <strong>{inviteSentTo}</strong> получил приглашение в группу
              </p>
              <button 
                className="btn btn-primary" 
                onClick={() => setShowInviteSentModal(false)}
                style={{width: '100%'}}
              >
                OK
              </button>
            </div>
          </div>
        )}

        {showInviteReceivedModal && currentInvitation && (
          <div className="modal-overlay">
            <div className="modal-content">
              <h3>📨 Приглашение в группу</h3>
              <p style={{marginTop: '15px', marginBottom: '20px'}}>
                Игрок <strong>{currentInvitation.inviter_name}</strong> (Lvl {currentInvitation.inviter_level}) 
                приглашает вас в группу <strong>{currentInvitation.party_name}</strong>
              </p>
              <div style={{display: 'flex', gap: '10px'}}>
                <button 
                  className="btn btn-success" 
                  onClick={() => acceptInvitation(currentInvitation.invitation_id)}
                  style={{flex: 1}}
                >
                  Принять
                </button>
                <button 
                  className="btn btn-secondary" 
                  onClick={() => rejectInvitation(currentInvitation.invitation_id)}
                  style={{flex: 1}}
                >
                  Отклонить
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }


  return (
    <div className="app">
      <header className="header">
        <div className="header-content">
          <div className="logo">
            <h1>Codex Online</h1>
            <p>Live by the Codex. Die by the Sword.</p>
          </div>
          {token && userId ? (
            <div className="user-info">
              <span className="user-id">ID: {userId}</span>
              <button onClick={handleLogout} className="btn btn-danger" style={{ marginLeft: '10px' }}>
                Выход
              </button>
            </div>
          ) : null}
        </div>
      </header>

      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="error-close">✕</button>
        </div>
      )}

      <div className="container">
        {/* Server Status */}
        <section className="card card-status">
          <div className="card-header">
            <h2>⚙️ Статус сервера</h2>
            <button onClick={checkHealth} className="btn-icon">🔄</button>
          </div>
          {health && (
            <div className="status-grid">
              <div className="status-item">
                <span className="status-label">Статус:</span>
                <span className="status-value">{health.status}</span>
              </div>
              <div className="status-item">
                <span className="status-label">Игроков онлайн:</span>
                <span className="status-value">{health.online_players ?? '—'}</span>
              </div>
            </div>
          )}
          {!health && (
            <div className="status-empty">Нет данных от сервера. Нажмите обновить.</div>
          )}
        </section>

        {/* Auth Section */}
        {!token ? (
          <section className="card card-auth">
            <div className="auth-tabs">
              <button
                className={`tab-btn ${authMode === 'login' ? 'active' : ''}`}
                onClick={() => setAuthMode('login')}
              >
                🔐 Вход
              </button>
              <button
                className={`tab-btn ${authMode === 'register' ? 'active' : ''}`}
                onClick={() => setAuthMode('register')}
              >
                ✨ Регистрация
              </button>
            </div>

            <div className="auth-form-container">
              {authMode === 'login' ? (
                <form onSubmit={handleLogin} className="auth-form">
                  <h3>Вход в игру</h3>
                  <div className="form-group">
                    <label>Логин</label>
                    <input
                      type="text"
                      placeholder="Введите логин"
                      value={login.username}
                      onChange={(e) => setLogin({ ...login, username: e.target.value })}
                      disabled={authLoading}
                    />
                  </div>
                  <div className="form-group">
                    <label>Пароль</label>
                    <input
                      type="password"
                      placeholder="Введите пароль"
                      value={login.password}
                      onChange={(e) => setLogin({ ...login, password: e.target.value })}
                      disabled={authLoading}
                    />
                  </div>
                  <button type="submit" className="btn btn-primary" disabled={authLoading}>
                    {authLoading ? '⏳ Загрузка...' : '➜ Войти в игру'}
                  </button>
                </form>
              ) : (
                <form onSubmit={handleRegister} className="auth-form">
                  <h3>Создать аккаунт</h3>
                  <div className="form-group">
                    <label>Логин</label>
                    <input
                      type="text"
                      placeholder="Выберите логин"
                      value={reg.username}
                      onChange={(e) => setReg({ ...reg, username: e.target.value })}
                      disabled={authLoading}
                    />
                  </div>
                  <div className="form-group">
                    <label>Email</label>
                    <input
                      type="email"
                      placeholder="Ваш email"
                      value={reg.email}
                      onChange={(e) => setReg({ ...reg, email: e.target.value })}
                      disabled={authLoading}
                    />
                  </div>
                  <div className="form-group">
                    <label>Пароль</label>
                    <input
                      type="password"
                      placeholder="Введите пароль"
                      value={reg.password}
                      onChange={(e) => setReg({ ...reg, password: e.target.value })}
                      disabled={authLoading}
                    />
                  </div>
                  <div className="form-group">
                    <label>Подтверждение пароля</label>
                    <input
                      type="password"
                      placeholder="Повторите пароль"
                      value={reg.confirmPassword}
                      onChange={(e) => setReg({ ...reg, confirmPassword: e.target.value })}
                      disabled={authLoading}
                    />
                  </div>
                  <button type="submit" className="btn btn-primary" disabled={authLoading}>
                    {authLoading ? '⏳ Загрузка...' : '✨ Создать аккаунт'}
                  </button>
                </form>
              )}
            </div>
          </section>
        ) : (
          <>
            {/* Characters Section */}
            <section className="card card-characters">
              <div className="card-header">
                <h2>👥 Персонажи</h2>
              </div>

              <div className="characters-panel">
                {characters.length === 0 ? (
                  <div className="empty-state">
                    <p className="empty-icon">😢</p>
                    <p>У вас нет персонажей. Создайте первого!</p>
                  </div>
                ) : (
                  <div className="characters-list">
                    {characters.map((char) => (
                      <div key={char.id} className={`character-card ${selectedCharId === char.id ? 'selected' : ''}`}>
                        <div className="char-info">
                          <div className="char-name">{char.name}</div>
                          <div className="char-level">Уровень {char.level}</div>
                          <div className="char-exp">Опыт: {char.experience}</div>
                        </div>
                        <div className="char-actions">
                          <button
                            onClick={() => {
                              setSelectedCharId(char.id);
                              loadWorld(char.id);
                            }}
                            className="btn btn-secondary"
                          >
                            Выбрать
                          </button>
                          <button
                            onClick={() => handleDeleteCharacter(char.id)}
                            className="btn btn-danger btn-small"
                            title="Удалить персонажа"
                          >
                            🗑️
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <button
                  onClick={() => {
                    setShowCreateCharModal(true);
                    loadCharacterRaces();
                    loadCharacterClasses();
                  }}
                  className="btn btn-success"
                  style={{ width: '100%' }}
                >
                  ➕ Создать персонажа
                </button>
              </div>

              {/* Create Character Modal */}
              {showCreateCharModal && (
                <div className="modal-overlay" onClick={() => !createCharLoading && setShowCreateCharModal(false)}>
                  <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                    <div className="modal-header">
                      <h3>✨ Создать нового персонажа</h3>
                      <button
                        className="modal-close"
                        onClick={() => !createCharLoading && setShowCreateCharModal(false)}
                        disabled={createCharLoading}
                      >
                        ✕
                      </button>
                    </div>
                    <form onSubmit={handleCreateCharacter} className="modal-form">
                      <div className="form-group">
                        <label>Имя персонажа</label>
                        <input
                          type="text"
                          placeholder="Введите имя героя..."
                          value={characterName}
                          onChange={(e) => setCharacterName(e.target.value)}
                          disabled={createCharLoading}
                          autoFocus
                        />
                      </div>
                      <div className="form-group">
                        <label>Раса персонажа</label>
                        <select
                          value={selectedRaceId ? String(selectedRaceId) : ''}
                          onChange={(e) => {
                            const val = e.target.value;
                            setSelectedRaceId(val ? parseInt(val, 10) : null);
                          }}
                          disabled={createCharLoading}
                          required
                        >
                          <option value="">Выберите расу...</option>
                          {characterRaces && characterRaces.length > 0 ? (
                            characterRaces.map((race) => (
                              <option key={race.id} value={String(race.id)}>
                                {race.name} - {formatRaceAdvantage(race)}
                              </option>
                            ))
                          ) : (
                            <option disabled>{racesLoading ? 'Загрузка рас...' : 'Нет доступных рас'}</option>
                          )}
                        </select>
                        {racesLoadError && <div className="field-hint field-hint-error">{racesLoadError}</div>}
                      </div>
                      {selectedRace && (
                        <div className="race-preview">
                          <div className="race-preview-title">
                            {selectedRace.name}: {formatRaceAdvantage(selectedRace)}
                          </div>
                          <div className="race-passive-list">
                            {(selectedRace.passive_abilities || []).map((ability) => (
                              <div key={ability.id} className="race-passive-item">
                                <img
                                  src={getPassiveIcon(ability.name)}
                                  alt={ability.name}
                                  className="race-passive-icon"
                                  loading="lazy"
                                />
                                <span className="race-passive-text">
                                  Пассивный скил - {ability.name}: {ability.description}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      <div className="form-group">
                        <label>Класс персонажа</label>
                        <select
                          value={selectedClassId ? String(selectedClassId) : ''}
                          onChange={(e) => {
                            const val = e.target.value;
                            setSelectedClassId(val ? parseInt(val, 10) : null);
                          }}
                          disabled={createCharLoading}
                          required
                        >
                          <option value="">Выберите класс...</option>
                          {characterClasses && characterClasses.length > 0 ? (
                            characterClasses.map((cls) => (
                              <option key={cls.id} value={String(cls.id)}>
                                {cls.name} - {cls.description}
                              </option>
                            ))
                          ) : (
                            <option disabled>{classesLoading ? 'Загрузка классов...' : 'Нет доступных классов'}</option>
                          )}
                        </select>
                        {classesLoadError && <div className="field-hint field-hint-error">{classesLoadError}</div>}
                      </div>
                      <div className="modal-actions">
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={() => setShowCreateCharModal(false)}
                          disabled={createCharLoading}
                        >
                          Отмена
                        </button>
                        <button
                          type="submit"
                          className="btn btn-success"
                          disabled={createCharLoading || !characterName.trim() || !selectedRaceId || !selectedClassId}
                        >
                          {createCharLoading ? '⏳ Создание...' : '✨ Создать'}
                        </button>
                      </div>
                    </form>
                  </div>
                </div>
              )}
            </section>

            {/* World Section */}
            {selectedCharId && (
              <section className="card card-world">
                <div className="card-header">
                  <div>
                    <h2>🗺️ Мир</h2>
                    {selectedCharacter && (
                      <p className="subtitle">
                        Персонаж: <strong>{selectedCharacter.name}</strong> | Уровень: <strong>{selectedCharacter.level}</strong>
                      </p>
                    )}
                  </div>
                  <button onClick={() => loadWorld(selectedCharId)} className="btn-icon">
                    🔄
                  </button>
                </div>

                {worldLoading ? (
                  <div className="loading">
                    <div className="mini-loader"></div>
                    <p>Загрузка мира...</p>
                  </div>
                ) : world ? (
                  <>
                    {/* Location Info */}
                    <div className="location-card">
                      <h3>{world.location.name}</h3>
                      <div className="location-stats">
                        <span>📍 Тип: {world.location.type}</span>
                        <span>⚡ Опасность: {world.location.danger_level}</span>
                      </div>
                      <p className="location-desc">{world.location.description}</p>
                    </div>

                    {/* Objects */}
                    {world.objects && world.objects.length > 0 && (
                      <div className="objects-section">
                        <h4>🔍 Объекты рядом</h4>
                        <div className="objects-grid">
                          {world.objects.map((obj) => (
                            <div key={obj.id} className="object-card">
                              <div className="object-name">{obj.name}</div>
                              <div className="object-type">{obj.type}</div>
                              {obj.distance_km && <div className="object-dist">{obj.distance_km} км</div>}
                              {obj.interaction && <div className="object-action">{obj.interaction}</div>}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                  </>
                ) : (
                  <div className="empty-state">
                    <p>Нет данных о локации...</p>
                  </div>
                )}
              </section>
            )}
          </>
        )}

        {/* Enter World */}
        {selectedCharacter && (
          <section className="card card-enter-world">
            <div className="card-header">
              <h2>🚪 Вход в мир</h2>
            </div>
            <div className="card-content">
              <p>Выбран персонаж: <strong>{selectedCharacter.name}</strong></p>
              <p>Текущая локация: {world?.location?.name || 'Загрузка...'}</p>
              <button onClick={handleEnterWorld} className="btn-primary btn-large">
                🌍 Войти в мир
              </button>
            </div>
          </section>
        )}
      </div>

      <footer className="footer">
        <p>Codex Online 2026 • Made with ❤️ for all • MIT License</p>
      </footer>
    </div>
  );
}

export default App;
