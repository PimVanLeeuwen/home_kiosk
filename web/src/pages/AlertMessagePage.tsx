import { ArrowLeft, BellOff, ExternalLink, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { PageHeader } from '../components/PageHeader'
import { SeverityPill } from '../components/alerts/SeverityPill'
import { TelegramText } from '../components/settings/TelegramText'
import { Button } from '../components/ui/Button'
import { buttonClass } from '../components/ui/buttonStyles'
import { Card, Surface } from '../components/ui/Card'
import { Loading, PageUnavailable } from '../components/ui/states'
import { sourceLabel } from '../lib/alertSources'
import { ApiError, sendJson } from '../lib/api'
import { cn } from '../lib/cn'
import { formatDuration, formatWhen } from '../lib/format'
import { serviceHref } from '../lib/links'
import type { Hosts, MessageExplanation, MessageLink, MessagePage, ServicesResponse, Severity } from '../lib/types'
import { useApi } from '../lib/useApi'
import { bodyHtml } from '../lib/phoneText'

const REFRESH_MS = 30_000

/** The dot on "Earlier", in the severity's colour. */
const DOT: Record<Severity, string> = { error: 'bg-down', warning: 'bg-warn', ok: 'bg-up', info: 'bg-accent-line' }

const day = new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
const clock = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit' })
const seconds = (from: string, to: Date) => (to.getTime() - new Date(from).getTime()) / 1000

/** A message's own page (M31): what a tap on a notification opens, for 7 days. */
export function AlertMessagePage() {
  const id = useParams().id ?? ''
  const { data, error, loading, reload } = useApi<MessagePage>(`/api/alerts/messages/${encodeURIComponent(id)}`, REFRESH_MS)
  if (loading && !data) return <Loading what="the message" />
  if (!data) {
    const missing = error instanceof ApiError && error.status === 404
    return missing ? (
      <Gone title="No such message" detail="The link may be from another hub, or the message was never logged." />
    ) : (
      <>
        <BackLink />
        <PageUnavailable what="This message" detail={error?.message} onRetry={reload} />
      </>
    )
  }
  if (data.expired) return <Gone title="This message has expired" detail="Message pages stay 7 days. It is still in the log on the Alerts page." />
  return <Message key={data.id} message={data} />
}

function BackLink() {
  return (
    <Link to="/alerts" viewTransition className="mb-4 inline-flex items-center gap-1.5 text-small text-muted hover:text-fg">
      <ArrowLeft aria-hidden="true" className="size-4" />
      Alerts
    </Link>
  )
}

function Gone({ title, detail }: { title: string; detail: string }) {
  return (
    <>
      <BackLink />
      <div className="mx-auto grid max-w-sm justify-items-center gap-3 py-16 text-center">
        <span className="grid size-16 place-items-center rounded-full border border-line text-faint">
          <BellOff aria-hidden="true" className="size-6" />
        </span>
        <h1 className="text-title font-semibold">{title}</h1>
        <p className="text-muted">{detail}</p>
        <Link to="/alerts" className={buttonClass('primary')}>
          Open Alerts
        </Link>
      </div>
    </>
  )
}

type Shown = Extract<MessagePage, { expired: false }>

function Message({ message }: { message: Shown }) {
  const now = new Date()
  const delivered =
    message.channel === 'ntfy' ? 'Sent to your phone (ntfy)' : message.channel === 'telegram' ? 'Sent on Telegram' : message.status === 'held' ? 'Held for the morning digest' : 'Not sent'
  return (
    <>
      <BackLink />
      <p className="mb-2 flex flex-wrap items-center gap-2 text-caption text-faint">
        <span>{formatWhen(message.ts, now)}</span>
        <span className="rounded-[6px] border border-glass-line bg-glass px-1.5 text-micro font-semibold tracking-[0.04em] text-muted">
          {sourceLabel(message.source)}
        </span>
        <SeverityPill severity={message.severity} />
      </p>
      <PageHeader title={message.title} />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.35fr)_minmax(300px,1fr)] lg:gap-6">
        <div className="grid content-start gap-4">
          {message.picture && (
            <img
              src={`/api/alerts/messages/${message.id}/picture`}
              alt="The picture sent with this message"
              width={1200}
              height={800}
              className="aspect-[3/2] w-full rounded-[14px] border border-line-soft bg-card object-cover"
            />
          )}
          {message.state && <StateStrip state={message.state} severity={message.severity} now={now} />}
          {bodyHtml(message.html) && (
            <Surface className="text-body leading-relaxed break-words whitespace-pre-wrap">
              <TelegramText html={bodyHtml(message.html)} />
            </Surface>
          )}
          <div className="hidden gap-0.5 text-caption text-faint lg:grid">
            <Foot message={message} delivered={delivered} />
          </div>
        </div>
        <div className="grid content-start gap-4">
          <Explanation message={message} />
          {message.links.length > 0 && <Links links={message.links} />}
          {message.earlier.length > 1 && <Earlier message={message} now={now} />}
          <div className="grid gap-0.5 text-caption text-faint lg:hidden">
            <Foot message={message} delivered={delivered} />
          </div>
        </div>
      </div>
    </>
  )
}

