import { Mic, Send, Volume2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext.jsx';
import { useI18n } from '../contexts/I18nContext.jsx';
import { api } from '../services/api.js';
import { useSpeechToText, useTextToSpeech } from '../hooks/useSpeech.js';

export function Chat() {
  const { peerId } = useParams();
  const { socket, user } = useAuth();
  const { t } = useI18n();
  const [receiverId, setReceiverId] = useState(peerId || '');
  const [messageText, setMessageText] = useState('');
  const [messages, setMessages] = useState([]);
  const [onlineUsers, setOnlineUsers] = useState({});
  const [typing, setTyping] = useState(false);
  const bottomRef = useRef(null);
  const { speak, supported: ttsSupported } = useTextToSpeech();
  const speechToText = useSpeechToText({
    onResult: (text) => setMessageText(text)
  });

  useEffect(() => setReceiverId(peerId || ''), [peerId]);

  useEffect(() => {
    if (!receiverId) return;
    async function loadMessages() {
      const { data } = await api.get(`/messages/${receiverId}`);
      setMessages(data.messages);
      await api.patch(`/messages/${receiverId}/seen`);
      socket?.emit('messages-seen', { peerId: Number(receiverId) });
    }
    loadMessages();
  }, [receiverId, socket]);

  useEffect(() => {
    if (!socket) return;
    const onMessage = (message) => {
      setMessages((current) => [...current, message]);
      if (String(message.sender_id) === String(receiverId)) {
        api.patch(`/messages/${receiverId}/seen`);
        socket.emit('messages-seen', { peerId: Number(receiverId) });
      }
    };
    const onSeen = ({ messageIds, seenAt }) => {
      setMessages((current) =>
        current.map((message) =>
          messageIds.includes(message.message_id) ? { ...message, seen_at: message.seen_at || seenAt } : message
        )
      );
    };
    const onPresenceSnapshot = (users) => {
      setOnlineUsers(Object.fromEntries(users.map((entry) => [entry.userId, entry.online])));
    };
    const onPresence = ({ userId, online }) => {
      setOnlineUsers((current) => ({ ...current, [userId]: online }));
    };
    const onTyping = ({ senderId, isTyping }) => {
      if (String(senderId) === String(receiverId)) setTyping(isTyping);
    };
    socket.on('message-received', onMessage);
    socket.on('messages-seen', onSeen);
    socket.on('presence-snapshot', onPresenceSnapshot);
    socket.on('user-online', onPresence);
    socket.on('typing', onTyping);
    return () => {
      socket.off('message-received', onMessage);
      socket.off('messages-seen', onSeen);
      socket.off('presence-snapshot', onPresenceSnapshot);
      socket.off('user-online', onPresence);
      socket.off('typing', onTyping);
    };
  }, [receiverId, socket]);

  useEffect(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), [messages]);

  async function send(event) {
    event.preventDefault();
    if (!receiverId || !messageText.trim()) return;
    const payload = { receiverId: Number(receiverId), messageText: messageText.trim() };
    const { data } = await api.post('/messages', payload);
    setMessages((current) => [...current, data.message]);
    setMessageText('');
    socket?.emit('typing', { receiverId: Number(receiverId), isTyping: false });
  }

  return (
    <section className="chat-layout">
      <aside className="chat-side">
        <label className="field">
          <span>Receiver ID</span>
          <input value={receiverId} onChange={(e) => setReceiverId(e.target.value)} placeholder="Enter user id" />
        </label>
        <div className={`presence-pill ${onlineUsers[Number(receiverId)] ? 'online' : ''}`}>
          {onlineUsers[Number(receiverId)] ? 'Online' : 'Offline'}
        </div>
        <p>Open a user from search to populate this automatically.</p>
      </aside>
      <div className="chat-panel">
        <div className="messages">
          {messages.map((message) => (
            <div key={message.message_id || `${message.created_at}-${message.message_text}`} className={`message ${message.sender_id === user?.user_id ? 'mine' : ''}`}>
              <p>{message.message_text}</p>
              <time>
                {new Date(message.created_at).toLocaleString()}
                {message.sender_id === user?.user_id ? ` | ${message.seen_at ? 'Seen' : 'Sent'}` : ''}
              </time>
              {ttsSupported ? (
                <button className="speak-button" onClick={() => speak(message.message_text)} aria-label="Read message aloud">
                  <Volume2 size={14} />
                </button>
              ) : null}
            </div>
          ))}
          {typing ? <div className="typing">Typing...</div> : null}
          <div ref={bottomRef} />
        </div>
        <form className="composer" onSubmit={send}>
          <input
            value={messageText}
            onChange={(e) => {
              setMessageText(e.target.value);
              if (receiverId) socket?.emit('typing', { receiverId: Number(receiverId), isTyping: true });
            }}
            placeholder="Type a message"
          />
          {speechToText.supported ? (
            <button
              className="icon-button"
              type="button"
              onClick={speechToText.listening ? speechToText.stop : speechToText.start}
              aria-label="Speech to text"
            >
              <Mic size={18} />
            </button>
          ) : null}
          <button className="primary-button" type="submit"><Send size={18} />{t('send')}</button>
        </form>
      </div>
    </section>
  );
}
