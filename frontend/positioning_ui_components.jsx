{/* ===== ADD THESE SECTIONS TO THE inWorld RENDER ===== */}

{/* Movement Status Bar */}
{movement.is_moving && (
  <section className="card" style={{background: '#2a4a2a', border: '2px solid #4CAF50'}}>
    <div className="card-header">
      <h2>🏃 Движение к цели</h2>
    </div>
    <div className="card-content">
      <table className="stats-table">
        <tbody>
          <tr>
            <td><strong>Цель:</strong></td>
            <td>{movement.target_name}</td>
          </tr>
          <tr>
            <td><strong>Расстояние:</strong></td>
            <td>{movement.distance_remaining.toFixed(1)} метров</td>
          </tr>
          <tr>
            <td><strong>Прибытие через:</strong></td>
            <td>{movement.eta_seconds.toFixed(0)} секунд</td>
          </tr>
        </tbody>
      </table>
      <div style={{marginTop: '10px', background: '#1a1a1a', borderRadius: '4px', overflow: 'hidden'}}>
        <div style={{
          width: `${Math.max(5, 100 - (movement.distance_remaining / (movement.distance_remaining + movement.eta_seconds * 5) * 100))}%`,
          height: '20px',
          background: 'linear-gradient(90deg, #4CAF50, #81C784)',
          transition: 'width 1s linear'
        }}></div>
      </div>
    </div>
  </section>
)}