function Foot({ message, delivered }: { message: Shown; delivered: string }) {
  return (
    <>
      <span>
        {delivered} at {clock.format(new Date(message.sent_at ?? message.ts))}
        {message.error && message.channel === 'telegram' ? `; ${message.error}` : ''}
      </span>
      <span>This page stays until {day.format(new Date(message.expires_at))}</span>
    </>
  )
}

function StateStrip({ state, severity, now }: { state: NonNullable<Shown['state']>; severity: Severity; now: Date }) {
  const tone = !state.open ? 'border-up/30 bg-up/[0.07]' : severity === 'error' ? 'border-down/35 bg-down/[0.08]' : 'border-warn/35 bg-warn/[0.07]'
  const dot = !state.open ? 'bg-up' : severity === 'error' ? 'bg-down shadow-[0_0_10px_var(--color-down)]' : 'bg-warn shadow-[0_0_10px_var(--color-warn)]'
  return (
    <div role="status" className={cn('flex items-center gap-3 rounded-[14px] border px-4 py-3', tone)}>
      <span aria-hidden="true" className={cn('size-2.5 shrink-0 rounded-full', dot)} />
      <div>
        <p className="font-semibold">{state.open ? 'Still open' : `Resolved at ${clock.format(new Date(state.resolved_at!))}`}</p>
        <p className="text-small text-muted">
          {state.open
            ? `for ${formatDuration(seconds(state.opened_at, now))}`
            : `after ${formatDuration(seconds(state.opened_at, new Date(state.resolved_at!)))}`}
        </p>
      </div>
    </div>
  )
}

function Explanation({ message }: { message: Shown }) {
  const [kept, setKept] = useState<MessageExplanation | null>(message.explanation)
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<string>()
  if (!kept && !message.can_explain) return null

  async function ask() {
    setBusy(true)
    setProblem(undefined)
    try {
      setKept(await sendJson<MessageExplanation>('POST', `/api/alerts/messages/${message.id}/explain`, {}))
    } catch (err) {
      setProblem(err instanceof ApiError ? err.message : 'Asking failed.')
    } finally {
      setBusy(false)
    }
  }

  if (!kept)
    return (
      <div className="grid gap-2">
        <Button onClick={ask} disabled={busy}>
          <Sparkles aria-hidden="true" className="size-4" />
          {busy ? 'Asking Claude…' : 'Explain'}
        </Button>
        {problem && (
          <p role="alert" className="text-small text-down">
            {problem}
          </p>
        )}
      </div>
    )
  return (
    <Card title="Explained">
      <p className="text-caption font-semibold tracking-[0.04em] text-accent-fg">Likely cause</p>
      <p className="mb-3">{kept.cause}</p>
      <p className="text-caption font-semibold tracking-[0.04em] text-accent-fg">Try first</p>
      <p>{kept.todo}</p>
      <p className="mt-3 text-caption text-faint">Claude · asked {formatWhen(kept.asked_at)} · kept with this message</p>
    </Card>
  )
}

function Links({ links }: { links: MessageLink[] }) {
  const services = useApi<ServicesResponse>('/api/services')
  const hosts = useApi<Hosts>('/api/hosts')
  const all = (services.data?.groups ?? []).flatMap((g) => g.services)
  const row = 'flex items-center gap-3 rounded-[13px] border border-line-soft bg-card px-4 py-3 font-medium hover:border-line'
  return (
    <nav aria-label="Go to" className="grid gap-2">
      {links.map((link) => {
        if ('page' in link)
          return (
            <Link key={link.label} to={link.page} viewTransition className={row}>
              <span className="flex-1">{link.label}</span>
              {link.hint && <span className="text-caption font-normal text-faint">{link.hint}</span>}
            </Link>
          )
        const service = all.find((s) => s.id === link.service && (s.port || s.url))
        if (!service) return null
        return (
          <a key={link.label} href={serviceHref({ ...service, path: link.path }, window.location.hostname, hosts.data)} target="_blank" rel="noreferrer" className={row}>
            <span className="flex-1">{link.label}</span>
            {link.hint && <span className="text-caption font-normal text-faint">{link.hint}</span>}
            <ExternalLink aria-hidden="true" className="size-4 text-faint" />
          </a>
        )
      })}
    </nav>
  )
}

function Earlier({ message, now }: { message: Shown; now: Date }) {
  return (
    <Card title="Earlier">
      <ul className="ml-1 grid gap-2.5 border-l border-line pl-4">
        {message.earlier.map((m) => (
          <li key={m.id} className="relative text-small">
            <span aria-hidden="true" className={cn('absolute top-1.5 -left-[20.5px] size-[7px] rounded-full', DOT[m.severity])} />
            {m.id === message.id ? (
              <span className="text-accent-fg">{m.title}</span>
            ) : (
              <Link to={`/alerts/${m.id}`} className="hover:underline">
                {m.title}
              </Link>
            )}
            <span className="block text-caption text-faint">
              {formatWhen(m.ts, now)}
              {m.id === message.id && ' · this message'}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  )
}
