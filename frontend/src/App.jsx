import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = 'http://localhost:8000/api';

function App() {
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    checkHealth();
  }, []);

  const checkHealth = async () => {
    try {
      const response = await axios.get(`${API_URL}/health`);
      setHealth(response.data);
      setLoading(false);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1>🎮 DreaMMO</h1>
        <p>Text-Based MMORPG</p>
      </header>

      <main style={styles.main}>
        <section style={styles.section}>
          <h2>Server Status</h2>
          {loading && <p>Loading...</p>}
          {error && <p style={{ color: 'red' }}>Error: {error}</p>}
          {health && (
            <div style={styles.statusBox}>
              <p><strong>Status:</strong> {health.status}</p>
              <p><strong>App:</strong> {health.app}</p>
              <p><strong>Version:</strong> {health.version}</p>
              <p><strong>Database:</strong> {health.database}</p>
            </div>
          )}
        </section>

        <section style={styles.section}>
          <h2>Features Coming Soon</h2>
          <ul>
            <li>⚔️ Combat System</li>
            <li>🔨 Crafting & Resources</li>
            <li>📜 Quest System</li>
            <li>🗣️ NPCs & Dialogue</li>
            <li>👥 Factions & Social</li>
            <li>🏔️ Dungeons & Exploration</li>
          </ul>
        </section>

        <section style={styles.section}>
          <h2>Documentation</h2>
          <p>
            Check out the <a href="/api/docs">API Documentation</a> or 
            <a href="https://github.com/zxDOOMxz/DreaMMO"> GitHub Repository</a>
          </p>
        </section>
      </main>

      <footer style={styles.footer}>
        <p>Made with ❤️ for MMORPG lovers | MIT License</p>
      </footer>
    </div>
  );
}

const styles = {
  container: {
    minHeight: '100vh',
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: '#1a1a1a',
    color: '#e0e0e0',
    fontFamily: 'Arial, sans-serif',
  },
  header: {
    backgroundColor: '#0066cc',
    padding: '40px 20px',
    textAlign: 'center',
    borderBottom: '2px solid #00cc00',
  },
  main: {
    flex: 1,
    maxWidth: '800px',
    margin: '0 auto',
    padding: '40px 20px',
    width: '100%',
  },
  section: {
    marginBottom: '40px',
    padding: '20px',
    backgroundColor: '#2a2a2a',
    borderRadius: '4px',
    borderLeft: '4px solid #00cc00',
  },
  statusBox: {
    backgroundColor: '#1a1a1a',
    padding: '15px',
    borderRadius: '4px',
    fontFamily: 'monospace',
    fontSize: '14px',
  },
  footer: {
    backgroundColor: '#0a0a0a',
    padding: '20px',
    textAlign: 'center',
    borderTop: '1px solid #00cc00',
    fontSize: '14px',
  },
};

export default App;
