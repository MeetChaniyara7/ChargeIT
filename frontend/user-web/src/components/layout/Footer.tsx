/** Data credits that OpenStreetMap (ODbL) and Open Charge Map (CC BY 4.0) require. */
export function Footer() {
  return (
    <footer className="border-t border-border px-4 py-6 text-center text-xs text-muted">
      Map data ©{' '}
      <a className="text-info underline-offset-2 hover:underline" href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">
        OpenStreetMap
      </a>{' '}
      contributors · Station data:{' '}
      <a className="text-info underline-offset-2 hover:underline" href="https://openchargemap.org" target="_blank" rel="noreferrer">
        Open Charge Map
      </a>
    </footer>
  );
}
