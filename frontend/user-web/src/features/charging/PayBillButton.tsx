import React from 'react';
import { AlertCircle, RefreshCw, Wallet } from 'lucide-react';
import { Button, Money, useToast } from '../../components/ui';
import type { ButtonSize } from '../../components/ui/button-styles';
import type { LiveSession } from './types';
import { useBillPayment } from './useBillPayment';

interface PayBillButtonProps {
  sessionId: string;
  /** The bill, for the label only. The amount that is charged always comes from the server. */
  amount: number;
  size?: ButtonSize;
  fullWidth?: boolean;
  /** Called after the server verified the payment. */
  onPaid: (session: LiveSession) => void;
}

/** "Pay ₹223.20": opens Razorpay Checkout for a finished session's bill and says what happened. */
export const PayBillButton: React.FC<PayBillButtonProps> = ({ sessionId, amount, size = 'lg', fullWidth = true, onPaid }) => {
  const toast = useToast();
  const { pay, checkAgain, paying, problem } = useBillPayment(sessionId, (session) => {
    toast.success('Bill paid. Thank you!');
    onPaid(session);
  });
  return (
    <div className="space-y-2">
      <Button size={size} fullWidth={fullWidth} loading={paying} icon={<Wallet className="size-4" aria-hidden="true" />} onClick={pay}>
        Pay <Money value={amount} />
      </Button>
      {problem && (
        <div role="alert" className="flex items-start gap-2 rounded-card border border-danger/40 bg-danger/10 p-3 text-sm">
          <AlertCircle className="mt-0.5 size-4 shrink-0 text-danger-soft" aria-hidden="true" />
          <div className="space-y-2">
            <p>{problem.message}</p>
            {problem.kind === 'verify' ? (
              <Button size="sm" variant="secondary" icon={<RefreshCw className="size-4" aria-hidden="true" />} onClick={checkAgain} loading={paying}>
                Check again
              </Button>
            ) : (
              <p className="text-xs text-muted">You can try again with the button above.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
