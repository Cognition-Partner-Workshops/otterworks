import { useState } from "react";
import { Link } from "react-router-dom";
import type { FormEvent, ReactNode } from "react";
import { fixtures } from "@/fixtures/fixtures";
import type { ChatMessage, ChatReply } from "@/fixtures/types";
import { MarkdownText } from "@/components/MarkdownText";
import { Avatar, Panel, ResetDemoButton, formatUtc, personFor } from "@/components/shared";
import { loadChatMessages, sendChatMessage } from "@/stores/chatStore";

const reactionGlyphs: Record<string, string> = {
  "+1": "👍",
  eyes: "👀",
  pray: "🙏",
  raised_hands: "🙌",
  rotating_light: "🚨",
  white_check_mark: "✅",
  tada: "🎉",
  warning: "⚠️",
  thumbsup: "👍",
  heart: "❤️",
};

function ReactionChips({ reactions }: { reactions: ChatMessage["reactions"] }) {
  if (!reactions.length) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {reactions.map((reaction) => (
        <span key={reaction.name} className="rounded-full border border-otter-200 bg-white px-2 py-1 text-xs text-slate-700">
          {reactionGlyphs[reaction.name] ?? `:${reaction.name}:`} {reaction.count}
        </span>
      ))}
    </div>
  );
}

function MessageContent({ authorId, at, text, reactions }: { authorId: string; at: string; text: string; reactions: ChatMessage["reactions"] }) {
  const person = personFor(fixtures.people, authorId);
  return (
    <div className="flex gap-3">
      <Avatar person={person} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-2">
          <span className="font-semibold text-otter-900">{person.name}</span>
          {person.kind === "devin" && <span className="rounded bg-otter-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-otter-700">Devin</span>}
          {person.kind === "bot" && <span className="rounded bg-otter-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-otter-700">Bot</span>}
          <time className="text-xs text-slate-500">{formatUtc(at)}</time>
        </div>
        <div className="mt-1 leading-6 text-slate-700"><MarkdownText text={text} /></div>
        <ReactionChips reactions={reactions} />
      </div>
    </div>
  );
}

function Composer({ channelId, replyToId, onSend }: { channelId: string; replyToId?: string; onSend: (text: string) => void }) {
  const [text, setText] = useState("");
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!text.trim()) return;
    onSend(text);
    setText("");
  };
  return (
    <form onSubmit={handleSubmit} className="border-t border-otter-200 bg-white p-4">
      <label htmlFor="chat-composer" className="sr-only">{replyToId ? "Write a reply" : `Message #${channelId}`}</label>
      <div className="flex items-end gap-3">
        <textarea
          id="chat-composer"
          className="min-h-12 flex-1 resize-y rounded border border-otter-300 p-3 text-sm focus:border-otter-500 focus:outline-none"
          placeholder={replyToId ? "Write a reply..." : `Message #${channelId}`}
          value={text}
          onChange={(event) => setText(event.target.value)}
          rows={2}
        />
        <button className="rounded bg-otter-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-otter-700" type="submit">Send</button>
      </div>
    </form>
  );
}

function ChatLayout({ children, title, topic, channelId, replyToId, onSend }: { children: ReactNode; title: string; topic: string; channelId: string; replyToId?: string; onSend: (text: string) => void }) {
  const channels = fixtures.channels;
  return (
    <div className="mx-auto flex min-h-[calc(100vh-65px)] max-w-[1500px] overflow-hidden bg-white shadow-sm">
      <aside className="hidden w-64 shrink-0 border-r border-otter-200 bg-otter-900 p-4 text-white md:block">
        <Link to="/chat" className="block border-b border-white/15 pb-4 text-lg font-semibold text-white hover:text-white">OtterWorks</Link>
        <h2 className="mb-2 mt-5 text-xs font-semibold uppercase tracking-[0.15em] text-otter-200">Channels</h2>
        <nav aria-label="Chat channels" className="space-y-1">
          {channels.map((channel) => (
            <Link key={channel.id} to={`/chat/${channel.id}`} className={`block rounded px-3 py-2 text-sm ${channel.id === channelId ? "bg-white/15 font-semibold text-white" : "text-otter-100 hover:bg-white/10 hover:text-white"}`}>
              <span className="mr-1">#</span>{channel.id}
            </Link>
          ))}
        </nav>
      </aside>
      <section className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-otter-200 px-5 py-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">#{channelId}</p><h1 className="mt-1 text-xl font-semibold text-otter-900">{title}</h1><p className="mt-1 text-sm text-slate-600">{topic}</p></div>
            <ResetDemoButton />
          </div>
        </header>
        <div className="flex-1 space-y-6 overflow-y-auto px-5 py-6">{children}</div>
        <Composer channelId={channelId} replyToId={replyToId} onSend={onSend} />
      </section>
    </div>
  );
}

