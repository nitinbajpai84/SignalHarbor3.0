import { useState } from "react";

import {
  ActionCard, ActivityIcon, BuildIcon, ChatIcon, CheckIcon, Chip, ClockIcon, CommentThread, ConsumeIcon, DatabaseIcon, DataTable,
  DocumentIcon, EmptyState, Footnote, HomeIcon, IntentIcon, LineChart, MapColumns, MapIcon, PageFrame, PenIcon, PeopleIcon,
  PhoneTabBar, Pill, PulseIcon, RoomTile, SideCard, Signature, Sparkline, StatCard, StatGrid, Strip, TableIcon, TopBar, Trail,
  VersionList, WarningIcon, type Comment, type PillTone,
} from ".";

// Every design part with sample props, at /design-gallery. Illustrative, synthetic data copied from the pulse canvas.

const LINKS = [
  { label: "Pulse", href: "/design-gallery", active: true },
  { label: "Intent", href: "/centre/intent" },
  { label: "Consume", href: "/centre/consume" },
  { label: "How my organisation connects", href: "/centre/map" },
];

const MAP = [
  { title: "Walls", nodes: [{ id: "w1", label: "Treasury", kind: "wall" }, { id: "w2", label: "Performance", kind: "wall" }] },
  { title: "Problems", nodes: [{ id: "p1", label: "Late capital-call notices", kind: "problem" }, { id: "p2", label: "Fee leakage", kind: "problem" }, { id: "p3", label: "Pay bands", kind: "problem", restricted: true }] },
  { title: "Measures", nodes: [{ id: "m1", label: "Trust NAV", kind: "measure" }, { id: "m2", label: "Fees Charged", kind: "measure" }, { id: "m3", label: "Net new money", kind: "measure" }] },
  { title: "Systems", nodes: [{ id: "s1", label: "Custodian", kind: "system" }, { id: "s2", label: "Fund admin", kind: "system" }] },
  { title: "Owners", nodes: [{ id: "o1", label: "Olga", kind: "owner" }, { id: "o2", label: "Dan", kind: "owner" }] },
];
const EDGES = [
  { from: "w1", to: "p1" }, { from: "w1", to: "p2" }, { from: "w2", to: "p3" }, { from: "p1", to: "m1" }, { from: "p2", to: "m2" },
  { from: "p2", to: "m3" }, { from: "m1", to: "s1" }, { from: "m2", to: "s2" }, { from: "m1", to: "o1" }, { from: "m2", to: "o2" },
];

const COMMENTS: Comment[] = [
  { id: "c1", kind: "ambiguity", text: "Dormant vehicles: the exposure workbook still counts two of them. Which is right?", by: "Harvey Rowley", at: "2 days ago", state: "open", decided_by: null, answer: null },
  { id: "c2", kind: "suggestion", text: "The process map misses the FX check on day 3.", by: "Aaron Lyle", at: "last week", state: "accepted", decided_by: "Dan", answer: "became version 3" },
];

const TONES: PillTone[] = ["ok", "late", "failed", "draft", "signed", "open", "restricted"];

const ICONS = { PeopleIcon, CheckIcon, DatabaseIcon, ActivityIcon, ClockIcon, DocumentIcon, WarningIcon, PenIcon, ChatIcon, TableIcon, MapIcon, PulseIcon, HomeIcon, IntentIcon, BuildIcon, ConsumeIcon };

