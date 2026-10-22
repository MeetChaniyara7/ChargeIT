import { cx } from './cx';

export function Spinner({ className }: { className?: string }) {
  return <span className={cx('inline-block size-6 animate-spin rounded-full border-4 border-current border-t-transparent', className)} role="presentation" />;
}
