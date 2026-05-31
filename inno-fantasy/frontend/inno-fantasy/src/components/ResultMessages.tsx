type ResultMessagesProps = {
  title: string;
  messages: string[];
  tone: 'error' | 'warning';
};

export function ResultMessages({ title, messages, tone }: ResultMessagesProps) {
  if (messages.length === 0) {
    return null;
  }

  return (
    <div className={`message-list message-${tone}`}>
      <strong>{title}</strong>
      <ul>
        {messages.map((message) => (
          <li key={message}>{message}</li>
        ))}
      </ul>
    </div>
  );
}
