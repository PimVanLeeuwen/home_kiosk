/** How the Alerts page and a message's page name who sent a message. */
const SOURCE_LABEL: Record<string, string> = {
  backup: 'Backup',
  watchtower: 'Watchtower',
  'uptime-kuma': 'Uptime Kuma',
  hub: 'Hub',
  'hub.test': 'Test',
  bot: 'Bot',
  briefing: 'Briefing',
  pinned: 'Pinned images',
  'github-mirror': 'GitHub mirror',
  explainer: 'Explainer',
  ai: 'AI',
  ups: 'UPS',
  paperless: 'Paperless',
}

export function sourceLabel(source: string): string {
  if (source.startsWith('rule.')) return 'Hub rule'
  return SOURCE_LABEL[source] ?? source
}
