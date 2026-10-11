import React, { useState } from 'react';
import type { ReactNode } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { CONNECTOR_TYPES } from '@chargespot/shared';
import {
  ApproximateTag,
  Badge,
  Button,
  Card,
  Chip,
  ConnectorIcon,
  DateTime,
  Divider,
  EmptyState,
  Field,
  IconButton,
  Money,
  Select,
  Sheet,
  SkeletonBlock,
  SkeletonCircle,
  SkeletonLine,
  Spinner,
  StatusBadge,
  TabPanel,
  Tabs,
  TextInput,
  useToast,
} from '../../components/ui';

// Development-only reference page (route /dev/ui, not in production builds).
// Every shared component appears here in each variant and state.

const SWATCHES = [
  ['bg', 'bg-bg'],
  ['surface', 'bg-surface'],
  ['raised', 'bg-raised'],
  ['border', 'bg-border'],
  ['field-border', 'bg-field-border'],
  ['fg', 'bg-fg'],
  ['muted', 'bg-muted'],
  ['primary', 'bg-primary'],
  ['primary-strong', 'bg-primary-strong'],
  ['info', 'bg-info'],
  ['warning', 'bg-warning'],
  ['danger', 'bg-danger'],
  ['danger-strong', 'bg-danger-strong'],
  ['danger-soft', 'bg-danger-soft'],
] as const;

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-xl font-bold">{title}</h2>
      <Card className="space-y-4 p-4">{children}</Card>
    </section>
  );
}

const Row = ({ children }: { children: ReactNode }) => <div className="flex flex-wrap items-center gap-3">{children}</div>;

