import React, { useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import EntityIcon from './EntityIcon';
import useIconIndex from './useIconIndex';
import { resolveAbilityIcon, resolveItemIcon } from './iconResolvers';
import { formatRaceAdvantage } from './formatters';
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
const EMPTY_STAT_ALLOCATION = {
  strength: 0,
  dexterity: 0,
  constitution: 0,
  intelligence: 0,
  wisdom: 0,
  luck: 0
};

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
  const [worldMaps, setWorldMaps] = useState([]);
  const [selectedWorldMapId, setSelectedWorldMapId] = useState(null);

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
  const [purchasableAbilities, setPurchasableAbilities] = useState([]);
  const [skillShopMeta, setSkillShopMeta] = useState({ completed_quests: 0 });
  const [skillShopLoading, setSkillShopLoading] = useState(false);
  const [mobs, setMobs] = useState([]);
  const [currentCombat, setCurrentCombat] = useState(null);
  const [combatLog, setCombatLog] = useState([]);
  const [selectedMobId, setSelectedMobId] = useState(null);

  // Quests & Crafting
  const [availableQuests, setAvailableQuests] = useState([]);
  const [activeQuests, setActiveQuests] = useState([]);
  const [questProgressMap, setQuestProgressMap] = useState({});
  const [skillCoins, setSkillCoins] = useState(0);
  const [butcheringSkill, setButcheringSkill] = useState({ skill_level: 0, experience: 0, items_butchered: 0 });
  const [showQuestPanel, setShowQuestPanel] = useState(false);
  const [showQuestModal, setShowQuestModal] = useState(false);
  const [questModalNpcName, setQuestModalNpcName] = useState('');
  const [questModalQuests, setQuestModalQuests] = useState([]);
  const [showButcherPanel, setShowButcherPanel] = useState(false);

  // Positioning & Movement
  const [subzones, setSubzones] = useState([]);
  const [nearestCityDistanceM, setNearestCityDistanceM] = useState(null);
  const [npcsInLocation, setNpcsInLocation] = useState([]);
  const [movement, setMovement] = useState({ is_moving: false, distance_remaining: 0, target_name: '', eta_seconds: 0 });
  const movementIntervalRef = useRef(null);
  const autoCombatTimerRef = useRef(null);
  const autoCombatEnabledRef = useRef(false);
  const currentCombatRef = useRef(null);
  const combatAttackInFlightRef = useRef(false);
  const nearbyPlayersRequestRef = useRef(false);
  const pendingInvitesRequestRef = useRef(false);
  
  // Combat & Party
  const [combatStats, setCombatStats] = useState(null);
  const [autoCombatEnabled, setAutoCombatEnabled] = useState(false);
  const [statAllocation, setStatAllocation] = useState(EMPTY_STAT_ALLOCATION);
  const [allocatingStats, setAllocatingStats] = useState(false);
  const [partyInfo, setPartyInfo] = useState(null);
  const [nearbyPlayers, setNearbyPlayers] = useState([]);
  const [pendingInvitations, setPendingInvitations] = useState([]);
  const [showInviteSentModal, setShowInviteSentModal] = useState(false);
  const [inviteSentTo, setInviteSentTo] = useState(null);
  const [showInviteReceivedModal, setShowInviteReceivedModal] = useState(false);
  const [currentInvitation, setCurrentInvitation] = useState(null);
  const [partyNameInput, setPartyNameInput] = useState('');
  const [partySearchTerm, setPartySearchTerm] = useState('');
  const [showShopModal, setShowShopModal] = useState(false);
  const [shopItems, setShopItems] = useState([]);
  const [sellItems, setSellItems] = useState([]);
  const [shopMode, setShopMode] = useState('buy');
  const [shopNpcId, setShopNpcId] = useState(null);
  const [shopNpcName, setShopNpcName] = useState('');
  const [showCraftModal, setShowCraftModal] = useState(false);
  const [craftRecipes, setCraftRecipes] = useState([]);

  // Inventory & Currency
  const [inventory, setInventory] = useState([]);
  const [gold, setGold] = useState(0);
  const [silver, setSilver] = useState(0);
  const [honorCoins, setHonorCoins] = useState(0);
  const [questSourceNpcName, setQuestSourceNpcName] = useState('');
  const generatedIcons = useIconIndex();

  // UI State
  const [activeTab, setActiveTab] = useState('world'); // world, inventory, character, abilities, quests, party, chat
  const [worldSubTab, setWorldSubTab] = useState('worldmap'); // worldmap, city, hunting, resource
  const [cityTab, setCityTab] = useState('npcs'); // npcs, stations
  const [cityInteractionsActive, setCityInteractionsActive] = useState(false);
  const [showTutorial, setShowTutorial] = useState(false);
  const [chatChannels, setChatChannels] = useState([]);
  const [chatSubTab, setChatSubTab] = useState('world');
  const [chatMessagesByChannel, setChatMessagesByChannel] = useState({ world: [], help: [], trade: [] });
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [systemChatMessages, setSystemChatMessages] = useState([]);
  const [tutorialProgress, setTutorialProgress] = useState({
    openedQuestsTab: false,
    acceptedQuest: false,
    completedQuest: false
  });

  // Derived
  const selectedCharacter = useMemo(
    () => characters.find((c) => c.id === selectedCharId) || null,
    [characters, selectedCharId]
  );

  const selectedRace = useMemo(
    () => characterRaces.find((r) => r.id === selectedRaceId) || null,
    [characterRaces, selectedRaceId]
  );

  const selectedClass = useMemo(
    () => characterClasses.find((cls) => cls.id === selectedClassId) || null,
    [characterClasses, selectedClassId]
  );

  const selectedWorldMap = useMemo(
    () => worldMaps.find((loc) => loc.id === selectedWorldMapId) || null,
    [worldMaps, selectedWorldMapId]
  );

  const worldMapCards = useMemo(() => {
    const spec = [
      {
        name: 'Аурис',
        apiName: 'Изумрудные леса Лирана',
        levelRange: '1-10',
        status: 'Доступно',
        inDevelopment: false,
        typeLabel: 'Для новичков',
      },
      {
        name: 'Туманные болота Моргрима',
        levelRange: '10-15',
        status: 'В разработке',
        inDevelopment: true,
        typeLabel: 'Нейтральная территория',
      },
      {
        name: 'Пепельные земли Кхаргара',
        levelRange: '15-20',
        status: 'В разработке',
        inDevelopment: true,
        typeLabel: 'ПВП территория',
      },
    ];

    return spec.map((entry) => {
      const apiMap = worldMaps.find((loc) => {
        const apiName = String(loc?.name || '').trim();
        return apiName === entry.name || apiName === entry.apiName;
      }) || null;
      return {
        ...entry,
        id: apiMap?.id ?? null,
        api: apiMap,
      };
    });
  }, [worldMaps]);

  const pendingInvitesCount = pendingInvitations.length;
  const activeQuestIdSet = useMemo(() => new Set((activeQuests || []).map((q) => q.quest_id)), [activeQuests]);

  const getAbilityIcon = (abilityName = '') => {
    return resolveAbilityIcon(abilityName, generatedIcons);
  };

  const getItemIcon = (itemName = '') => {
    return resolveItemIcon(itemName, generatedIcons);
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
      loadPendingInvitations(selectedCharId);
      loadNearbyPlayers(selectedCharId);
    }, 10000); // Check every 10 seconds
    
    return () => clearInterval(interval);
  }, [inWorld, selectedCharId]);

  useEffect(() => {
    if (!inWorld || !selectedCharId) return;
    const key = `codex_tutorial_done_${selectedCharId}`;
    const done = localStorage.getItem(key) === '1';
    setShowTutorial(!done);
  }, [inWorld, selectedCharId]);

  useEffect(() => {
    if (activeTab === 'quests') {
      setTutorialProgress((prev) => ({ ...prev, openedQuestsTab: true }));
    }
  }, [activeTab]);

  useEffect(() => {
    if (inWorld && selectedCharId && activeTab === 'abilities') {
      loadPurchasableAbilities(selectedCharId);
    }
  }, [inWorld, selectedCharId, activeTab]);

  useEffect(() => {
    if (!inWorld || !selectedCharId || activeTab !== 'world' || worldSubTab !== 'hunting') return;

    const activeZoneId = Number(world?.zone?.id || 0);
    const hasActiveHuntingZone = subzones.some(
      (zone) => String(zone?.type || '').toLowerCase() === 'hunting' && Number(zone.zone_id) === activeZoneId
    );
    if (!hasActiveHuntingZone) return;

    const interval = setInterval(() => {
      loadMobs(selectedCharId);
    }, 3000);

    return () => clearInterval(interval);
  }, [inWorld, selectedCharId, activeTab, worldSubTab, world, subzones]);

  useEffect(() => {
    if (!inWorld || !selectedCharId) return;
    loadChatChannels(selectedCharId);
    loadChatHistory('world', selectedCharId);
  }, [inWorld, selectedCharId, world?.location?.id]);

  useEffect(() => {
    if (!inWorld || !selectedCharId || activeTab !== 'chat' || chatSubTab === 'system') return;
    const timer = setInterval(() => {
      loadChatHistory(chatSubTab, selectedCharId);
    }, 6000);
    return () => clearInterval(timer);
  }, [inWorld, selectedCharId, activeTab, chatSubTab]);

  useEffect(() => {
    return () => {
      if (movementIntervalRef.current) {
        clearInterval(movementIntervalRef.current);
        movementIntervalRef.current = null;
      }
      if (autoCombatTimerRef.current) {
        clearTimeout(autoCombatTimerRef.current);
        autoCombatTimerRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    autoCombatEnabledRef.current = autoCombatEnabled;
  }, [autoCombatEnabled]);

  useEffect(() => {
    currentCombatRef.current = currentCombat;
  }, [currentCombat]);

  useEffect(() => {
    if (!currentCombat || !['ready', 'active'].includes(currentCombat.status)) {
      setAutoCombatEnabled(false);
      clearAutoCombatTimer();
    }
  }, [currentCombat]);

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
      const detail = e?.response?.data?.detail || e.message;
      if (detail === 'Invalid credentials') {
        setError('Неверный логин или пароль. Если аккаунта еще нет, откройте вкладку "Регистрация" и создайте его.');
      } else {
        setError(`Ошибка входа: ${detail}`);
      }
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

  const loadWorldMaps = async () => {
    try {
      const { data } = await api.get('/locations');
      setWorldMaps(data?.locations || []);
    } catch (e) {
      console.warn('world maps load failed:', e);
      setWorldMaps([]);
    }
  };

  const appendSystemMessage = (text) => {
    const msg = {
      id: `${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      text,
      created_at: new Date().toISOString(),
    };
    setSystemChatMessages((prev) => [...prev.slice(-79), msg]);
  };

  const loadChatChannels = async (charId = selectedCharId) => {
    if (!charId) return;
    try {
      const { data } = await api.get(`/chat/channels/${charId}`);
      const channels = data?.channels || [];
      setChatChannels(channels);
    } catch (err) {
      console.warn('chat channels load failed:', err);
      setChatChannels([]);
    }
  };

  const loadChatHistory = async (channel, charId = selectedCharId) => {
    if (!charId || !channel || channel === 'system') return;
    setChatLoading(true);
    try {
      const { data } = await api.get(`/chat/history/${charId}`, {
        params: { channel, limit: 80 }
      });
      const messages = data?.messages || [];
      setChatMessagesByChannel((prev) => ({ ...prev, [channel]: messages }));
    } catch (err) {
      console.warn('chat history load failed:', err);
      setChatMessagesByChannel((prev) => ({ ...prev, [channel]: [] }));
    } finally {
      setChatLoading(false);
    }
  };

  const sendChatMessage = async () => {
    if (!selectedCharId || chatSubTab === 'system') return;
    const text = String(chatInput || '').trim();
    if (!text) return;
    try {
      const { data } = await api.post(`/chat/send/${selectedCharId}`, {
        channel: chatSubTab,
        message: text,
      });
      const sent = data?.message;
      if (sent) {
        setChatMessagesByChannel((prev) => {
          const current = Array.isArray(prev[chatSubTab]) ? prev[chatSubTab] : [];
          return { ...prev, [chatSubTab]: [...current.slice(-79), sent] };
        });
      }
      setChatInput('');
      setError(null);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Ошибка отправки сообщения');
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
      const quests = data?.quests || [];
      setActiveQuests(quests);

      if (quests.length === 0) {
        setQuestProgressMap({});
        return;
      }

      const progressEntries = await Promise.all(
        quests.map(async (quest) => {
          try {
            const { data: progress } = await api.get(`/quests/${charId}/${quest.quest_id}/progress`);
            return [quest.quest_id, progress];
          } catch {
            return [quest.quest_id, null];
          }
        })
      );

      setQuestProgressMap(Object.fromEntries(progressEntries));
    } catch (e) {
      console.warn('active quests load failed:', e);
    }
  };

  const loadSkillCoins = async (charId) => {
    try {
      const { data } = await api.get(`/skill_coins/${charId}`);
      const balance = data?.balance || 0;
      setSkillCoins(balance);
      setHonorCoins(balance);
      return balance;
    } catch (e) {
      console.warn('skill coins load failed:', e);
      return 0;
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

  const loadPurchasableAbilities = async (charId = selectedCharId) => {
    if (!charId) return;
    setSkillShopLoading(true);
    try {
      const { data } = await api.get(`/abilities/${charId}/honor-shop`);
      setPurchasableAbilities(data?.abilities || []);
      setSkillShopMeta({
        completed_quests: data?.completed_quests || 0,
      });
    } catch (e) {
      console.warn('purchasable abilities load failed:', e);
      setPurchasableAbilities([]);
      setSkillShopMeta({ completed_quests: 0 });
    } finally {
      setSkillShopLoading(false);
    }
  };

  const learnAbilityWithHonor = async (abilityId) => {
    if (!selectedCharId) return;
    try {
      const { data } = await api.post(`/abilities/${abilityId}/learn`, null, {
        params: { character_id: selectedCharId },
      });
      if (data?.status !== 'ability_learned') {
        setError(data?.message || 'Не удалось изучить способность');
        return;
      }
      setError(`✓ Изучено: ${data.ability_name}`);
      await loadCharacterAbilities(selectedCharId);
      await loadSkillCoins(selectedCharId);
      await loadPurchasableAbilities(selectedCharId);
    } catch (e) {
      setError(e?.response?.data?.detail || 'Ошибка изучения способности');
    }
  };

  const acceptQuest = async (questId) => {
    if (!selectedCharId) return;
    try {
      await api.post(`/quests/${questId}/accept`, null, { params: { character_id: selectedCharId } });
      setError(null);
      setAvailableQuests((prev) => prev.filter((q) => q.id !== questId));
      setQuestModalQuests((prev) => prev.map((q) => (q.id === questId ? { ...q, _accepted: true } : q)));
      await loadActiveQuests(selectedCharId);
      setTutorialProgress((prev) => ({ ...prev, acceptedQuest: true }));
    } catch (e) {
      setError(`Ошибка принятия квеста: ${e?.response?.data?.detail || e.message}`);
    }
  };

  const butcherMob = async (mobId) => {
    if (!selectedCharId) return;
    try {
      const { data } = await api.post(`/butchering/butcher_mob`, null, { params: { character_id: selectedCharId, mob_id: mobId } });
      setError(null);
      const itemsText = (data.obtained_items || []).map((i) => `${i.name}x${i.quantity}`).join(', ');
      setCombatLog((prev) => [`✅ Разделка: ${itemsText || 'нет ресурсов'}`, ...prev].slice(0, 50));
      setCurrentCombat((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          butchered: true,
          butchered_items: data.obtained_items || [],
        };
      });
      await loadInventory(selectedCharId);
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
      await loadPurchasableAbilities(selectedCharId);
      setCombatLog([...combatLog, `🎉 Квест завершен! +${data.honor_points_reward || data.skill_coins_reward} очков чести`]);
      appendSystemMessage(`Квест завершен: +${data.reward_experience || 0} опыта, +${data.reward_gold || 0} золота, +${data.honor_points_reward || data.skill_coins_reward || 0} очков чести`);
      setTutorialProgress((prev) => ({ ...prev, completedQuest: true }));
    } catch (e) {
      setError(`Ошибка завершения квеста: ${e?.response?.data?.detail || e.message}`);
    }
  };

  const closeTutorial = () => {
    if (selectedCharId) {
      localStorage.setItem(`codex_tutorial_done_${selectedCharId}`, '1');
    }
    setShowTutorial(false);
  };

  const selectMobForCombat = (mob) => {
    const isBoss = String(mob?.mob_tier || '').toLowerCase() === 'boss' || Boolean(mob?.is_boss);
    const inParty = Boolean(partyInfo?.in_party || partyInfo?.party_id);
    if (isBoss && !inParty) {
      const confirmed = window.confirm('Вы уверены что хотите начать атаку?');
      if (!confirmed) {
        return;
      }
    }

    stopAutoCombat();
    const mobDisplayName = isBoss ? `${mob.name} (Босс)` : mob.name;
    setSelectedMobId(mob.id);
    setCurrentCombat({
      mob_id: mob.id,
      mob_name: mobDisplayName,
      mob_health: mob.health,
      mob_max_health: mob.max_health,
      character_health: selectedCharacter?.health_points || 1,
      character_max_health: selectedCharacter?.max_health_points || 1,
      status: 'ready',
      exp_gained: 0,
      gold_gained: 0,
      silver_gained: 0,
      exp_lost: 0,
      death_territory: null,
      dropped_items: [],
      can_butcher: false,
      butchered: false,
      butchered_items: [],
      mob_tier: mob?.mob_tier || null,
    });
    setCombatLog([`Выбран противник: ${mobDisplayName}`]);
  };

  const finishCombat = () => {
    stopAutoCombat();
    setCurrentCombat(null);
    setSelectedMobId(null);
    setCombatLog([]);
  };

  const leaveCombat = () => {
    stopAutoCombat();
    setCombatLog((prev) => ['Вы отступили из боя.', ...prev].slice(0, 50));
    setCurrentCombat((prev) => (prev ? { ...prev, status: 'fled' } : prev));
  };

  const useAbility = async (abilityId) => {
    if (!currentCombat?.mob_id) return;
    await attackMob(currentCombat.mob_id, abilityId);
  };

  const handleEnterWorld = async (charId = selectedCharId) => {
    if (!charId) return;
    setInWorld(true);
    setSelectedCharId(charId);
    try {
      // First get current location
      const { data: worldData } = await api.get('/world/current', { params: { character_id: charId } });
      const locationId = worldData?.location?.id || 1;
      setWorld(worldData);
      setSelectedWorldMapId(locationId);
      setAvailableQuests([]);
      setQuestSourceNpcName('');
      setShowQuestPanel(false);
      
      // Fast world entry: render location/UI first, then load heavy data in background.
      await Promise.all([loadLocationSubzones(locationId, charId), loadWorldMaps()]);

      await Promise.all([loadChatChannels(charId), loadChatHistory('world', charId), loadChatHistory('help', charId), loadChatHistory('trade', charId)]);

      Promise.allSettled([
        loadCharacterAbilities(charId),
        loadCombatStats(charId),
        loadPartyInfo(charId),
        loadNearbyPlayers(charId),
        loadPendingInvitations(charId),
        loadActiveQuests(charId),
        loadSkillCoins(charId),
        loadPurchasableAbilities(charId),
        loadButcheringSkill(charId),
        api.post(`/characters/${charId}/starter-items/ensure`),
        loadInventory(charId),
        loadMobs(charId),
      ]);
      appendSystemMessage(`Вход в мир: ${worldData?.location?.name || 'Неизвестная локация'}`);
    } catch (err) {
      setError('Ошибка входа в мир: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleExitWorld = () => {
    if (movementIntervalRef.current) {
      clearInterval(movementIntervalRef.current);
      movementIntervalRef.current = null;
    }
    setInWorld(false);
    setSubzones([]);
    setNearestCityDistanceM(null);
    setNpcsInLocation([]);
    setAvailableQuests([]);
    setQuestSourceNpcName('');
    setShowQuestPanel(false);
    setShowQuestModal(false);
    setQuestModalNpcName('');
    setQuestModalQuests([]);
    setMovement({ is_moving: false, distance_remaining: 0, target_name: '', eta_seconds: 0 });
    setZoneObjects([]);
    setNearbyPlayers([]);
    setPendingInvitations([]);
    setShowInviteSentModal(false);
    setShowInviteReceivedModal(false);
    setCurrentInvitation(null);
    setShowShopModal(false);
    setShopItems([]);
    setSellItems([]);
    setShopMode('buy');
    setShopNpcId(null);
    setShopNpcName('');
    setShowCraftModal(false);
    setCraftRecipes([]);
    setCurrentCombat(null);
    stopAutoCombat();
    setCombatLog([]);
    setSelectedMobId(null);
    setWorldSubTab('worldmap');
    setCityTab('npcs');
    setCityInteractionsActive(false);
    setChatChannels([]);
    setChatSubTab('world');
    setChatMessagesByChannel({ world: [], help: [], trade: [] });
    setChatInput('');
    setSystemChatMessages([]);
  };

  // ===== POSITIONING FUNCTIONS =====

  const loadLocationSubzones = async (locationId, charId = selectedCharId) => {
    if (!charId || !locationId) return;
    try {
      let data;
      try {
        ({ data } = await api.get(`/world/subzones/${locationId}?character_id=${charId}&include_mobs=false`));
      } catch (primaryErr) {
        if (primaryErr?.response?.status !== 404) {
          throw primaryErr;
        }
        ({ data } = await api.get(`/world/zones/${locationId}?character_id=${charId}&include_mobs=false`));
      }
      setSubzones(data.subzones || data.zones || []);
      setNearestCityDistanceM(
        Number.isFinite(Number(data?.nearest_city_distance_m))
          ? Number(data.nearest_city_distance_m)
          : null
      );
      setNpcsInLocation(data.npcs || []);
      setSelectedWorldMapId(locationId);
      setError(null);
    } catch (err) {
      console.error('Failed to load subzones:', err);
      setSubzones([]);
      setNearestCityDistanceM(null);
      setNpcsInLocation([]);
    }
  };

  const startMovement = async (targetType, targetId, targetName) => {
    try {
      const { data } = await api.post(`/world/move/${selectedCharId}`, null, {
        params: { target_type: targetType, target_id: targetId }
      });

      const normalizedTargetType = String(targetType || '').toLowerCase();
      if (['zone', 'subzone', 'area'].includes(normalizedTargetType)) {
        setWorld((prev) => {
          if (!prev?.zone) return prev;
          if (Number(prev.zone.id || 0) === Number(targetId || 0)) return prev;
          return { ...prev, zone: null };
        });
      }

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

  const startMovementPolling = () => {
    if (movementIntervalRef.current) clearInterval(movementIntervalRef.current);
    movementIntervalRef.current = setInterval(async () => {
      const stillMoving = await checkMovementStatus();
      if (!stillMoving) {
        clearInterval(movementIntervalRef.current);
        movementIntervalRef.current = null;
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
        // Get current location and reload subzones
        const { data: locData } = await api.get('/world/current', { params: { character_id: selectedCharId } });
        setWorld(locData);
        const locId = locData?.location?.id || 1;
        await loadLocationSubzones(locId, selectedCharId);
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
        let successMessage = data.message || 'Взаимодействие успешно';
        setError(successMessage);
        if (data.action === 'shop_buy' && Array.isArray(data.items)) {
          setShopMode('buy');
          setShopItems(data.items);
          setSellItems([]);
          setShopNpcId(data.npc_id || targetId);
          setShopNpcName(data.npc_name || 'Торговец');
          if (data.wallet) {
            setGold(data.wallet.gold ?? gold);
            setSilver(data.wallet.silver ?? silver);
          }
          setShowShopModal(true);
        }
        if (data.action === 'shop_sell' && Array.isArray(data.items)) {
          setShopMode('sell');
          setSellItems(data.items);
          setShopItems([]);
          setShopNpcId(data.npc_id || targetId);
          setShopNpcName(data.npc_name || 'Торговец');
          if (data.wallet) {
            setGold(data.wallet.gold ?? gold);
            setSilver(data.wallet.silver ?? silver);
          }
          setShowShopModal(true);
        }
        if (data.action === 'craft_station') {
          const recipesResp = await api.get('/crafting/recipes', { params: { character_id: selectedCharId } });
          setCraftRecipes(recipesResp?.data?.recipes || []);
          setShowCraftModal(true);
        }
        if (data.action === 'quest_list' && data.quests) {
          setAvailableQuests(data.quests);
          setQuestSourceNpcName(data.npc_name || 'этого NPC');
          setShowQuestPanel(true);
          setQuestModalNpcName(data.npc_name || 'этого NPC');
          setQuestModalQuests(data.quests || []);
          setShowQuestModal(true);
        }
        if (data.action === 'enter_zone') {
          const { data: locData } = await api.get('/world/current', { params: { character_id: selectedCharId } });
          const locId = locData?.location?.id || 1;
          setWorld(locData);
          setCurrentCombat(null);
          setCombatLog([]);
          setSelectedMobId(null);
          await loadLocationSubzones(locId, selectedCharId);
          if (Array.isArray(data.mobs)) {
            setMobs(data.mobs);
          } else {
            await loadMobs(selectedCharId);
          }
        }
        if (data.action === 'exit_zone') {
          const { data: locData } = await api.get('/world/current', { params: { character_id: selectedCharId } });
          const locId = locData?.location?.id || 1;
          setWorld(locData);
          setCurrentCombat(null);
          setCombatLog([]);
          setSelectedMobId(null);
          setMobs([]);
          await loadLocationSubzones(locId, selectedCharId);
        }
      } else {
        setError(data.message);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка взаимодействия');
    }
  };

  // ===== COMBAT FUNCTIONS =====

  const attackMob = async (mobId, abilityId = null) => {
    if (!selectedCharId) return;
    if (combatAttackInFlightRef.current) return null;
    combatAttackInFlightRef.current = true;
    try {
      const params = abilityId ? { ability_id: abilityId } : undefined;
      const { data } = await api.post(`/combat/attack/${selectedCharId}/${mobId}`, null, { params });

      const logLines = Array.isArray(data?.combat_log) ? data.combat_log.filter(Boolean) : [];
      setCombatLog((prev) => [...logLines, ...prev].slice(0, 50));

      setCurrentCombat((prev) => {
        if (!prev) return prev;

        const next = {
          ...prev,
          mob_health: Number(data?.mob_hp ?? prev.mob_health),
          mob_max_health: Number(data?.mob_max_hp ?? prev.mob_max_health),
          character_health: Number(data?.character_hp ?? prev.character_health),
          status: 'active',
        };

        if (data?.mob_killed) {
          next.status = 'victory';
          next.exp_gained = Number(data?.exp_gained || 0);
          next.gold_gained = Number(data?.gold_gained || 0);
          next.silver_gained = Number(data?.silver_gained || 0);
          next.can_butcher = Boolean(data?.can_butcher);
          next.mob_health = 0;
        }

        if (data?.character_died) {
          next.status = 'defeat';
          next.exp_lost = Number(data?.exp_lost || 0);
          next.death_territory = data?.death_territory || null;
          next.dropped_items = Array.isArray(data?.dropped_items) ? data.dropped_items : [];
        }

        return next;
      });

      if (data.mob_killed) {
        setError(`☠️ Победа: +${data.exp_gained || 0} опыта, +${data.gold_gained || 0} золота, +${data.silver_gained || 0} серебра`);
        appendSystemMessage(`Последний бой: +${data.exp_gained || 0} опыта, +${data.gold_gained || 0} золота, +${data.silver_gained || 0} серебра`);
        const { data: locData } = await api.get('/world/current', { params: { character_id: selectedCharId } });
        const locId = locData?.location?.id || 1;
        setWorld(locData);
        await loadLocationSubzones(locId, selectedCharId);
        await loadMobs(selectedCharId);
        await loadCharacters();
        await loadInventory(selectedCharId);
      }

      if (data.character_died) {
        setError(`Персонаж погиб: -${data.exp_lost || 0} опыта`);
        appendSystemMessage(`Поражение в бою: -${data.exp_lost || 0} опыта`);
        await loadCharacters();
        await loadInventory(selectedCharId);
      }
      return data;
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка атаки');
      return null;
    } finally {
      combatAttackInFlightRef.current = false;
    }
  };

  const clearAutoCombatTimer = () => {
    if (autoCombatTimerRef.current) {
      clearTimeout(autoCombatTimerRef.current);
      autoCombatTimerRef.current = null;
    }
  };

  const stopAutoCombat = () => {
    setAutoCombatEnabled(false);
    clearAutoCombatTimer();
  };

  const getAutoCombatIntervalMs = (combatSnapshot) => {
    const rawAttackSpeed = Number(combatStats?.combat?.attack_speed || 60);
    const attackSpeed = Number.isFinite(rawAttackSpeed) && rawAttackSpeed > 0 ? rawAttackSpeed : 60;
    const baseInterval = 60000 / attackSpeed;
    const tier = String(combatSnapshot?.mob_tier || '').toLowerCase();
    const tierMultiplier = tier === 'weak'
      ? 1.4
      : tier === 'normal'
        ? 1.15
        : tier === 'strong'
          ? 0.8
          : tier === 'boss'
            ? 0.65
            : 1;

    return Math.max(900, Math.min(4200, Math.round(baseInterval * tierMultiplier)));
  };

  const runAutoCombatTick = async () => {
    if (!autoCombatEnabledRef.current) return;

    const combatSnapshot = currentCombatRef.current;
    if (!combatSnapshot || !['ready', 'active'].includes(combatSnapshot.status)) {
      stopAutoCombat();
      return;
    }

    const result = await attackMob(combatSnapshot.mob_id);
    if (!autoCombatEnabledRef.current) return;
    if (!result || result.mob_killed || result.character_died) {
      stopAutoCombat();
      return;
    }

    const nextSnapshot = currentCombatRef.current || combatSnapshot;
    const delayMs = getAutoCombatIntervalMs(nextSnapshot);
    clearAutoCombatTimer();
    autoCombatTimerRef.current = setTimeout(runAutoCombatTick, delayMs);
  };

  const startAutoCombat = () => {
    const combatSnapshot = currentCombatRef.current;
    if (!combatSnapshot || !['ready', 'active'].includes(combatSnapshot.status)) return;
    if (autoCombatEnabledRef.current) return;

    setAutoCombatEnabled(true);
    clearAutoCombatTimer();
    autoCombatTimerRef.current = setTimeout(runAutoCombatTick, 0);
  };

  const loadCombatStats = async (charId = selectedCharId) => {
    if (!charId) return;
    try {
      const { data } = await api.get(`/combat/stats/${charId}`);
      setCombatStats(data);
      setStatAllocation({ ...EMPTY_STAT_ALLOCATION });
    } catch (err) {
      console.error('Failed to load combat stats:', err);
    }
  };

  const updateStatAllocation = (statName, rawValue) => {
    const safeValue = Math.max(0, Number.parseInt(rawValue, 10) || 0);
    setStatAllocation((prev) => ({ ...prev, [statName]: safeValue }));
  };

  const allocateStatPoints = async () => {
    if (!selectedCharId) return;
    const payload = Object.fromEntries(
      Object.entries(statAllocation).map(([key, value]) => [key, Math.max(0, Number.parseInt(value, 10) || 0)])
    );
    const pointsToSpend = Object.values(payload).reduce((sum, value) => sum + value, 0);
    const available = Number(combatStats?.available_stat_points || 0);

    if (pointsToSpend <= 0) {
      setError('Укажите хотя бы 1 очко для распределения');
      return;
    }
    if (pointsToSpend > available) {
      setError(`Недостаточно очков: доступно ${available}`);
      return;
    }

    setAllocatingStats(true);
    try {
      await api.post(`/combat/stats/${selectedCharId}/allocate`, payload);
      setError(`✓ Распределено очков: ${pointsToSpend}`);
      setStatAllocation({ ...EMPTY_STAT_ALLOCATION });
      await loadCombatStats(selectedCharId);
      await loadCharacters();
      await loadWorld(selectedCharId);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Ошибка распределения характеристик');
    } finally {
      setAllocatingStats(false);
    }
  };

  const increaseSingleStat = async (statName) => {
    if (!selectedCharId) return;
    const available = Number(combatStats?.available_stat_points || 0);
    if (available <= 0 || allocatingStats) return;

    setAllocatingStats(true);
    try {
      const payload = { ...EMPTY_STAT_ALLOCATION, [statName]: 1 };
      await api.post(`/combat/stats/${selectedCharId}/allocate`, payload);
      await loadCombatStats(selectedCharId);
      await loadCharacters();
      await loadWorld(selectedCharId);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Ошибка распределения характеристик');
    } finally {
      setAllocatingStats(false);
    }
  };

  // ===== PARTY FUNCTIONS =====

  const createParty = async (partyName) => {
    try {
      await api.post(`/party/create/${selectedCharId}`, null, {
        params: { party_name: partyName, is_public: false }
      });
      setError('✓ Группа создана');
      setPartyNameInput('');
      await loadPartyInfo();
      await loadNearbyPlayers();
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка создания группы');
    }
  };

  const loadPartyInfo = async (charId = selectedCharId) => {
    if (!charId) return;
    try {
      const { data } = await api.get(`/party/my-party/${charId}`);
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

  const loadNearbyPlayers = async (charId = selectedCharId) => {
    if (!charId) return;
    if (nearbyPlayersRequestRef.current) return;
    nearbyPlayersRequestRef.current = true;
    try {
      const { data } = await api.get(`/party/nearby-players/${charId}`);
      setNearbyPlayers(data.nearby_players || []);
    } catch (err) {
      console.error('Failed to load nearby players:', err);
      setNearbyPlayers([]);
    } finally {
      nearbyPlayersRequestRef.current = false;
    }
  };

  const loadPendingInvitations = async (charId = selectedCharId) => {
    if (!charId) return;
    if (pendingInvitesRequestRef.current) return;
    pendingInvitesRequestRef.current = true;
    try {
      const { data } = await api.get(`/party/invitations/pending/${charId}`);
      setPendingInvitations(data.invitations || []);
      
      // Show modal for first pending invitation
      if (data.invitations && data.invitations.length > 0 && !showInviteReceivedModal) {
        setCurrentInvitation(data.invitations[0]);
        setShowInviteReceivedModal(true);
      }
    } catch (err) {
      console.error('Failed to load invitations:', err);
      setPendingInvitations([]);
    } finally {
      pendingInvitesRequestRef.current = false;
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

  const loadInventory = async (charId = selectedCharId) => {
    if (!charId) return;
    try {
      const { data } = await api.get(`/characters/${charId}/inventory`);
      setInventory(data?.inventory || []);
      setGold(data?.gold ?? selectedCharacter?.gold ?? 0);
      setSilver(data?.silver ?? selectedCharacter?.silver ?? 0);
      
      // Load honor coins (renamed from skill_coins)
      const coins = await loadSkillCoins(charId);
      setHonorCoins(coins);
    } catch (err) {
      console.error('Failed to load inventory:', err);
    }
  };

  const equipmentSlots = ['right_hand', 'left_hand', 'head', 'chest', 'legs', 'feet', 'ring_left', 'ring_right'];
  const equippableItemTypes = new Set([
    'weapon',
    'melee_weapon',
    'one_handed_weapon',
    'weapon_1h',
    'weapon_one_handed',
    'two_handed_weapon',
    'weapon_2h',
    'weapon_two_handed',
    'sword',
    'axe',
    'mace',
    'bow',
    'staff',
    'armor',
    'chest_armor',
    'body_armor',
    'robe',
    'shield',
    'helmet',
    'hat',
    'boots',
    'gloves',
    'pants',
    'ring',
    'accessory'
  ]);

  const isItemEquippable = (item) => equippableItemTypes.has((item?.type || '').toLowerCase());

  const buildItemTooltip = (item) => {
    if (!item) return '';
    const lines = [];
    lines.push(item.name || 'Предмет');
    lines.push(`Тип: ${item.type || 'unknown'}`);
    if (item.rarity) lines.push(`Редкость: ${item.rarity}`);
    if (item.description) lines.push(item.description);
    if ((item.damage_min || 0) > 0 || (item.damage_max || 0) > 0) {
      lines.push(`Урон: ${item.damage_min || 0}-${item.damage_max || 0}`);
    }
    if ((item.armor_class || 0) > 0) {
      lines.push(`Броня: +${item.armor_class}`);
    }
    if ((item.health_recovery || 0) > 0) {
      lines.push(`Лечение: +${item.health_recovery} HP`);
    }
    lines.push(`Количество: ${item.quantity || 0}`);
    lines.push(`Цена: ${item.value || 0} золота`);
    lines.push(isItemEquippable(item) ? 'Можно экипировать' : 'Не экипируется (расходник/материал)');
    return lines.join('\n');
  };

  const slotLabels = {
    right_hand: 'Правая рука',
    left_hand: 'Левая рука',
    head: 'Голова',
    chest: 'Тело',
    legs: 'Ноги',
    feet: 'Ступни',
    ring_left: 'Левое кольцо',
    ring_right: 'Правое кольцо'
  };

  const equippedBySlot = useMemo(() => {
    const map = {};
    inventory.filter((item) => item.equipped).forEach((item) => {
      if (item.slot === 'both_hands') {
        map.right_hand = item;
        map.left_hand = item;
        return;
      }
      if (item.slot) {
        map[item.slot] = item;
      }
    });
    return map;
  }, [inventory]);

  const backpackItems = useMemo(
    () => inventory.filter((item) => !item.equipped),
    [inventory]
  );

  const equipItem = async (itemId) => {
    if (!selectedCharId) return;
    try {
      await api.post(`/characters/${selectedCharId}/inventory/equip`, { item_id: itemId });
      await Promise.all([loadInventory(selectedCharId), loadCombatStats(selectedCharId)]);
      setError('Предмет экипирован');
    } catch (e) {
      setError(`Ошибка экипировки: ${e?.response?.data?.detail || e.message}`);
    }
  };

  const unequipItem = async (slot) => {
    if (!selectedCharId) return;
    try {
      await api.post(`/characters/${selectedCharId}/inventory/unequip`, { slot });
      await Promise.all([loadInventory(selectedCharId), loadCombatStats(selectedCharId)]);
      setError('Предмет снят');
    } catch (e) {
      setError(`Ошибка снятия: ${e?.response?.data?.detail || e.message}`);
    }
  };

  const buyShopItem = async (itemId) => {
    if (!selectedCharId || !shopNpcId) return;
    try {
      const { data } = await api.post(`/shop/buy/${selectedCharId}`, null, {
        params: { npc_id: shopNpcId, item_id: itemId, quantity: 1 }
      });
      setError(data.message || 'Покупка успешна');
      if (data.wallet) {
        setGold(data.wallet.gold ?? gold);
        setSilver(data.wallet.silver ?? silver);
      }
      await loadInventory(selectedCharId);
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка покупки');
    }
  };

  const sellShopItem = async (itemId) => {
    if (!selectedCharId || !shopNpcId) return;
    try {
      const { data } = await api.post(`/shop/sell/${selectedCharId}`, null, {
        params: { npc_id: shopNpcId, item_id: itemId, quantity: 1 }
      });
      setError(data.message || 'Продажа успешна');
      if (data.wallet) {
        setGold(data.wallet.gold ?? gold);
        setSilver(data.wallet.silver ?? silver);
      }
      await loadInventory(selectedCharId);
      const refresh = await api.post(`/world/interact/${selectedCharId}`, null, {
        params: { target_type: 'npc', target_id: shopNpcId, action: 'sell' }
      });
      setSellItems(refresh?.data?.items || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка продажи');
    }
  };

  const craftRecipe = async (recipeId) => {
    if (!selectedCharId) return;
    try {
      const { data } = await api.post('/crafting/craft', null, {
        params: { character_id: selectedCharId, recipe_id: recipeId }
      });
      if (data.status === 'missing_materials') {
        setError('Недостаточно материалов для крафта');
      } else if (data.status === 'craft_failed') {
        setError(`Крафт не удался (${data.success_rate}%)`);
      } else {
        const bonus = data.bonus_proc ? ' + бонус от вдохновения!' : '';
        setError(`Создано: ${data.result_item_name} x${data.result_quantity}${bonus}`);
      }
      const recipesResp = await api.get('/crafting/recipes', { params: { character_id: selectedCharId } });
      setCraftRecipes(recipesResp?.data?.recipes || []);
      await loadInventory(selectedCharId);
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка крафта');
    }
  };

  const areaMeta = {
    city: { name: 'Город', icon: '🏛️' },
    hunting: { name: 'Охота', icon: '⚔️' },
    resource: { name: 'Добыча', icon: '⛏️' }
  };

  // Strict 3-area model: only city, hunting, resource.
  const subzonesByType = useMemo(() => {
    const groups = { city: [], hunting: [], resource: [] };
    subzones.forEach((zone) => {
      const zoneType = String(zone.type || '').toLowerCase();
      if (zoneType === 'city') {
        groups.city.push(zone);
      } else if (zoneType === 'hunting' || zoneType === 'pack') {
        groups.hunting.push(zone);
      } else if (zoneType === 'resource' || zoneType === 'mining') {
        groups.resource.push(zone);
      }
    });
    return groups;
  }, [subzones]);

  const cityStations = useMemo(
    () => npcsInLocation.filter((npc) => npc.type === 'crafting_station'),
    [npcsInLocation]
  );

  const cityNpcs = useMemo(
    () => npcsInLocation.filter((npc) => npc.type !== 'crafting_station'),
    [npcsInLocation]
  );

  const cityQuestNpcs = useMemo(
    () => cityNpcs.filter((npc) => npc.type === 'quest_giver'),
    [cityNpcs]
  );

  const cityMerchants = useMemo(
    () => cityNpcs.filter((npc) => npc.type === 'merchant' || npc.type === 'broker'),
    [cityNpcs]
  );

  const getResourceHint = (name = '') => {
    const n = String(name).toLowerCase();
    if (n.includes('шахт') || n.includes('руд')) return '⛏️ Рудная точка';
    if (n.includes('гора') || n.includes('кам')) return '🪨 Каменная точка';
    if (n.includes('лес') || n.includes('берез') || n.includes('дерев')) return '🌲 Лесная точка';
    return '📦 Точка добычи';
  };

  const getMobTierLabel = (tier = '') => {
    const normalized = String(tier || '').toLowerCase();
    if (normalized === 'weak') return 'Слабый';
    if (normalized === 'normal') return 'Обычный';
    if (normalized === 'strong') return 'Сильный';
    if (normalized === 'boss') return 'Босс';
    return 'Обычный';
  };

  const getMobDisplayName = (mob) => {
    const isBoss = String(mob?.mob_tier || '').toLowerCase() === 'boss' || Boolean(mob?.is_boss);
    return isBoss ? `${mob?.name || ''} (Босс)` : (mob?.name || '');
  };

  if (loading) {
    return (
      <div className="app loading-screen">
        <div className="loader"></div>
        <h2>Загрузка CodeX of Honor...</h2>
      </div>
    );
  }

  if (inWorld) {
    const hpPercent = selectedCharacter ? (selectedCharacter.health_points / selectedCharacter.max_health_points) * 100 : 100;
    const mpPercent = selectedCharacter ? (selectedCharacter.magic_points / selectedCharacter.max_magic_points) * 100 : 100;
    const activeZoneId = Number(world?.zone?.id || 0);
    const activeCityZone = subzonesByType.city.find((zone) => Number(zone.zone_id) === activeZoneId) || null;
    const isInCityZone = Boolean(activeCityZone);
    const cityZonesSorted = [...subzonesByType.city].sort((a, b) => Number(a.distance || 0) - Number(b.distance || 0));
    const nearestCityZone = (isInCityZone
      ? cityZonesSorted[0]
      : cityZonesSorted.find((zone) => Number(zone.distance || 0) > 0) || cityZonesSorted[0]) || null;
    const nearestCityDistanceDisplay = (() => {
      if (Number.isFinite(Number(nearestCityDistanceM))) {
        const value = Number(nearestCityDistanceM);
        if (!isInCityZone && value <= 0) {
          const fallback = Number(nearestCityZone?.distance || 0);
          return fallback > 0 ? fallback : value;
        }
        return value;
      }
      const fallback = Number(nearestCityZone?.distance || 0);
      return Number.isFinite(fallback) ? fallback : null;
    })();
    const activeHuntingZoneId = subzonesByType.hunting.some((zone) => Number(zone.zone_id) === activeZoneId)
      ? activeZoneId
      : 0;

    // Tab content render helper
    const renderTabContent = () => {
      switch(activeTab) {
        case 'world':
          return (
            <div className="zones-shell">
              <div className="zones-subtabs">
                <button
                  className={`zones-subtab ${worldSubTab === 'worldmap' ? 'active' : ''}`}
                  onClick={() => setWorldSubTab('worldmap')}
                >
                  Мир ({worldMapCards.length})
                </button>
                <button
                  className={`zones-subtab ${worldSubTab === 'city' ? 'active' : ''}`}
                  onClick={() => setWorldSubTab('city')}
                >
                  Город ({subzonesByType.city.length})
                </button>
                <button
                  className={`zones-subtab ${worldSubTab === 'hunting' ? 'active' : ''}`}
                  onClick={() => setWorldSubTab('hunting')}
                >
                  Охота ({subzonesByType.hunting.length})
                </button>
                <button
                  className={`zones-subtab ${worldSubTab === 'resource' ? 'active' : ''}`}
                  onClick={() => setWorldSubTab('resource')}
                >
                  Добыча ({subzonesByType.resource.length})
                </button>
              </div>

              <div className="zones-subtab-content">
                {worldSubTab === 'worldmap' && (
                  <div>
                    <h3>Карты мира</h3>
                    {worldMapCards.length === 0 ? (
                      <p style={{ color: '#888' }}>Карты мира не найдены.</p>
                    ) : (
                      <div className="zone-list">
                        {worldMapCards.map((loc) => (
                          <div key={loc.name} className="zone-item">
                            <div className="zone-info">
                              <div className="zone-name">
                                <EntityIcon
                                  name={loc.name === 'Аурис' ? 'Город новичков Аурис' : loc.name}
                                  category="objects"
                                  iconsIndex={generatedIcons}
                                  fallback={loc.name === 'Аурис' ? '🏙️' : '🌍'}
                                />{' '}
                                {loc.name}
                                {loc.id && selectedWorldMapId === loc.id ? ' (текущая)' : ''}
                                <span
                                  style={{
                                    marginLeft: '8px',
                                    padding: '2px 8px',
                                    borderRadius: '999px',
                                    fontSize: '11px',
                                    fontWeight: 700,
                                    color: loc.inDevelopment ? '#ffd7d7' : '#d9ffef',
                                    background: loc.inDevelopment ? 'rgba(255, 82, 82, 0.22)' : 'rgba(16, 185, 129, 0.22)',
                                    border: loc.inDevelopment ? '1px solid rgba(255, 110, 110, 0.5)' : '1px solid rgba(52, 211, 153, 0.5)',
                                  }}
                                >
                                  {loc.status}
                                </span>
                              </div>
                              <div className="zone-details">
                                <span>Уровни: {loc.levelRange}</span>
                                <span>Тип: {loc.typeLabel}</span>
                                <span>Статус: {loc.status}</span>
                              </div>
                            </div>
                            <div className="zone-actions">
                              <button
                                className={`btn-small ${loc.inDevelopment ? '' : 'btn-primary'}`}
                                disabled={loc.inDevelopment || !loc.id}
                                onClick={async () => {
                                  if (loc.inDevelopment || !loc.id) return;
                                  await loadLocationSubzones(loc.id, selectedCharId);
                                  setWorldSubTab('city');
                                  setCityTab('npcs');
                                  setCityInteractionsActive(false);
                                }}
                              >
                                {loc.inDevelopment ? 'В разработке' : 'Открыть зоны'}
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {worldSubTab === 'city' && (
                  <div className="location-overview">
                    <h3>
                      <EntityIcon
                        name={'Город новичков Аурис'}
                        category="objects"
                        iconsIndex={generatedIcons}
                        fallback="🏙️"
                      />{' '}
                      {'Город новичков Аурис'}
                    </h3>
                    <p>{world?.location?.description || 'Городская область: здесь доступны НПС и ремесленные станки.'}</p>
                    <div className="location-overview-stats">
                      <span>🛠️ Станки: {cityStations.length}</span>
                      <span>👥 НПС: {cityNpcs.length}</span>
                      <span>
                        🏙️ До Ауриса: {Number.isFinite(Number(nearestCityDistanceDisplay))
                          ? `${Number(nearestCityDistanceDisplay).toFixed(1)}м`
                          : 'нет данных'}
                      </span>
                      {movement.is_moving && <span>🏃 Движение к {movement.target_name}</span>}
                    </div>

                    {!isInCityZone && nearestCityZone && (
                      <div style={{ marginTop: '12px' }}>
                        <div style={{ marginBottom: '8px', opacity: 0.9 }}>
                          Ближайшая городская зона: <strong>{nearestCityZone.name}</strong> ({Number(nearestCityZone.distance || 0).toFixed(1)}м)
                        </div>
                        <button
                          className="btn-small btn-primary"
                          onClick={() => {
                            if (nearestCityZone.can_interact) {
                              interactWithObject('subzone', nearestCityZone.zone_id, 'enter');
                            } else {
                              startMovement('subzone', nearestCityZone.zone_id, nearestCityZone.name);
                            }
                          }}
                        >
                          {nearestCityZone.can_interact ? 'Войти в город' : 'Сблизиться с городом'}
                        </button>
                      </div>
                    )}

                    <div style={{ marginTop: '18px' }}>
                      <div className="zones-subtabs" style={{ marginBottom: '12px' }}>
                        <button
                          className={`zones-subtab ${cityTab === 'npcs' ? 'active' : ''}`}
                          onClick={() => setCityTab('npcs')}
                        >
                          НПС и квесты
                        </button>
                        <button
                          className={`zones-subtab ${cityTab === 'stations' ? 'active' : ''}`}
                          onClick={() => setCityTab('stations')}
                        >
                          Станки
                        </button>
                      </div>

                      {isInCityZone && !cityInteractionsActive && (
                        <div style={{ marginTop: '10px' }}>
                          <button
                            className="btn-small btn-primary"
                            onClick={() => setCityInteractionsActive(true)}
                          >
                            Активировать городские взаимодействия
                          </button>
                        </div>
                      )}
                      {!isInCityZone && (
                        <p style={{ color: '#888', marginTop: '10px' }}>
                          Вы находитесь вне городской зоны. Сначала подойдите к Аурису и войдите в город.
                        </p>
                      )}
                    </div>

                    {cityTab === 'npcs' && (
                      <div style={{ marginTop: '18px' }}>
                        <h4>Квестовые НПС</h4>
                        {isInCityZone && !cityInteractionsActive && (
                          <p style={{ color: '#888' }}>Сначала нажмите «Активировать городские взаимодействия», чтобы открыть квестовых НПС.</p>
                        )}
                        {isInCityZone && cityInteractionsActive && cityQuestNpcs.length === 0 && (
                          <p style={{ color: '#888' }}>В этой городской области пока нет квестовых НПС.</p>
                        )}
                        {isInCityZone && cityInteractionsActive && cityQuestNpcs.length > 0 && (
                          <div className="zone-list">
                            {cityQuestNpcs.map((npc) => {
                              const npcId = npc.npc_id;

                              return (
                                <div key={npcId} className="zone-item">
                                  <div className="zone-info">
                                    <div className="zone-name">
                                      <EntityIcon
                                        name={npc.name}
                                        category="npcs"
                                        iconsIndex={generatedIcons}
                                        fallback="👤"
                                      />{' '}
                                      {npc.name}
                                    </div>
                                    <div className="zone-details">
                                      <span>Тип: {npc.type}</span>
                                      {npc.interaction_options?.length > 0 && <span>{npc.interaction_options.join(', ')}</span>}
                                    </div>
                                  </div>
                                  <div className="zone-actions">
                                    <button className="btn-small btn-primary" onClick={() => interactWithObject('npc', npcId, 'quest')}>
                                      Квесты
                                    </button>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    )}

                    {cityTab === 'npcs' && (
                      <div style={{ marginTop: '18px' }}>
                        <h4>Торговцы</h4>
                        {isInCityZone && !cityInteractionsActive && (
                          <p style={{ color: '#888' }}>Сначала нажмите «Активировать городские взаимодействия», чтобы открыть торговлю.</p>
                        )}
                        {isInCityZone && cityInteractionsActive && cityMerchants.length === 0 && (
                          <p style={{ color: '#888' }}>В этой городской области пока нет торговцев.</p>
                        )}
                        {isInCityZone && cityInteractionsActive && cityMerchants.length > 0 && (
                          <div className="zone-list">
                            {cityMerchants.map((npc) => {
                              const npcId = npc.npc_id;
                              const npcAction = npc.type === 'broker' ? 'auction' : 'buy';

                              return (
                                <div key={npcId} className="zone-item">
                                  <div className="zone-info">
                                    <div className="zone-name">
                                      <EntityIcon
                                        name={npc.name}
                                        category="npcs"
                                        iconsIndex={generatedIcons}
                                        fallback="👤"
                                      />{' '}
                                      {npc.name}
                                    </div>
                                    <div className="zone-details">
                                      <span>Тип: {npc.type}</span>
                                      {npc.interaction_options?.length > 0 && <span>{npc.interaction_options.join(', ')}</span>}
                                    </div>
                                  </div>
                                  <div className="zone-actions">
                                    <button className="btn-small btn-primary" onClick={() => interactWithObject('npc', npcId, npcAction)}>
                                      {npcAction === 'buy' ? 'Купить' : 'Аукцион'}
                                    </button>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    )}

                    {cityTab === 'stations' && (
                    <div style={{ marginTop: '18px' }}>
                      <h4>Станки</h4>
                      {!isInCityZone ? (
                        <p style={{ color: '#888' }}>Станки доступны только внутри городской зоны.</p>
                      ) : cityStations.length === 0 ? (
                        <p style={{ color: '#888' }}>В этой городской области станки не найдены.</p>
                      ) : (
                        <div className="zone-list">
                          {cityStations.map((npc) => (
                            <div key={npc.npc_id} className="zone-item">
                              <div className="zone-info">
                                <div className="zone-name">
                                  <EntityIcon name={npc.name} category="objects" iconsIndex={generatedIcons} fallback="🛠️" /> {npc.name}
                                </div>
                                <div className="zone-details">
                                  <span>Тип: станок</span>
                                </div>
                              </div>
                              <div className="zone-actions">
                                <button className="btn-small btn-primary" onClick={() => interactWithObject('npc', npc.npc_id, 'craft')}>
                                  Крафт
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                    )}
                  </div>
                )}

                {(worldSubTab === 'hunting' || worldSubTab === 'resource') && (
                  <div>
                    <div style={{ marginBottom: '10px', opacity: 0.9 }}>
                      🏙️ До ближайшего города:{' '}
                      {Number.isFinite(Number(nearestCityDistanceDisplay))
                        ? `${Number(nearestCityDistanceDisplay).toFixed(1)}м`
                        : 'нет данных'}
                    </div>
                    {(() => {
                      const zonesForTab = worldSubTab === 'hunting' && activeHuntingZoneId
                        ? subzonesByType.hunting.filter((zone) => Number(zone.zone_id) === activeHuntingZoneId)
                        : subzonesByType[worldSubTab];
                      return (
                        <>
                    {zonesForTab.length === 0 && (
                      <p style={{ color: '#888' }}>
                        {worldSubTab === 'hunting'
                          ? 'Охотничьи локации не найдены для текущей области.'
                          : 'Точки добычи не найдены для текущей области.'}
                      </p>
                    )}
                    <div className="zone-group">
                      <div className="zone-group-header">
                        <span className="zone-group-icon">{areaMeta[worldSubTab].icon}</span>
                        <span className="zone-group-title">{areaMeta[worldSubTab].name}</span>
                        <span className="zone-group-count">{zonesForTab.length}</span>
                      </div>
                      <div className="zone-list">
                        {zonesForTab.map((zone) => (
                          <div key={zone.zone_id} className="zone-item">
                            <div className="zone-info">
                              <div className="zone-name">
                                <EntityIcon
                                  name={zone.name}
                                  category="objects"
                                  iconsIndex={generatedIcons}
                                  fallback={worldSubTab === 'hunting' ? '🐾' : '⛏️'}
                                />{' '}
                                {zone.name}
                              </div>
                              <div className="zone-details">
                                <span>📏 {zone.distance}м</span>
                                <span>⭐ {zone.level_range}</span>
                                {worldSubTab === 'resource' && <span>{getResourceHint(zone.name)}</span>}
                              </div>
                            </div>
                            <div className="zone-actions">
                              {activeZoneId === Number(zone.zone_id) ? (
                                <button
                                  className="btn-small btn-danger"
                                  onClick={() => interactWithObject('subzone', activeZoneId || zone.zone_id, 'exit_zone')}
                                >
                                  Выйти
                                </button>
                              ) : zone.can_interact ? (
                                <button className="btn-small btn-success" onClick={() => interactWithObject('subzone', zone.zone_id, 'enter')}>
                                  Войти
                                </button>
                              ) : (
                                <button className="btn-small" onClick={() => startMovement('subzone', zone.zone_id, zone.name)}>
                                  Идти
                                </button>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                        </>
                      );
                    })()}

                    {worldSubTab === 'hunting' && (
                      <div style={{ marginTop: '16px' }}>
                        <h4>Мобы в зоне</h4>
                        {mobs.length === 0 ? (
                          <p style={{ color: '#888' }}>Войдите в зону охоты, чтобы увидеть типы мобов и счетчики респавна.</p>
                        ) : (
                          <div className="zone-list">
                            {mobs.map((mob) => (
                              <div key={mob.id} className="zone-item">
                                <div className="zone-info">
                                  <div className="zone-name">
                                    {String(mob.mob_tier || '').toLowerCase() === 'boss' ? '😈 ' : ''}
                                    <EntityIcon
                                      name={getMobDisplayName(mob)}
                                      category="mobs"
                                      iconsIndex={generatedIcons}
                                      fallback={String(mob.mob_tier || '').toLowerCase() === 'boss' ? '😈' : '🐺'}
                                    />{' '}
                                    {getMobDisplayName(mob)}
                                  </div>
                                  <div className="zone-details">
                                    <span>⭐ Уровень: {mob.level}</span>
                                    <span>🏷️ Тип: {getMobTierLabel(mob.mob_tier)}</span>
                                    <span>📊 Живые: {mob.alive_count ?? 0}/{mob.total_count ?? 0}</span>
                                    <span>⏱️ Респавн: {mob.respawn_seconds ?? 0}с/ед.</span>
                                    {(mob.alive_count ?? 0) < (mob.total_count ?? 0) && (
                                      <span>⌛ До следующего: {mob.next_respawn_in_seconds ?? 0}с</span>
                                    )}
                                    {!!mob.party_required && <span>👥 Только в пати</span>}
                                    {String(mob.mob_tier || '').toLowerCase() === 'boss' && <span>⚠️ Рекомендуется группа</span>}
                                  </div>
                                </div>
                                <div className="zone-actions">
                                  <button
                                    className={`btn-small ${selectedMobId === mob.id ? 'btn-success' : 'btn-primary'}`}
                                    disabled={(mob.alive_count ?? 0) <= 0}
                                    onClick={() => selectMobForCombat(mob)}
                                  >
                                    {(mob.alive_count ?? 0) <= 0 ? 'Истреблен' : 'Атаковать'}
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          );

        case 'chat': {
          const activeChannelMessages = chatSubTab === 'system'
            ? systemChatMessages
            : (chatMessagesByChannel[chatSubTab] || []);
          const worldChannelLabel = chatChannels.find((c) => c.id === 'world')?.label || 'Мир - Аурис';

          return (
            <div>
              <h3>💬 Глобальный чат</h3>
              <div className="zones-subtabs" style={{ marginBottom: '12px' }}>
                <button
                  className={`zones-subtab ${chatSubTab === 'world' ? 'active' : ''}`}
                  onClick={async () => {
                    setChatSubTab('world');
                    await loadChatHistory('world');
                  }}
                >
                  {worldChannelLabel}
                </button>
                <button
                  className={`zones-subtab ${chatSubTab === 'help' ? 'active' : ''}`}
                  onClick={async () => {
                    setChatSubTab('help');
                    await loadChatHistory('help');
                  }}
                >
                  Помощь новичка
                </button>
                <button
                  className={`zones-subtab ${chatSubTab === 'trade' ? 'active' : ''}`}
                  onClick={async () => {
                    setChatSubTab('trade');
                    await loadChatHistory('trade');
                  }}
                >
                  Торговля
                </button>
                <button
                  className={`zones-subtab ${chatSubTab === 'system' ? 'active' : ''}`}
                  onClick={() => setChatSubTab('system')}
                >
                  Системный
                </button>
              </div>

              <div
                style={{
                  minHeight: '320px',
                  maxHeight: '420px',
                  overflowY: 'auto',
                  border: '1px solid #2d3748',
                  borderRadius: '10px',
                  padding: '10px',
                  background: '#0f172a'
                }}
              >
                {chatLoading && chatSubTab !== 'system' && <p style={{ color: '#94a3b8' }}>Загрузка чата...</p>}
                {!chatLoading && activeChannelMessages.length === 0 && (
                  <p style={{ color: '#94a3b8' }}>
                    {chatSubTab === 'system'
                      ? 'Системных событий пока нет.'
                      : 'Сообщений пока нет. Напишите первым.'}
                  </p>
                )}
                {activeChannelMessages.map((msg) => {
                  const dt = msg?.created_at ? new Date(msg.created_at) : null;
                  const tm = dt && !Number.isNaN(dt.getTime())
                    ? dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                    : '--:--';
                  const text = msg?.text || msg?.message || '';
                  const sender = msg?.sender_name || 'Система';
                  return (
                    <div key={msg.id || `${tm}_${text}`} style={{ marginBottom: '8px', paddingBottom: '8px', borderBottom: '1px solid #1e293b' }}>
                      <div style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '2px' }}>[{tm}] {sender}</div>
                      <div style={{ whiteSpace: 'pre-wrap', color: '#e2e8f0' }}>{text}</div>
                    </div>
                  );
                })}
              </div>

              {chatSubTab !== 'system' && (
                <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        sendChatMessage();
                      }
                    }}
                    maxLength={400}
                    placeholder="Введите сообщение..."
                    style={{
                      flex: 1,
                      padding: '10px',
                      borderRadius: '8px',
                      border: '1px solid #334155',
                      background: '#0b1220',
                      color: '#e2e8f0'
                    }}
                  />
                  <button className="btn btn-primary" onClick={sendChatMessage}>Отправить</button>
                </div>
              )}
            </div>
          );
        }

        case 'inventory':
          return (
            <div>
              <div className="equipment-row">
                {equipmentSlots.map((slot) => {
                  const equipped = equippedBySlot[slot];
                  return (
                    <div key={slot} className="equipment-slot-card">
                      <div className="equipment-slot-title">{slotLabels[slot] || slot}</div>
                      {equipped ? (
                        <>
                          <EntityIcon
                            name={equipped.name}
                            category="items"
                            iconsIndex={generatedIcons}
                            resolver={getItemIcon}
                            className="item-icon-img"
                            fallback={equipped.icon || '📦'}
                            fallbackClassName="item-icon"
                          />
                          <div className="equipment-item-name" title={buildItemTooltip(equipped)}>{equipped.name}</div>
                          <button className="btn-small" onClick={() => unequipItem(slot)}>Снять</button>
                        </>
                      ) : (
                        <div className="equipment-slot-empty">Пусто</div>
                      )}
                    </div>
                  );
                })}
              </div>

              <div style={{marginBottom: '20px'}}>
                <h3>💰 Валюта</h3>
                <div style={{display: 'flex', gap: '15px', marginTop: '10px'}}>
                  <div className="currency-item">
                    <span>🪙 Золото:</span>
                    <strong>{gold}</strong>
                  </div>
                  <div className="currency-item">
                    <span>🥈 Серебро:</span>
                    <strong>{silver}</strong>
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
                  const item = backpackItems[idx];
                  const canEquip = isItemEquippable(item);
                  return (
                    <div key={idx} className={`inventory-slot ${!item ? 'empty' : ''}`} title={item ? buildItemTooltip(item) : ''}>
                      {item ? (
                        <>
                          <EntityIcon
                            name={item.name}
                            category="items"
                            iconsIndex={generatedIcons}
                            resolver={getItemIcon}
                            className="item-icon-img"
                            fallback={item.icon || '📦'}
                            fallbackClassName="item-icon"
                          />
                          {item.quantity > 1 && <div className="item-count">{item.quantity}</div>}
                          {canEquip ? (
                            <button className="btn-equip-inline" onClick={() => equipItem(item.item_id)}>Надеть</button>
                          ) : (
                            <button className="btn-equip-inline" disabled title="Этот предмет нельзя надеть">
                              {item.type === 'consumable' ? 'Расходник' : 'Материал'}
                            </button>
                          )}
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
                      <tr>
                        <td>Бонус оружия:</td>
                        <td>
                          +{combatStats.combat.equipment_weapon_damage_min || 0}
                          -
                          +{combatStats.combat.equipment_weapon_damage_max || 0}
                        </td>
                      </tr>
                      <tr><td>Защита:</td><td>{combatStats.combat.armor_value}</td></tr>
                      <tr><td>Бонус брони:</td><td>+{combatStats.combat.equipment_armor_bonus || 0}</td></tr>
                      <tr><td>Крит. шанс:</td><td>{combatStats.combat.crit_chance}%</td></tr>
                      <tr><td>Шанс блока:</td><td>{combatStats.combat.block_chance}%</td></tr>
                      <tr><td>Скорость атаки:</td><td>{combatStats.combat.attack_speed} атак/мин</td></tr>
                    </tbody>
                  </table>

                  <h3 style={{marginTop: '20px'}}>📊 Характеристики</h3>
                  <div style={{marginBottom: '10px', fontWeight: 600}}>
                    Доступно очков характеристик: {combatStats.available_stat_points || 0}
                  </div>
                  <table className="compact-table">
                    <tbody>
                      <tr>
                        <td title="Влияет на физический урон и силу ударов">💪 Сила:</td>
                        <td style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span>{combatStats.stats.strength}</span>
                          <button
                            className="btn-small"
                            onClick={() => increaseSingleStat('strength')}
                            disabled={allocatingStats || Number(combatStats.available_stat_points || 0) <= 0}
                          >
                            +
                          </button>
                        </td>
                      </tr>
                      <tr>
                        <td title="Влияет на шанс попадания, блок и скорость атаки">🏃 Ловкость:</td>
                        <td style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span>{combatStats.stats.dexterity}</span>
                          <button
                            className="btn-small"
                            onClick={() => increaseSingleStat('dexterity')}
                            disabled={allocatingStats || Number(combatStats.available_stat_points || 0) <= 0}
                          >
                            +
                          </button>
                        </td>
                      </tr>
                      <tr>
                        <td title="Влияет на запас здоровья и снижение входящего урона">🛡️ Выносливость:</td>
                        <td style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span>{combatStats.stats.constitution}</span>
                          <button
                            className="btn-small"
                            onClick={() => increaseSingleStat('constitution')}
                            disabled={allocatingStats || Number(combatStats.available_stat_points || 0) <= 0}
                          >
                            +
                          </button>
                        </td>
                      </tr>
                      <tr>
                        <td title="Влияет на магический потенциал и эффективность умений">🧠 Интеллект:</td>
                        <td style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span>{combatStats.stats.intelligence}</span>
                          <button
                            className="btn-small"
                            onClick={() => increaseSingleStat('intelligence')}
                            disabled={allocatingStats || Number(combatStats.available_stat_points || 0) <= 0}
                          >
                            +
                          </button>
                        </td>
                      </tr>
                      <tr>
                        <td title="Влияет на поддержку, восстановление и магическую устойчивость">📿 Мудрость:</td>
                        <td style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span>{combatStats.stats.wisdom}</span>
                          <button
                            className="btn-small"
                            onClick={() => increaseSingleStat('wisdom')}
                            disabled={allocatingStats || Number(combatStats.available_stat_points || 0) <= 0}
                          >
                            +
                          </button>
                        </td>
                      </tr>
                      <tr>
                        <td title="Влияет на критические эффекты и редкие шансы">🎲 Удача:</td>
                        <td style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span>{combatStats.stats.luck}</span>
                          <button
                            className="btn-small"
                            onClick={() => increaseSingleStat('luck')}
                            disabled={allocatingStats || Number(combatStats.available_stat_points || 0) <= 0}
                          >
                            +
                          </button>
                        </td>
                      </tr>
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
                    <span className="ability-name-line">
                      <EntityIcon
                        name={ability.name}
                        category="abilities"
                        iconsIndex={generatedIcons}
                        resolver={getAbilityIcon}
                        className="ability-icon"
                        fallback="⚡"
                      />
                      {ability.name}
                    </span><br/>
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
                    <span className="ability-name-line">
                      <EntityIcon
                        name={ability.name}
                        category="abilities"
                        iconsIndex={generatedIcons}
                        resolver={getAbilityIcon}
                        className="ability-icon"
                        fallback="🔮"
                      />
                      {ability.name}
                    </span><br/>
                    <small>{ability.mana_cost} маны</small>
                  </button>
                ))}
              </div>

              <h3 style={{marginTop: '20px'}}>💎 Коины Умений</h3>
              <p>Доступно: <strong>{honorCoins}</strong> коинов</p>

              <h3 style={{marginTop: '20px'}}>🏛️ Магистр Способностей</h3>
              <p style={{ color: '#aaa' }}>
                Покупка уникальных способностей за очки чести. Завершено квестов: <strong>{skillShopMeta.completed_quests || 0}</strong>
              </p>
              {skillShopLoading ? (
                <p style={{ color: '#888' }}>Загрузка доступных способностей...</p>
              ) : purchasableAbilities.length === 0 ? (
                <p style={{ color: '#888' }}>Пока нет доступных уникальных способностей. Завершайте квесты и повышайте уровень.</p>
              ) : (
                <div className="quests-list" style={{ marginTop: '10px' }}>
                  {purchasableAbilities.map((ability) => {
                    const canBuy = Boolean(ability.requirements_met);
                    return (
                      <div key={ability.ability_id} className="quest-card" style={{ marginBottom: '10px' }}>
                        <div className="quest-info">
                          <h4 className="ability-card-title">
                            <EntityIcon
                              name={ability.name}
                              category="abilities"
                              iconsIndex={generatedIcons}
                              resolver={getAbilityIcon}
                              className="ability-icon"
                              fallback="⚡"
                            />
                            {ability.name}
                          </h4>
                          <p>{ability.description}</p>
                          <div className="quest-rewards">
                            <span>💎 Цена: {ability.honor_points_cost}</span>
                            <span>⭐ Уровень: {ability.unlocked_at_level}+</span>
                            <span>📜 Квестов: {ability.required_completed_quests}</span>
                          </div>
                        </div>
                        <button
                          className="btn btn-primary"
                          onClick={() => learnAbilityWithHonor(ability.ability_id)}
                          disabled={!canBuy}
                          title={canBuy ? 'Изучить способность' : 'Не выполнены требования или не хватает очков чести'}
                        >
                          Изучить
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
              
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
              <h3>📜 Доступные квесты {questSourceNpcName ? `(NPC: ${questSourceNpcName})` : ''}</h3>
              {availableQuests.length === 0 ? (
                <div className="quest-empty-state" style={{marginTop: '10px'}}>
                  <p style={{color: '#888'}}>Подойдите к нужному квестовому NPC и нажмите "Квесты"</p>
                  <button
                    className="btn btn-primary"
                    onClick={() => {
                      setActiveTab('world');
                      setError('Осмотритесь в областях: подойдите к NPC-квестодателю или перейдите в другую локацию.');
                    }}
                  >
                    Перейти в мир
                  </button>
                </div>
              ) : (
                <div className="quests-list">
                  {availableQuests.map((quest) => (
                    <div key={quest.id} className="quest-card">
                      <div className="quest-info">
                        <h4>
                          <EntityIcon
                            name={quest.title}
                            category="quests"
                            iconsIndex={generatedIcons}
                            fallback="📜"
                          />{' '}
                          {quest.title}
                        </h4>
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
                <div className="quest-empty-state" style={{marginTop: '10px'}}>
                  <p style={{color: '#888'}}>Нет активных квестов</p>
                  <button
                    className="btn btn-primary"
                    onClick={() => {
                      if (availableQuests.length > 0) {
                        acceptQuest(availableQuests[0].id);
                      }
                    }}
                    disabled={availableQuests.length === 0}
                  >
                    Взять первый квест
                  </button>
                </div>
              ) : (
                <div className="quests-list">
                  {activeQuests.map((quest) => (
                    <div key={quest.quest_id} className="quest-card active">
                      <div className="quest-info">
                        <h4>
                          <EntityIcon
                            name={quest.title}
                            category="quests"
                            iconsIndex={generatedIcons}
                            fallback="📘"
                          />{' '}
                          {quest.title}
                        </h4>
                        <p>{quest.description}</p>

                        {questProgressMap[quest.quest_id]?.quest_type === 'kill' && (
                          <div className="quest-progress-block">
                            {questProgressMap[quest.quest_id]?.progress?.map((target) => {
                              const ratio = target.required > 0
                                ? Math.min(100, Math.round((target.killed / target.required) * 100))
                                : 0;
                              return (
                                <div key={`${quest.quest_id}_${target.mob_id}`} className="quest-progress-item">
                                  <div className="quest-progress-head">
                                    <span>
                                      <EntityIcon
                                        name={target.mob_name}
                                        category="mobs"
                                        iconsIndex={generatedIcons}
                                        fallback="🐾"
                                      />{' '}
                                      {target.mob_name}
                                    </span>
                                    <strong>{target.killed}/{target.required}</strong>
                                  </div>
                                  <div className="quest-progress-bar">
                                    <div className="quest-progress-fill" style={{ width: `${ratio}%` }}></div>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                      <button
                        className="btn btn-success"
                        onClick={() => completeQuest(quest.quest_id)}
                        disabled={questProgressMap[quest.quest_id]?.all_completed === false}
                        title={questProgressMap[quest.quest_id]?.all_completed === false ? 'Сначала выполните цели квеста' : 'Сдать квест'}
                      >
                        {questProgressMap[quest.quest_id]?.all_completed === false ? 'Цели не выполнены' : 'Завершить'}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );

        case 'party':
          const playersAvailableForInvite = nearbyPlayers
            .filter((p) => !p.in_party)
            .filter((p) => p.name.toLowerCase().includes(partySearchTerm.trim().toLowerCase()));

          return (
            <div>
              {pendingInvitations.length > 0 && (
                <div style={{ marginBottom: '16px', padding: '12px', border: '1px solid #4b5563', borderRadius: '8px', background: '#111827' }}>
                  <h4 style={{ marginBottom: '10px' }}>Входящие приглашения</h4>
                  {pendingInvitations.map((inv) => (
                    <div key={inv.invitation_id} style={{ padding: '10px', border: '1px solid #374151', borderRadius: '6px', marginBottom: '8px' }}>
                      <div><strong>{inv.inviter_name}</strong> приглашает в <strong>{inv.party_name}</strong></div>
                      <div style={{ fontSize: '12px', color: '#9ca3af', marginTop: '4px' }}>
                        Уровень: {inv.inviter_level} • Локация: {inv.inviter_location || 'Неизвестно'}
                      </div>
                      <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                        <button className="btn-small btn-primary" onClick={() => acceptInvitation(inv.invitation_id)}>Принять</button>
                        <button className="btn-small" onClick={() => rejectInvitation(inv.invitation_id)}>Отклонить</button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {!partyInfo ? (
                <div>
                  <p style={{marginBottom: '15px', color: '#aaa'}}>Вы не в группе</p>
                  <input
                    type="text"
                    placeholder="Название группы"
                    value={partyNameInput}
                    onChange={(e) => setPartyNameInput(e.target.value)}
                    style={{ width: '100%', marginBottom: '8px', padding: '10px', borderRadius: '8px', border: '1px solid #374151', background: '#111827', color: '#f3f4f6' }}
                  />
                  <button 
                    className="btn btn-primary" 
                    onClick={() => createParty((partyNameInput || `Группа ${selectedCharacter?.name}`).trim())}
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

                  {partyInfo.leader.id === selectedCharId && (
                    <div style={{marginTop: '20px'}}>
                      <h4>Пригласить:</h4>
                      <input
                        type="text"
                        placeholder="Поиск игрока по имени"
                        value={partySearchTerm}
                        onChange={(e) => setPartySearchTerm(e.target.value)}
                        style={{ width: '100%', marginBottom: '8px', padding: '8px', borderRadius: '8px', border: '1px solid #374151', background: '#111827', color: '#f3f4f6' }}
                      />
                      {playersAvailableForInvite.map((player) => (
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
                      {playersAvailableForInvite.length === 0 && (
                        <div style={{ fontSize: '12px', color: '#9ca3af', marginTop: '6px' }}>
                          Подходящих игроков не найдено
                        </div>
                      )}
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
              <h1>CodeX of Honor</h1>
              <p>{selectedCharacter?.name} - {world?.location?.name}</p>
            </div>
            <div className="user-info">
              <button onClick={handleExitWorld} className="btn btn-world-back">Назад к персонажам</button>
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
              <span>🥈</span>
              <strong>{silver}</strong>
            </div>
            <div className="currency-item">
              <span>🎖️</span>
              <strong>{honorCoins}</strong>
            </div>
          </div>
        </div>

        {showTutorial && (
          <div className="tutorial-panel">
            <div className="tutorial-header">
              <h3>Первые шаги в Элдории</h3>
              <button className="tutorial-close" onClick={closeTutorial}>Скрыть</button>
            </div>
            <p className="tutorial-text">
              Добро пожаловать в CodeX of Honor. Твой путь героя начинается с простого цикла: найти квест, выполнить цель и получить награду.
            </p>
            <div className="tutorial-steps">
              <div className={`tutorial-step ${tutorialProgress.openedQuestsTab ? 'done' : ''}`}>
                1. Открой вкладку квестов, чтобы увидеть задания поблизости.
              </div>
              <div className={`tutorial-step ${tutorialProgress.acceptedQuest ? 'done' : ''}`}>
                2. Прими первый квест у квестодателя в локации.
              </div>
              <div className="tutorial-step">
                3. Перейди в область охоты, атакуй мобов и выполни условия.
              </div>
              <div className={`tutorial-step ${tutorialProgress.completedQuest ? 'done' : ''}`}>
                4. Сдай квест во вкладке квестов и получи опыт, золото и коины.
              </div>
            </div>
            <div className="tutorial-actions">
              <button className="btn btn-primary" onClick={() => setActiveTab('quests')}>Открыть квесты</button>
              <button className="btn btn-secondary" onClick={closeTutorial}>Понятно</button>
            </div>
          </div>
        )}

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
            className={`game-tab ${activeTab === 'world' ? 'active' : ''}`}
            onClick={() => setActiveTab('world')}
          >
            🗺️ Мир
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
            👥 <span className={pendingInvitesCount > 0 && activeTab !== 'party' ? 'party-tab-alert' : ''}>Группа</span>
            {partyInfo && ` (${partyInfo.current_members})`}
            {!partyInfo && pendingInvitesCount > 0 && ` (${pendingInvitesCount})`}
          </button>
          <button
            className={`game-tab ${activeTab === 'chat' ? 'active' : ''}`}
            onClick={() => setActiveTab('chat')}
          >
            💬 Чат
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
                <h4>
                  <EntityIcon
                    name={currentCombat.mob_name}
                    category="mobs"
                    iconsIndex={generatedIcons}
                    fallback="🧟"
                  />{' '}
                  {currentCombat.mob_name}
                </h4>
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

                {(currentCombat.status === 'ready' || currentCombat.status === 'active') && (
                  <div style={{ marginTop: '14px', display: 'flex', gap: '8px' }}>
                    {!autoCombatEnabled ? (
                      <button className="btn btn-success" onClick={startAutoCombat}>
                        Автобой до конца
                      </button>
                    ) : (
                      <button className="btn btn-danger" onClick={stopAutoCombat}>
                        Остановить автобой
                      </button>
                    )}
                    <button className="btn" onClick={leaveCombat}>
                      Уйти
                    </button>
                  </div>
                )}

                {(currentCombat.status === 'ready' || currentCombat.status === 'active') && autoCombatEnabled && (
                  <p style={{ marginTop: '8px', fontSize: '12px', color: '#86efac' }}>
                    Автобой активен: атаки продолжаются до финала боя.
                  </p>
                )}

                {currentCombat.status === 'victory' && (
                  <div style={{ marginTop: '12px' }}>
                    <h5>Награда</h5>
                    <p style={{ margin: '6px 0' }}>Опыт: +{currentCombat.exp_gained || 0}</p>
                    <p style={{ margin: '6px 0' }}>Золото: +{currentCombat.gold_gained || 0}</p>
                    <p style={{ margin: '6px 0' }}>Серебро: +{currentCombat.silver_gained || 0}</p>

                    {currentCombat.can_butcher && !currentCombat.butchered && (
                      <button className="btn btn-primary" onClick={() => butcherMob(currentCombat.mob_id)}>
                        Разделка
                      </button>
                    )}

                    {currentCombat.butchered && (
                      <p style={{ marginTop: '8px' }}>
                        Ресурсы получены: {(currentCombat.butchered_items || []).map((i) => `${i.name}x${i.quantity}`).join(', ') || 'нет'}
                      </p>
                    )}

                    {(!currentCombat.can_butcher || currentCombat.butchered) && (
                      <button className="btn btn-success" onClick={finishCombat}>
                        Завершить бой
                      </button>
                    )}
                  </div>
                )}

                {currentCombat.status === 'defeat' && (
                  <div style={{ marginTop: '12px' }}>
                    <h5>Поражение</h5>
                    <p style={{ margin: '6px 0' }}>Потеря опыта: -{currentCombat.exp_lost || 0}</p>
                    {currentCombat.death_territory && <p style={{ margin: '6px 0' }}>Территория: {currentCombat.death_territory}</p>}
                    {(currentCombat.dropped_items || []).length > 0 && (
                      <p style={{ margin: '6px 0' }}>
                        Потеряно: {currentCombat.dropped_items.map((i) => `${i.name}x${i.quantity}`).join(', ')}
                      </p>
                    )}
                    <button className="btn btn-success" onClick={finishCombat}>
                      Завершить бой
                    </button>
                  </div>
                )}

                {currentCombat.status === 'fled' && (
                  <div style={{ marginTop: '12px' }}>
                    <button className="btn btn-success" onClick={finishCombat}>
                      Завершить бой
                    </button>
                  </div>
                )}
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
                приглашает вас в группу <strong>{currentInvitation.party_name}</strong><br/>
                Локация: <strong>{currentInvitation.inviter_location || 'Неизвестно'}</strong>
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

        {showQuestModal && (
          <div className="modal-overlay" onClick={() => setShowQuestModal(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '760px', width: '92%' }}>
              <h3>📜 Квесты от NPC: {questModalNpcName || 'Квестодатель'}</h3>
              <p style={{ marginTop: '8px', marginBottom: '12px', color: '#9ca3af' }}>
                Выберите квест для принятия. Уже взятые квесты отмечены.
              </p>
              <div style={{ maxHeight: '430px', overflowY: 'auto', display: 'grid', gap: '8px' }}>
                {questModalQuests.length === 0 && (
                  <div style={{ color: '#9ca3af' }}>У этого NPC пока нет доступных квестов.</div>
                )}
                {questModalQuests.map((quest) => {
                  const accepted = Boolean(quest._accepted) || activeQuestIdSet.has(quest.id);
                  return (
                    <div key={quest.id} className="quest-card" style={{ marginBottom: '0' }}>
                      <div className="quest-info">
                        <h4>
                          <EntityIcon
                            name={quest.title}
                            category="quests"
                            iconsIndex={generatedIcons}
                            fallback="📜"
                          />{' '}
                          {quest.title}
                        </h4>
                        <p>{quest.description}</p>
                        <div className="quest-rewards">
                          <span>⭐ Опыт: {quest.reward_experience}</span>
                          <span>💰 Золото: {quest.reward_gold}</span>
                        </div>
                      </div>
                      <button
                        className={`btn ${accepted ? 'btn-secondary' : 'btn-success'}`}
                        onClick={() => !accepted && acceptQuest(quest.id)}
                        disabled={accepted}
                      >
                        {accepted ? 'Квест принят' : 'Принять'}
                      </button>
                    </div>
                  );
                })}
              </div>
              <button className="btn btn-secondary" style={{ width: '100%', marginTop: '12px' }} onClick={() => setShowQuestModal(false)}>
                Закрыть
              </button>
            </div>
          </div>
        )}

        {showShopModal && (
          <div className="modal-overlay" onClick={() => setShowShopModal(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '720px', width: '90%' }}>
              <h3>🛒 Торговля: {shopNpcName}</h3>
              <p style={{ marginTop: '8px', marginBottom: '12px', color: '#9ca3af' }}>
                Баланс: <strong>{gold}</strong> золота, <strong>{silver}</strong> серебра
              </p>

              <div style={{ display: 'flex', gap: '8px', marginBottom: '10px' }}>
                <button className={`btn ${shopMode === 'buy' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setShopMode('buy')}>
                  Купить
                </button>
                <button className={`btn ${shopMode === 'sell' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setShopMode('sell')}>
                  Продать
                </button>
              </div>

              <div style={{ maxHeight: '420px', overflowY: 'auto', display: 'grid', gap: '8px' }}>
                {(shopMode === 'buy' ? shopItems : sellItems).map((item) => (
                  <div
                    key={item.item_id}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '10px',
                      border: '1px solid #374151',
                      borderRadius: '8px',
                      background: '#111827'
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <EntityIcon
                          name={item.name}
                          category="items"
                          iconsIndex={generatedIcons}
                          resolver={getItemIcon}
                          fallback="🧰"
                        />
                        {item.name}
                      </div>
                      <div style={{ fontSize: '12px', color: '#9ca3af' }}>
                        {item.description || item.type}
                        {shopMode === 'sell' ? ` • В рюкзаке: ${item.quantity || 0}` : ''}
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <div style={{ fontSize: '13px', color: '#e5e7eb' }}>
                        {shopMode === 'buy' ? item.price_silver : item.sell_price_silver} серебра
                      </div>
                      {shopMode === 'buy' ? (
                        <button className="btn-small btn-primary" onClick={() => buyShopItem(item.item_id)}>Купить</button>
                      ) : (
                        <button className="btn-small btn-primary" onClick={() => sellShopItem(item.item_id)}>Продать</button>
                      )}
                    </div>
                  </div>
                ))}
                {(shopMode === 'buy' ? shopItems : sellItems).length === 0 && (
                  <div style={{ color: '#9ca3af' }}>У торговца пока нет доступных товаров.</div>
                )}
              </div>

              <button className="btn btn-secondary" style={{ width: '100%', marginTop: '12px' }} onClick={() => setShowShopModal(false)}>
                Закрыть
              </button>
            </div>
          </div>
        )}

        {showCraftModal && (
          <div className="modal-overlay" onClick={() => setShowCraftModal(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '760px', width: '92%' }}>
              <h3>⚒️ Крафт</h3>
              <p style={{ marginTop: '8px', marginBottom: '12px', color: '#9ca3af' }}>
                Простой цикл: выбери рецепт, проверь материалы, создавай предметы. Иногда срабатывает вдохновение (+1 предмет).
              </p>

              <div style={{ maxHeight: '430px', overflowY: 'auto', display: 'grid', gap: '8px' }}>
                {craftRecipes.map((recipe) => (
                  <div key={recipe.id} style={{ border: '1px solid #374151', borderRadius: '8px', padding: '10px', background: '#111827' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px' }}>
                      <div>
                        <div style={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <EntityIcon
                            name={recipe.result_item_name}
                            category="items"
                            iconsIndex={generatedIcons}
                            resolver={getItemIcon}
                            fallback="⚒️"
                          />
                          {recipe.result_item_name}
                        </div>
                        <div style={{ fontSize: '12px', color: '#9ca3af' }}>
                          Тип: {recipe.type} • Шанс: {recipe.success_rate}% • Время: {recipe.crafting_time_seconds}с
                        </div>
                      </div>
                      <button
                        className="btn-small btn-primary"
                        disabled={recipe.can_craft === false}
                        onClick={() => craftRecipe(recipe.id)}
                      >
                        Создать
                      </button>
                    </div>
                    <div style={{ marginTop: '8px', fontSize: '12px', color: '#cbd5e1' }}>
                      Материалы:{' '}
                      {Array.isArray(recipe.required_materials) && recipe.required_materials.length > 0
                        ? recipe.required_materials
                            .map((m) => `${m.item_name} ${m.have != null ? `${m.have}/` : ''}${m.quantity}`)
                            .join(', ')
                        : 'не требуются'}
                    </div>
                  </div>
                ))}
                {craftRecipes.length === 0 && <div style={{ color: '#9ca3af' }}>Рецепты не найдены.</div>}
              </div>

              <button className="btn btn-secondary" style={{ width: '100%', marginTop: '12px' }} onClick={() => setShowCraftModal(false)}>
                Закрыть
              </button>
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
            <h1>CodeX of Honor</h1>
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
                          <div className="char-meta">Раса: {char.race_name || 'Не выбрана'}</div>
                          <div className="char-meta">Класс: {char.class_name || 'Не выбран'}</div>
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
                            onClick={() => handleEnterWorld(char.id)}
                            className="btn btn-primary btn-small"
                          >
                            Войти в мир
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
                                <EntityIcon
                                  name={ability.name}
                                  category="abilities"
                                  iconsIndex={generatedIcons}
                                  resolver={getAbilityIcon}
                                  className="race-passive-icon"
                                  fallback="✨"
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
                                {cls.name} - {cls.description} (STR {cls?.base_stats?.strength ?? 10}, DEX {cls?.base_stats?.dexterity ?? 10}, CON {cls?.base_stats?.constitution ?? 10})
                              </option>
                            ))
                          ) : (
                            <option disabled>{classesLoading ? 'Загрузка классов...' : 'Нет доступных классов'}</option>
                          )}
                        </select>
                        {classesLoadError && <div className="field-hint field-hint-error">{classesLoadError}</div>}
                      </div>
                      {selectedClass && (
                        <div className="race-preview">
                          <div className="race-preview-title">Класс {selectedClass.name}: базовые характеристики</div>
                          <div className="race-passive-list" style={{ gap: '8px' }}>
                            <div className="race-passive-item"><span className="race-passive-text">HP: {selectedClass.base_health} | MP: {selectedClass.base_mana}</span></div>
                            <div className="race-passive-item"><span className="race-passive-text">💪 Сила: {selectedClass?.base_stats?.strength ?? 10}</span></div>
                            <div className="race-passive-item"><span className="race-passive-text">🏃 Ловкость: {selectedClass?.base_stats?.dexterity ?? 10}</span></div>
                            <div className="race-passive-item"><span className="race-passive-text">🛡️ Выносливость: {selectedClass?.base_stats?.constitution ?? 10}</span></div>
                            <div className="race-passive-item"><span className="race-passive-text">🧠 Интеллект: {selectedClass?.base_stats?.intelligence ?? 10}</span></div>
                            <div className="race-passive-item"><span className="race-passive-text">📿 Мудрость: {selectedClass?.base_stats?.wisdom ?? 10}</span></div>
                            <div className="race-passive-item"><span className="race-passive-text">🎲 Удача: {selectedClass?.base_stats?.luck ?? 10}</span></div>
                          </div>
                        </div>
                      )}
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

      </div>

      <footer className="footer">
        <p>CodeX of Honor 2026 • Made with ❤️ for all • MIT License</p>
      </footer>
    </div>
  );
}

export default App;
