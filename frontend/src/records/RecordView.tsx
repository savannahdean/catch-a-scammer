// Draws whatever the server sends: a generic "card" (backend/server/cards.py) or
// one of the seven original record shapes (domain, ip, malware, campaign, actor,
// person, article). Renderers never change state themselves; a click on a row
// goes through `nav`, so the window hosting the record decides what happens.
import { useState } from 'react'
import type { ReactNode } from 'react'
import type {
  ActorRecord,
  AnyRecord,
  ArticleRecord,
  Block,
  CampaignRecord,
  Card,
  DomainRecord,
  Envelope,
  FetchAction,
  IpRecord,
  MalwareRecord,
  PersonRecord,
  Pin,
} from '../api/types'
import { isCard } from '../api/types'
import { GlossaryText } from '../glossary/GlossaryText'
import { useSession } from '../state/session'
import { statusColor, toneColor } from '../theme'
import { ActionRow, Badge, KeyValue, Meter, SectionLabel } from '../ui/widgets'

/** How a record's links are followed. */
export interface RecordNav {
  /** open another tool and search it */
  open: (app: string, query: string) => void
  /** load one record, in this window or in the tool that owns it */
  fetch: (f: FetchAction) => void
}

/** The default: every link opens the target tool. */
export function useOpenNav(): RecordNav {
  const s = useSession()
  return {
    open: (app, query) => s.requestOpen(app, query),
    fetch: (f) => s.requestOpen(f.app || 'intelsearch', undefined, f),
  }
}

function Header({ kind, title, status }: { kind: string; title: string; status?: string }) {
  return (
    <div className="rec-header">
      <div className="rec-kind">
        <GlossaryText text={kind} />
      </div>
      <div className="rec-title" title={title}>
        {title}
      </div>
      {status ? <Badge color={statusColor(status)}>{status.toUpperCase()}</Badge> : null}
    </div>
  )
}

function PinButtons({ pin, graph = false }: { pin: Pin | null; graph?: boolean }) {
  const s = useSession()
  if (!pin) return null
  const pinned = s.isPinned(pin.entity_id)
  const closed = s.brief?.status !== 'open'
  return (
    <div className="rec-actions">
      <button type="button" className="btn btn-primary" disabled={pinned || closed} onClick={() => void s.pin(pin)} data-tour="pin">
        {pinned ? 'IN EVIDENCE' : 'ADD TO EVIDENCE'}
      </button>
      {graph && (
        <button type="button" className="btn" onClick={() => s.requestOpen('evidencemap')}>
          OPEN GRAPH
        </button>
      )}
    </div>
  )
}

function Pivots({ items, query, nav }: { items: [string, string][]; query: string; nav: RecordNav }) {
  return (
    <>
      <SectionLabel>INVESTIGATE FURTHER</SectionLabel>
      <div className="pivot-strip">
        {items.map(([label, app]) => (
          <button key={app} type="button" className="btn btn-small" onClick={() => nav.open(app, query)} data-tour={`pivot-${app}`}>
            {label}
          </button>
        ))}
      </div>
    </>
  )
}

function Section({ label, note, children }: { label: string; note?: string; children: ReactNode }) {
  return (
    <div className="rec-section">
      <SectionLabel>{label}</SectionLabel>
      {note ? (
        <div className="rec-note">
          <GlossaryText text={note} />
        </div>
      ) : null}
      {children}
    </div>
  )
}

// ------------------------------------------------------------------ cards
function BlockView({ b, nav }: { b: Block; nav: RecordNav }) {
  if (b.type === 'text')
    return (
      <Section label={b.label}>
        <div className="rec-text">
          <GlossaryText text={b.text} />
        </div>
      </Section>
    )
  if (b.type === 'mono')
    return (
      <Section label={b.label}>
        <pre className="terminal">{b.text}</pre>
      </Section>
    )
  if (b.type === 'meter')
    return (
      <Section label={b.label}>
        <Meter value={b.value} low={b.low} high={b.high} />
        {b.note ? (
          <div className="rec-note">
            <GlossaryText text={b.note} />
          </div>
        ) : null}
      </Section>
    )
  return (
    <Section label={b.label} note={b.note}>
      {b.rows.map((r, i) => (
        <ActionRow
          key={i}
          text={r.text}
          right={r.right}
          color={toneColor(r.tone, 'var(--accent)')}
          onClick={r.open ? () => nav.open(r.open!.app, r.open!.query) : r.fetch ? () => nav.fetch(r.fetch!) : undefined}
        />
      ))}
    </Section>
  )
}