export default function Gallery() {
  const [selected, setSelected] = useState("m1");
  const [signed, setSigned] = useState(false);
  return (
    <div className="ds-screen">
      <TopBar product="Signal Harbor" company="Lakeside Family Office" links={LINKS} person="Priya Nair" role="Participant" initials="PN" />
      <PageFrame
        title="Good morning, Priya."
        subline="Tuesday 7 October · 4 things need you · about 12 minutes · Illustrative"
        actions={<><Chip tone="active" href="/design-gallery">Whole map</Chip><Chip onClick={() => undefined}>Holes: 6</Chip><Chip>New this week: 5</Chip></>}
        aside={
          <>
            <SideCard title="How my organisation connects" action={{ label: "Open", href: "/centre/map" }}>
              <p>Problems, measures, systems and owners, and how they link. Open to everyone in the company.</p>
            </SideCard>
            <SideCard title="Versions"><VersionList versions={[{ v: 1, what: "Drafted by Lens", by: "Lens", at: "15 Sep" }, { v: 3, what: "FX check added", by: "Dan Data", at: "30 Sep" }, { v: 2, what: "Dormant vehicles excluded", by: "Olga Trustee", at: "22 Sep" }]} /></SideCard>
            <EmptyState title="Nothing needs you today" lines={["New asks appear here when someone names you."]} links={[{ label: "Open the map", href: "/centre/map" }]} />
            <Footnote>Everything here is read from the company's own records.</Footnote>
          </>
        }
      >
        <div className="ds-gallery">
          <Strip label="Invited">
            <ActionCard icon={<PeopleIcon />} title="Treasury: capital calls wall, from Aaron Lyle" detail="8 people · North drafted 3 cards from your interview" due="Closes Friday" action="Open the wall" href="/design-gallery" />
          </Strip>
          <Strip label="Decide" tone="amber">
            <ActionCard tone="amber" icon={<CheckIcon />} title="Confirm the definition of Fees Charged" detail="Lens drafted it from the fee schedule. Confirm, or send back with a note." action="Confirm" href="/design-gallery" />
          </Strip>
          <Strip label="Today's ops report" tone="amber">
            <div className="ds-card ds-side">
              <StatGrid cols={4}>
                <StatCard bare label="Loads on time" value="6 of 7" />
                <StatCard bare label="Late" value="1" valueTone="warn" />
                <StatCard bare label="Checks failed" value="2" valueTone="warn" />
                <StatCard bare label="Measures released" value="14" />
              </StatGrid>
              <ActionCard inset tone="amber" icon={<WarningIcon />} title="Critical: Trust NAV outside its range for two days" detail="The Prover shows a 1.8% gap to the reported figure." action="Open in Ops" href="/design-gallery" />
            </div>
          </Strip>
          <Strip label="Watch">
            <StatGrid>
              <StatCard href="/design-gallery" label="Fees Charged · Sep" value="2.14m" note="Outside its usual range" tone="warn" />
              <StatCard href="/design-gallery" label="Capital calls open" value="7" note="Same as last week" />
              <StatCard href="/design-gallery" label="Market brief" value="Private credit spreads tightened again" note="Outside material" tone="muted" text />
            </StatGrid>
          </Strip>
          <Strip label="Your initiatives">
            <DataTable
              columns={[{ key: "name", label: "Initiative" }, { key: "where", label: "Where it is" }, { key: "hurdle", label: "Hurdle" }]}
              rows={[{ name: <strong>Treasury</strong>, where: "Define: charter ready to sign", hurdle: "None" }, { name: <strong>Performance</strong>, where: "Moment of truth: 12 of 14 match", hurdle: <span className="ds-warn">Custodian file late</span> }]}
            />
          </Strip>
          <Strip label="Map">
            <div className="ds-card ds-side">
              <MapColumns columns={MAP} edges={EDGES} selectedId={selected} onSelect={setSelected} holeIds={["m3"]} />
              <p>Selected: {selected}</p>
            </div>
          </Strip>
          <Strip label="Trail">
            <Trail steps={[{ step: "asked", label: "Treasury wall", ref: "Late capital-call notices" }, { step: "defined", label: "Treasury baseline", by: "Mei Tan", at: "22 Sep" }, { step: "supplied", label: "Custodian system" }]} />
          </Strip>
          <Strip label="Comments">
            <div className="ds-card ds-side"><CommentThread comments={COMMENTS} canDecide onDecide={() => undefined} /></div>
          </Strip>
          <Strip label="Signature">
            <Signature state={signed ? "signed" : "waiting"} by="Mei Tan" at={signed ? "today" : undefined} onSign={() => setSigned(true)} />
          </Strip>
          <Strip label="Rooms">
            <StatGrid cols={3}>
              <RoomTile number={1} name="Bring what you have" state="open" line="Nira read 12 files." counts={["4 guesses", "2 to confirm"]} action={{ label: "Continue", href: "/design-gallery" }} />
              <RoomTile number={2} name="The wall" state="next" line="Opens when the profile is confirmed." counts={["8 people"]} />
              <RoomTile number={3} name="Define" state="dim" line="After the wall closes." counts={[]} />
            </StatGrid>
          </Strip>
          <Strip label="Pills and charts">
            <div className="ds-frame__actions">{TONES.map((t) => <Pill key={t} tone={t}>{t}</Pill>)}</div>
            <Sparkline points={[3, 5, 4, 7, 6, 9, 8]} />
            <LineChart points={[{ period: "Jun", value: 1.8 }, { period: "Jul", value: 1.9 }, { period: "Aug", value: 2.0 }, { period: "Sep", value: 2.14 }]} label="Fees Charged by month" />
          </Strip>
          <Strip label="Icons">
            <div className="ds-frame__actions ds-soft">{Object.entries(ICONS).map(([name, I]) => <span key={name} title={name}><I /></span>)}</div>
          </Strip>
          <Strip label="Phone tab bar (under 480px)">
            <div className="ds-gallery__phone">
              <PhoneTabBar items={[
                { label: "Pulse", href: "/design-gallery", icon: <PulseIcon />, active: true },
                { label: "Intent", href: "/centre/intent", icon: <IntentIcon /> },
                { label: "Consume", href: "/centre/consume", icon: <ConsumeIcon /> },
                { label: "Map", href: "/centre/map", icon: <MapIcon /> },
              ]} />
            </div>
          </Strip>
        </div>
      </PageFrame>
    </div>
  );
}