{/* Zones and NPCs Table */}
<section className="card">
  <div className="card-header">
    <h2>🗺️ Зоны и объекты</h2>
    <button onClick={loadLocationZones} className="btn-icon">🔄</button>
  </div>
  <div className="card-content">
    <table className="objects-table">
      <thead>
        <tr>
          <th>Название</th>
          <th>Тип</th>
          <th>Расстояние (м)</th>
          <th>Уровни</th>
          <th>Действия</th>
        </tr>
      </thead>
      <tbody>
        {zones.map((zone) => (
          <React.Fragment key={`zone-${zone.zone_id}`}>
            <tr style={{background: zone.is_aggressive ? '#3a2a2a' : '#2a2a3a'}}>
              <td><strong>{zone.name}</strong></td>
              <td>{zone.is_aggressive ? '⚔️ АГР' : '🌿 ПАС'}</td>
              <td>{zone.distance}</td>
              <td>{zone.level_range}</td>
              <td>
                {zone.can_interact ? (
                  <button 
                    className="btn-small btn-success" 
                    onClick={() => interactWithObject('zone', zone.zone_id, 'enter')}
                  >
                    Войти
                  </button>
                ) : (
                  <button 
                    className="btn-small" 
                    onClick={() => startMovement('zone', zone.zone_id, zone.name)}
                  >
                    Идти ({zone.distance}м)
                  </button>
                )}
              </td>
            </tr>
            {zone.mobs && zone.mobs.map((mob, idx) => (
              <tr key={`mob-${zone.zone_id}-${idx}`} style={{background: '#1a1a1a', fontSize: '0.9em'}}>
                <td style={{paddingLeft: '30px'}}>└─ {mob.name}</td>
                <td>{mob.level} lvl ({mob.aggression})</td>
                <td></td>
                <td>{mob.stars > 0 ? `${'⭐'.repeat(mob.stars)} Чемпион` : ''}</td>
                <td>
                  {zone.can_interact && (
                    <button 
                      className="btn-small btn-danger" 
                      onClick={() => attackMob(mob.id)}
                    >
                      Атаковать
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </React.Fragment>
        ))}
        
        {npcsInLocation.map((npc) => (
          <tr key={`npc-${npc.npc_id}`} style={{background: '#2a3a2a'}}>
            <td><strong>👨‍💼 {npc.name}</strong></td>
            <td>{npc.type}</td>
            <td>{npc.distance}</td>
            <td>{npc.level} lvl</td>
            <td>
              {npc.can_interact ? (
                <div style={{display: 'flex', gap: '5px', flexWrap: 'wrap'}}>
                  {npc.interaction_options.map((opt, idx) => (
                    <button 
                      key={idx}
                      className="btn-small" 
                      onClick={() => {
                        if (opt === 'Квесты') interactWithObject('npc', npc.npc_id, 'quest');
                        else if (opt === 'Сдать квест') interactWithObject('npc', npc.npc_id, 'turn_in_quest');
                        else if (opt === 'Купить') interactWithObject('npc', npc.npc_id, 'buy');
                        else if (opt === 'Продать') interactWithObject('npc', npc.npc_id, 'sell');
                        else if (opt === 'Аукцион') interactWithObject('npc', npc.npc_id, 'auction');
                      }}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              ) : (
                <button 
                  className="btn-small" 
                  onClick={() => startMovement('npc', npc.npc_id, npc.name)}
                >
                  Идти ({npc.distance}м)
                </button>
              )}
            </td>
          </tr>
        ))}
        
        {zones.length === 0 && npcsInLocation.length === 0 && (
          <tr>
            <td colSpan="5" className="no-data">Нет объектов. Нажмите обновить.</td>
          </tr>
        )}
      </tbody>
    </table>
  </div>
</section>

{/* Combat Log */}
{combatLog.length > 0 && (
  <section className="card">
    <div className="card-header">
      <h2>⚔️ Боевой лог</h2>
      <button onClick={() => setCombatLog([])} className="btn-small btn-danger">Очистить</button>
    </div>
    <div className="card-content" style={{maxHeight: '300px', overflowY: 'auto'}}>
      {combatLog.map((msg, idx) => (
        <div key={idx} style={{
          padding: '5px 10px',
          margin: '5px 0',
          background: '#1a1a1a',
          borderLeft: msg.includes('КРИТИЧЕСКИЙ') ? '3px solid #f44336' : 
                       msg.includes('промахнулся') ? '3px solid #999' :
                       msg.includes('повержен') ? '3px solid #4CAF50' : '3px solid #2196F3',
          borderRadius: '4px',
          fontSize: '0.9em'
        }}>
          {msg}
        </div>
      ))}
    </div>
  </section>
)}

{/* Combat Stats Panel */}
{combatStats && (
  <section className="card">
    <div className="card-header">
      <h2>📊 Боевые характеристики</h2>
      <button onClick={loadCombatStats} className="btn-icon">🔄</button>
    </div>
    <div className="card-content">
      <table className="stats-table">
        <tbody>
          <tr>
            <td><strong>Урон:</strong></td>
            <td>{combatStats.combat.damage_min} - {combatStats.combat.damage_max}</td>
          </tr>
          <tr>
            <td><strong>Шанс попадания:</strong></td>
            <td>{combatStats.combat.hit_chance}%</td>
          </tr>
          <tr>
            <td><strong>Шанс крита:</strong></td>
            <td>{combatStats.combat.crit_chance}%</td>
          </tr>
          <tr>
            <td><strong>Шанс блока:</strong></td>
            <td>{combatStats.combat.block_chance}%</td>
          </tr>
          <tr>
            <td><strong>Скорость атаки:</strong></td>
            <td>{combatStats.combat.attack_speed} атак/мин</td>
          </tr>
          <tr>
            <td><strong>Броня:</strong></td>
            <td>{combatStats.combat.armor_value}</td>
          </tr>
        </tbody>
      </table>
      <div style={{marginTop: '15px', padding: '10px', background: '#1a1a1a', borderRadius: '4px'}}>
        <div style={{fontSize: '0.85em', color: '#aaa'}}>
          <div>💪 Сила: {combatStats.stats.strength} | 🏃 Ловкость: {combatStats.stats.dexterity}</div>
          <div>🛡️ Выносливость: {combatStats.stats.constitution} | 🎲 Удача: {combatStats.stats.luck}</div>
        </div>
      </div>
    </div>
  </section>
)}

{/* Party Panel */}
<section className="card">
  <div className="card-header">
    <h2>👥 Группа</h2>
  </div>
  <div className="card-content">
    {!partyInfo ? (
      <div>
        <p>Вы не в группе</p>
        <button 
          className="btn btn-primary" 
          onClick={() => {
            const name = prompt('Название группы:');
            if (name) createParty(name);
          }}
        >
          Создать группу
        </button>
      </div>
    ) : (
      <div>
        <h3>{partyInfo.party_name}</h3>
        <p>Лидер: {partyInfo.leader.name} | Участников: {partyInfo.current_members}/{partyInfo.max_members}</p>
        <table className="stats-table" style={{marginTop: '10px'}}>
          <thead>
            <tr>
              <th>Имя</th>
              <th>Уровень</th>
              <th>HP</th>
              <th>Роль</th>
            </tr>
          </thead>
          <tbody>
            {partyInfo.members.map((member) => (
              <tr key={member.character_id}>
                <td>{member.name}</td>
                <td>{member.level}</td>
                <td>{member.hp}/{member.max_hp}</td>
                <td>{member.role === 'leader' ? '👑 Лидер' : 'Участник'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <button 
          className="btn btn-danger" 
          style={{marginTop: '10px'}}
          onClick={leaveParty}
        >
          {partyInfo.leader.id === selectedCharId ? 'Распустить группу' : 'Покинуть группу'}
        </button>
      </div>
    )}
  </div>
</section>