export function CardView({ card, nav, compact = false }: { card: Card; nav: RecordNav; compact?: boolean }) {
  const [open, setOpen] = useState(!compact)
  return (
    <article className={`record${compact ? ' record-compact' : ''}`}>
      <Header kind={card.kind_label} title={card.title} status={card.status} />
      {card.subtitle ? <div className="rec-subtitle">{card.subtitle}</div> : null}
      {compact && (
        <button type="button" className="link-btn" onClick={() => setOpen(!open)}>
          {open ? 'Hide details' : 'Show details'}
        </button>
      )}
      {open && (
        <>
          {card.fields.length > 0 && (
            <div className="rec-fields">
              {card.fields.map(([k, v, tone], i) => (
                <KeyValue key={i} k={k} v={<span className="mono">{String(v)}</span>} color={toneColor(tone)} />
              ))}
            </div>
          )}
          {card.blocks.map((b, i) => (
            <BlockView key={i} b={b} nav={nav} />
          ))}
        </>
      )}
      <PinButtons pin={card.pin} />
    </article>
  )
}

// ------------------------------------------------------ original record shapes
function DomainView({ d, nav }: { d: DomainRecord; nav: RecordNav }) {
  return (
    <article className="record">
      <Header kind="DOMAIN" title={d.domain_name} status={d.status} />
      <div className="rec-fields">
        <KeyValue k="First seen" v={d.first_seen || 'unknown'} />
        <KeyValue k="Last seen" v={d.last_seen || 'unknown'} />
        <KeyValue k="Registrar" v={d.registrar || 'unknown'} />
        {d.registered && <KeyValue k="Registered" v={d.registered} />}
        {d.lookalike_of && <KeyValue k="Resembles" v={d.lookalike_of} color="var(--warn)" />}
      </div>
      {d.associated_ips.length > 0 && (
        <Section label="ASSOCIATED ADDRESSES">
          {d.associated_ips.map((ip) => (
            <ActionRow
              key={ip.ip_id}
              text={ip.ip_address}
              right={`${ip.first_seen ? `${ip.first_seen} to ${ip.last_seen}   ` : ''}VIEW IP >`}
              color="var(--accent)"
              onClick={() => nav.fetch({ app: 'intelsearch', path: `/api/intel/ip/${ip.ip_id}`, params: {} })}
            />
          ))}
        </Section>
      )}
      {d.delivers_malware.length > 0 && (
        <Section label="STAGED PAYLOADS">
          {d.delivers_malware.map((m) => (
            <ActionRow key={m.malware_id} text={m.family_name} right="VIEW MALWARE >" color="var(--danger)"
              onClick={() => nav.open('malwaredb', m.family_name)} />
          ))}
        </Section>
      )}
      <Pivots
        nav={nav}
        query={d.domain_name}
        items={[
          ['DNS HISTORY', 'dns'],
          ['WHOIS HISTORY', 'whois'],
          ['CERTIFICATES', 'certs'],
          ['URL SCANS', 'urlscan'],
          ['WEB SEARCH', 'websearch'],
        ]}
      />
      <PinButtons pin={{ entity_kind: 'domain', entity_id: d.domain_id, label: d.domain_name }} graph />
    </article>
  )
}

