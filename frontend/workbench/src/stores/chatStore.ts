import type { ChatMessage, ChatReply, Fixtures } from "@/fixtures/types";

export const CHAT_STORAGE_KEY = "workbench.chat.v1";

function getStorage(storage?: Storage): Storage {
  return storage ?? window.localStorage;
}

export function loadChatMessages(fixtures: Fixtures, storage?: Storage): ChatMessage[] {
  try {
    const saved = getStorage(storage).getItem(CHAT_STORAGE_KEY);
    if (saved) {
      const parsed: unknown = JSON.parse(saved);
      if (Array.isArray(parsed)) return parsed as ChatMessage[];
    }
  } catch {
    return fixtures.messages.map((message) => ({ ...message, replies: [...message.replies] }));
  }
  return fixtures.messages.map((message) => ({ ...message, replies: [...message.replies] }));
}

export function sendChatMessage(
  fixtures: Fixtures,
  channelId: string,
  text: string,
  replyToId?: string,
  storage?: Storage,
  at = new Date().toISOString(),
): ChatMessage[] {
  const content = text.trim();
  const messages = loadChatMessages(fixtures, storage);
  if (!content || !fixtures.channels.some((channel) => channel.id === channelId)) return messages;

  if (replyToId) {
    const parent = messages.find((message) => message.id === replyToId && message.channelId === channelId);
    if (!parent) return messages;
    const reply: ChatReply = {
      id: `reply-${parent.replies.length + 1}`,
      authorId: fixtures.currentUserId,
      at,
      text: content,
      reactions: [],
    };
    parent.replies = [...parent.replies, reply];
  } else {
    messages.push({
      id: `message-${messages.length + 1}`,
      channelId,
      authorId: fixtures.currentUserId,
      at,
      text: content,
      reactions: [],
      replies: [],
    });
  }

  getStorage(storage).setItem(CHAT_STORAGE_KEY, JSON.stringify(messages));
  return messages;
}