const StyleGuidePage: React.FC = () => {
  const toast = useToast();
  const [sheetOpen, setSheetOpen] = useState(false);
  const [tab, setTab] = useState('upcoming');
  const [chips, setChips] = useState({ ccs2: true, fast: false });
  const [loading, setLoading] = useState(false);
  const [now] = useState(() => Date.now());

  const demoLoading = () => {
    setLoading(true);
    window.setTimeout(() => setLoading(false), 1500);
  };

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-4 py-8">
      <header>
        <h1 className="text-display font-bold">ChargeSpot style guide</h1>
        <p className="mt-1 text-sm text-muted">
          Development only. Every shared component in every state. Tokens live in <code>frontend/shared/src/styles/tokens.css</code>.
        </p>
      </header>

      <Section title="Colours">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {SWATCHES.map(([name, cls]) => (
            <div key={name}>
              <div className={`h-12 rounded-control border border-border ${cls}`} />
              <p className="mt-1 text-xs text-muted">{name}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Type">
        <p className="text-hero font-bold">Hero 36 · ₹1,23,456.50</p>
        <p className="text-display font-bold">Display 28</p>
        <p className="text-xl font-bold">Title 20</p>
        <p className="text-base">Body 16: Book your EV charger before you arrive.</p>
        <p className="text-sm">Small 14: Plug type, power and price.</p>
        <p className="text-xs text-muted">Caption 12: Fixed-width digits keep numbers steady: 0123456789</p>
        <p className="num text-xl font-bold">{'1111 vs 8888 (tabular)'}</p>
      </Section>

      <Section title="Buttons">
        <Row>
          <Button>Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Danger</Button>
        </Row>
        <Row>
          <Button size="sm">Small</Button>
          <Button size="md">Medium</Button>
          <Button size="lg">Large</Button>
        </Row>
        <Row>
          <Button icon={<Plus className="size-4" aria-hidden="true" />}>With icon</Button>
          <Button disabled>Disabled</Button>
          <Button loading={loading} onClick={demoLoading}>
            {loading ? 'Saving…' : 'Click for loading'}
          </Button>
          <IconButton aria-label="Delete">
            <Trash2 className="size-5" aria-hidden="true" />
          </IconButton>
          <IconButton aria-label="Add" variant="primary">
            <Plus className="size-5" aria-hidden="true" />
          </IconButton>
          <Spinner className="size-6 text-primary" />
        </Row>
        <Button fullWidth>Full width</Button>
      </Section>

      <Section title="Cards and dividers">
        <div className="grid gap-3 sm:grid-cols-2">
          <Card className="p-4">Elevation 1</Card>
          <Card elevation={2} className="p-4">Elevation 2</Card>
        </div>
        <Divider />
      </Section>

      <Section title="Badges and status">
        <Row>
          <Badge>Neutral</Badge>
          <Badge tone="primary">Primary</Badge>
          <Badge tone="info">Admin</Badge>
          <Badge tone="warning">Hold 4:32</Badge>
          <Badge tone="danger">No-show</Badge>
        </Row>
        <Row>
          <StatusBadge status="free" />
          <StatusBadge status="few" />
          <StatusBadge status="busy" />
          <StatusBadge status="offline" />
          <StatusBadge status="free" label="3/4 free" />
        </Row>
        <Row>
          <ApproximateTag />
          <ApproximateTag reason="Price estimated from typical Tata Power tariffs." />
        </Row>
      </Section>

      <Section title="Chips">
        <Row>
          <Chip selected={chips.ccs2} onSelectedChange={(v) => setChips((c) => ({ ...c, ccs2: v }))}>
            CCS2
          </Chip>
          <Chip selected={chips.fast} onSelectedChange={(v) => setChips((c) => ({ ...c, fast: v }))}>
            Fast 50 kW+
          </Chip>
        </Row>
      </Section>

      <Section title="Form fields">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Nickname" hint="For your own reference.">
            {(p) => <TextInput {...p} placeholder="My Nexon" />}
          </Field>
          <Field label="Battery size (kWh)" error="Enter a number between 5 and 250.">
            {(p) => <TextInput {...p} defaultValue="abc" />}
          </Field>
          <Field label="Connector">
            {(p) => (
              <Select {...p} defaultValue="CCS2">
                <option>CCS2</option>
                <option>Type 2</option>
                <option>CHAdeMO</option>
              </Select>
            )}
          </Field>
          <Field label="Disabled">{(p) => <TextInput {...p} disabled value="Can't edit" readOnly />}</Field>
        </div>
      </Section>

      <Section title="Tabs">
        <Tabs
          label="Booking status"
          value={tab}
          onChange={setTab}
          tabs={[
            { id: 'upcoming', label: 'Upcoming' },
            { id: 'past', label: 'Past' },
            { id: 'due', label: 'Payment due', count: 2 },
          ]}
        />
        <TabPanel id="upcoming" value={tab}>Upcoming content (use arrow keys to move between tabs)</TabPanel>
        <TabPanel id="past" value={tab}>Past content</TabPanel>
        <TabPanel id="due" value={tab}>Payment due content</TabPanel>
      </Section>

      <Section title="Loading and empty states">
        <div className="flex items-center gap-3">
          <SkeletonCircle />
          <div className="flex-1 space-y-2">
            <SkeletonLine className="w-1/2" />
            <SkeletonLine className="w-3/4" />
          </div>
        </div>
        <SkeletonBlock />
        <Divider />
        <EmptyState
          title="Your bookings will appear here"
          text="Find a charger and book your first slot."
          action={<Button>Find a charger</Button>}
        />
      </Section>

      <Section title="Toasts and sheet">
        <Row>
          <Button variant="secondary" onClick={() => toast.success('Booking cancelled · ₹149.25 refund')}>
            Success toast
          </Button>
          <Button variant="secondary" onClick={() => toast.info('Booking opens in an upcoming update.')}>
            Info toast
          </Button>
          <Button variant="secondary" onClick={() => toast.error('Payment didn’t go through. Please try again.')}>
            Error toast
          </Button>
          <Button onClick={() => setSheetOpen(true)}>Open sheet</Button>
        </Row>
        <Sheet
          open={sheetOpen}
          onClose={() => setSheetOpen(false)}
          title="Cancel booking?"
          footer={
            <>
              <Button variant="secondary" onClick={() => setSheetOpen(false)}>
                Keep booking
              </Button>
              <Button variant="danger" onClick={() => setSheetOpen(false)}>
                Cancel booking
              </Button>
            </>
          }
        >
          <p className="text-sm">
            You&apos;ll get <Money value={149.25} className="font-bold" /> back. Press Esc, Tab and Shift+Tab to try the focus trap.
          </p>
        </Sheet>
      </Section>

      <Section title="Money and dates">
        <Row>
          <Money value={223.2} />
          <Money value={1234567.5} />
          <Money value={18} perKwh />
          <Money value={undefined} />
        </Row>
        <Row>
          <DateTime value={new Date(now)} />
          <DateTime value={new Date(now + 24 * 3600 * 1000)} />
          <DateTime value={new Date(now + 4 * 24 * 3600 * 1000)} />
          <DateTime value={new Date(now)} format="time" />
          <DateTime value={null} />
        </Row>
      </Section>

      <Section title="Connector icons">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {CONNECTOR_TYPES.map((type) => (
            <ConnectorIcon key={type} type={type} />
          ))}
          <ConnectorIcon type="CCS2" showLabel={false} />
        </div>
      </Section>
    </div>
  );
};

export default StyleGuidePage;
