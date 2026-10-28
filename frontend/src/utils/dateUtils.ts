import type { Conversation } from '@/types/conversation';

interface DateGroup {
  label: string;
  items: Conversation[];
}

export function groupConversationsByDate(conversations: Conversation[]): DateGroup[] {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const sevenDaysAgo = new Date(today.getTime() - 7 * 86400000);

  const groups: Record<string, Conversation[]> = {
    Hoy: [],
    Ayer: [],
    'Últimos 7 días': [],
    Anteriores: [],
  };

  for (const conv of conversations) {
    const d = new Date(conv.updated_at);
    if (d >= today) groups['Hoy'].push(conv);
    else if (d >= yesterday) groups['Ayer'].push(conv);
    else if (d >= sevenDaysAgo) groups['Últimos 7 días'].push(conv);
    else groups['Anteriores'].push(conv);
  }

  return Object.entries(groups)
    .filter(([, items]) => items.length > 0)
    .map(([label, items]) => ({ label, items }));
}

export function relativeDate(dateStr: string): string {
  const d = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return 'ahora';
  if (minutes < 60) return `hace ${minutes} min`;
  if (hours < 24) return `hace ${hours}h`;
  if (days < 7) return `hace ${days}d`;
  return d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' });
}