function IpView({ d, nav }: { d: IpRecord; nav: RecordNav }) {
  const repColor =
    d.provider_reputation === 'bulletproof' ? 'var(--danger)' : d.provider_reputation === 'mixed' ? 'var(--warn)'
      : d.provider_reputation === 'clean' ? 'var(--ok)' : 'var(--text-dim)'
  return (
    <article className="record">
      <Header kind="IP ADDRESS" title={d.ip_address} status={d.status} />
      <Section label="APPROXIMATE LOCATION">
        <div className="rec-fields">
          <KeyValue k="Country" v={d.country || 'unknown'} />
          <KeyValue k="Region" v={d.region || 'unknown'} />
          <KeyValue k="City" v={d.city || 'unknown'} />
        </div>
      </Section>
      <Section label="NETWORK INFORMATION">
        <div className="rec-fields">
          <KeyValue k="ASN" v={d.asn || 'unknown'} />
          <KeyValue k="Organization" v={d.provider_name || 'unknown'} />
          <KeyValue k="Reputation" v={d.provider_reputation || 'unknown'} color={repColor} />
          <KeyValue k="Abuse contact" v={d.abuse_email || 'none published'} />
          {d.reverse_dns && <KeyValue k="Reverse DNS" v={d.reverse_dns} />}
          {d.tags && <KeyValue k="Tags" v={d.tags} color="var(--warn)" />}
        </div>
      </Section>
      {d.related_domains.length > 0 && (
        <Section label="DOMAINS ON THIS ADDRESS" note="Co-hosting is common. Shared address is not a shared operator.">
          {d.related_domains.map((dm) => (
            <ActionRow
              key={dm.domain_id}
              text={dm.domain_name}
              right={dm.first_seen || '?'}
              color={statusColor(dm.status)}
              onClick={() => nav.fetch({ app: 'intelsearch', path: `/api/intel/domain/${dm.domain_id}`, params: {} })}
            />
          ))}
        </Section>
      )}
      {d.related_malware.length > 0 && (
        <Section label="MALWARE BEACONING HERE">
          {d.related_malware.map((m) => (
            <ActionRow key={m.malware_id} text={m.family_name} right="VIEW MALWARE >" color="var(--danger)"
              onClick={() => nav.open('malwaredb', m.family_name)} />
          ))}
        </Section>
      )}
      <Pivots nav={nav} query={d.ip_address} items={[['DNS HISTORY', 'dns'], ['URL SCANS', 'urlscan']]} />
      <PinButtons pin={{ entity_kind: 'ip', entity_id: d.ip_id, label: d.ip_address }} graph />
    </article>
  )
}

function MalwareView({ d, nav }: { d: MalwareRecord; nav: RecordNav }) {
  return (
    <article className="record">
      <Header kind="MALWARE FAMILY" title={d.family_name} />
      <div className="rec-fields">
        <KeyValue k="Type" v={d.malware_type} />
        <KeyValue k="First observed" v={d.first_observed || 'unknown'} />
        <KeyValue k="Source" v={d.source || 'community'} />
      </div>
      {d.campaigns.length > 0 && (
        <Section label="ASSOCIATED CAMPAIGNS">
          {d.campaigns.map((c) => (
            <ActionRow key={c.campaign_id} text={c.name} right="SEARCH THE WEB >" color="var(--accent)"
              onClick={() => nav.open('websearch', c.name)} />
          ))}
        </Section>
      )}
      {d.infrastructure.length > 0 && (
        <Section label="ASSOCIATED INFRASTRUCTURE">
          {d.infrastructure.map((ip) => (
            <ActionRow key={ip.ip_address} text={ip.ip_address} right="VIEW IN INTELSEARCH >" color="var(--accent)"
              onClick={() => nav.open('intelsearch', ip.ip_address)} />
          ))}
        </Section>
      )}
      <PinButtons pin={{ entity_kind: 'malware_family', entity_id: d.malware_id, label: d.family_name }} graph />
    </article>
  )
}

function CampaignView({ d, nav }: { d: CampaignRecord; nav: RecordNav }) {
  return (
    <article className="record">
      <Header kind="CAMPAIGN" title={d.name} />
      <div className="rec-fields">
        <KeyValue k="Active since" v={d.active_since || 'unknown'} />
      </div>
      <div className="rec-text">
        <GlossaryText text={d.description} />
      </div>
      {d.actors.length > 0 && (
        <Section label="ATTRIBUTED TO">
          {d.actors.map((a) => (
            <ActionRow key={a.alias} text={a.alias} right="OPEN PROFILE >" color="var(--noise)"
              onClick={() => nav.open('directory', a.alias)} />
          ))}
        </Section>
      )}
      {d.attribution_sources.length > 0 && (
        <Section label="WHO SAYS SO">
          {d.attribution_sources.map((src) => (
            <div key={src} className="rec-note">
              {src}
            </div>
          ))}
        </Section>
      )}
      <PinButtons pin={{ entity_kind: 'campaign', entity_id: d.campaign_id, label: d.name }} graph />
    </article>
  )
}