export function ChannelPage({ channelId }: { channelId: string }) {
  const channel = fixtures.channels.find((item) => item.id === channelId);
  const [revision, setRevision] = useState(0);
  if (!channel) {
    return <div className="mx-auto max-w-4xl px-5 py-8"><Panel title="Channel not found"><p>That channel is not in this workspace.</p></Panel></div>;
  }
  const messages = loadChatMessages(fixtures).filter((message) => message.channelId === channel.id);
  const onSend = (text: string) => {
    sendChatMessage(fixtures, channel.id, text);
    setRevision((value) => value + 1);
  };
  void revision;

  return (
    <ChatLayout title={`#${channel.id}`} topic={channel.topic} channelId={channel.id} onSend={onSend}>
      {messages.map((message) => (
        <article key={message.id} className="border-b border-otter-100 pb-5">
          <MessageContent authorId={message.authorId} at={message.at} text={message.text} reactions={message.reactions} />
          <Link className="ml-12 mt-3 inline-block text-sm font-semibold text-otter-600 hover:underline" to={`/chat/${channel.id}/t/${message.id}`}>
            {message.replies.length} {message.replies.length === 1 ? "reply" : "replies"}
          </Link>
        </article>
      ))}
    </ChatLayout>
  );
}

function ReplyContent({ reply }: { reply: ChatReply }) {
  return (
    <article className="border-b border-otter-100 pb-5">
      <MessageContent authorId={reply.authorId} at={reply.at} text={reply.text} reactions={reply.reactions} />
    </article>
  );
}

export function ThreadPage({ channelId, messageId }: { channelId: string; messageId: string }) {
  const channel = fixtures.channels.find((item) => item.id === channelId);
  const [revision, setRevision] = useState(0);
  if (!channel) return <div className="mx-auto max-w-4xl px-5 py-8"><Panel title="Thread not found"><p>That channel is not in this workspace.</p></Panel></div>;
  const parent = loadChatMessages(fixtures).find((message) => message.id === messageId && message.channelId === channel.id);
  if (!parent) return <div className="mx-auto max-w-4xl px-5 py-8"><Panel title="Thread not found"><p>That message could not be found.</p><Link to={`/chat/${channel.id}`} className="mt-3 inline-block hover:underline">Back to #{channel.id}</Link></Panel></div>;

  const onSend = (text: string) => {
    sendChatMessage(fixtures, channel.id, text, parent.id);
    setRevision((value) => value + 1);
  };
  void revision;
  return (
    <ChatLayout title="Thread" topic={channel.topic} channelId={channel.id} replyToId={parent.id} onSend={onSend}>
      <Link to={`/chat/${channel.id}`} className="text-sm font-medium hover:underline">Back to #{channel.id}</Link>
      <article className="border-b border-otter-200 pb-5">
        <MessageContent authorId={parent.authorId} at={parent.at} text={parent.text} reactions={parent.reactions} />
        <p className="ml-12 mt-4 text-xs font-semibold uppercase tracking-wide text-slate-500">{parent.replies.length} replies</p>
      </article>
      {parent.replies.map((reply) => <ReplyContent key={reply.id} reply={reply} />)}
    </ChatLayout>
  );
}
