// Add to App.jsx - New state variables and functions for positioning system

// ===== NEW STATE (add these to existing state) =====
const [zones, setZones] = useState([]);
const [npcsInLocation, setNpcsInLocation] = useState([]);
const [movement, setMovement] = useState({ is_moving: false, distance_remaining: 0, target_name: '' });
const [combatLog, setCombatLog] = useState([]);
const [partyInfo, setPartyInfo] = useState(null);
const [combatStats, setCombatStats] = useState(null);

// ===== POSITIONING FUNCTIONS =====

const loadLocationZones = async () => {
  try {
    const { data } = await api.get(`/world/zones/${world.location.id}?character_id=${selectedCharId}`);
    setZones(data.zones || []);
    setNpcsInLocation(data.npcs || []);
  } catch (err) {
    console.error('Failed to load zones:', err);
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
    // Start polling movement status
    startMovementPolling();
  } catch (err) {
    setError(err.response?.data?.detail || 'Ошибка движения');
  }
};

const checkMovementStatus = async () => {
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
      setError(`Прибыли к цели: ${data.target_name}`);
      loadLocationZones(); // Refresh zones
      return false; // Stop polling
    }
    return data.is_moving; // Continue polling if still moving
  } catch (err) {
    return false; // Stop polling on error
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
  }, 1000); // Update every second
};

const interactWithObject = async (targetType, targetId, action) => {
  try {
    const { data } = await api.post(`/world/interact/${selectedCharId}`, null, {
      params: { target_type: targetType, target_id: targetId, action }
    });
    
    if (data.success) {
      setError(data.message || 'Взаимодействие успешно');
      // Handle specific actions
      if (data.action === 'quest_list') {
        // Show quest dialog
        console.log('Quests:', data.quests);
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
    
    // Add to combat log
    setCombatLog(prev => [...data.combat_log, ...prev].slice(0, 50));
    
    if (data.mob_killed) {
      setError(`${data.exp_gained} опыта, ${data.gold_gained} золота`);
      loadLocationZones(); // Refresh to update mob HP
    }
    
    // Update character stats display
    loadCharacters();
  } catch (err) {
    setError(err.response?.data?.detail || 'Ошибка атаки');
  }
};

const loadCombatStats = async () => {
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
    const { data } = await api.post(`/party/create/${selectedCharId}`, null, {
      params: { party_name: partyName, is_public: false }
    });
    setError('Группа создана');
    loadPartyInfo();
  } catch (err) {
    setError(err.response?.data?.detail || 'Ошибка создания группы');
  }
};

const loadPartyInfo = async () => {
  try {
    const { data } = await api.get(`/party/my-party/${selectedCharId}`);
    setPartyInfo(data.in_party ? data : null);
  } catch (err) {
    console.error('Failed to load party:', err);
  }
};

const leaveParty = async () => {
  try {
    await api.post(`/party/leave/${selectedCharId}`);
    setPartyInfo(null);
    setError('Покинули группу');
  } catch (err) {
    setError(err.response?.data?.detail || 'Ошибка выхода из группы');
  }
};

// ===== CALL ON WORLD ENTER =====
// Add to your enterWorld function:
// loadLocationZones();
// loadCombatStats();
// loadPartyInfo();