function ActorView({ d, nav }: { d: ActorRecord; nav: RecordNav }) {
  return (
    <article className="record">
      <Header kind="THREAT ACTOR ALIAS" title={d.alias} />
      <div className="rec-fields">
        <KeyValue k="Origin region" v={d.origin_region || 'unattributed'} />
        <KeyValue k="Motivation" v={d.motivation || 'unclear'} />
        <KeyValue k="Known campaigns" v={String(d.campaigns.length)} />
        <KeyValue k="Known infrastructure" v={String(d.known_domains.length)} />
      </div>
      {d.notes && <div className="rec-text rec-dim">{d.notes}</div>}
      {d.campaigns.length > 0 && (
        <Section label="CAMPAIGNS">
          {d.campaigns.map((c) => (
            <ActionRow key={c.name} text={c.name} right="SEARCH THE WEB >" color="var(--accent)"
              onClick={() => nav.open('websearch', c.name)} />
          ))}
        </Section>
      )}
      {d.known_domains.length > 0 && (
        <Section label="KNOWN INFRASTRUCTURE">
          {d.known_domains.map((dm) => (
            <ActionRow key={dm.domain_name} text={dm.domain_name} right="VIEW >" color={statusColor(dm.status)}
              onClick={() => nav.open('intelsearch', dm.domain_name)} />
          ))}
        </Section>
      )}
      <PinButtons pin={{ entity_kind: 'threat_actor', entity_id: d.actor_id, label: d.alias }} graph />
    </article>
  )
}

function PersonView({ d }: { d: PersonRecord }) {
  const socials = Object.entries(d.socials ?? {})
  return (
    <article className="record">
      <Header kind="CIVILIAN RECORD" title={d.full_name} />
      <div className="rec-fields">
        <KeyValue k="City" v={d.city || '-'} />
        <KeyValue k="Country" v={d.country || '-'} />
        <KeyValue k="Employer" v={d.employer || '-'} />
        <KeyValue k="Job title" v={d.job_title || '-'} />
      </div>
      {socials.length > 0 && (
        <Section label="PUBLIC ACCOUNTS">
          <div className="rec-fields">
            {socials.map(([platform, handle]) => (
              <KeyValue key={platform} k={platform} v={handle} />
            ))}
          </div>
        </Section>
      )}
      <PinButtons pin={{ entity_kind: 'person', entity_id: d.person_id, label: d.full_name }} />
    </article>
  )
}

function ArticleView({ d }: { d: ArticleRecord }) {
  return (
    <article className={`article${d.reveals_alias ? ' article-reliable' : ''}`}>
      <h3 className="article-title">{d.title}</h3>
      <div className="article-meta">
        {d.outlet} · {d.published || 'undated'}
      </div>
      <div className="article-body">{d.body}</div>
    </article>
  )
}

export function RecordView({ rec, nav, compact = false }: { rec: AnyRecord; nav: RecordNav; compact?: boolean }) {
  if (isCard(rec)) return <CardView card={rec} nav={nav} compact={compact} />
  switch (rec.kind) {
    case 'domain':
      return <DomainView d={rec} nav={nav} />
    case 'ip':
      return <IpView d={rec} nav={nav} />
    case 'malware':
      return <MalwareView d={rec} nav={nav} />
    case 'campaign':
      return <CampaignView d={rec} nav={nav} />
    case 'actor':
      return <ActorView d={rec} nav={nav} />
    case 'person':
      return <PersonView d={rec} />
    case 'article':
      return <ArticleView d={rec} />
  }
}

/** A search result: every record list in the envelope, in a fixed order. */
export function EnvelopeView({ env, nav }: { env: Envelope; nav: RecordNav }) {
  const recs: AnyRecord[] = [
    ...(env.domains ?? []),
    ...(env.ips ?? []),
    ...(env.malware ?? []),
    ...(env.campaigns ?? []),
    ...(env.actors ?? []),
    ...(env.persons ?? []),
    ...env.cards,
    ...(env.articles ?? []),
  ]
  return (
    <div className="record-list">
      {recs.map((r, i) => (
        <RecordView key={i} rec={r} nav={nav} />
      ))}
    </div>
  )
}
