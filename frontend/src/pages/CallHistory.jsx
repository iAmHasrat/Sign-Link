import { useEffect, useState } from 'react';
import { api } from '../services/api.js';

export function CallHistory() {
  const [calls, setCalls] = useState([]);

  useEffect(() => {
    api.get('/calls/history').then(({ data }) => setCalls(data.calls));
  }, []);

  return (
    <section className="page-stack">
      <div className="list-panel">
        {calls.map((call) => (
          <article className="history-row" key={call.call_id}>
            <div>
              <h3>{call.caller_name} → {call.receiver_name}</h3>
              <p>{new Date(call.start_time).toLocaleString()}</p>
            </div>
            <span className={`status-pill ${call.call_status}`}>{call.call_status}</span>
            <strong>{call.duration_seconds || 0}s</strong>
          </article>
        ))}
        {calls.length === 0 ? <p>No calls yet.</p> : null}
      </div>
    </section>
  );
}
