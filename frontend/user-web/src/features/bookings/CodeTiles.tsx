import React from 'react';

/** The six digits of a one-time code, as large tiles. Screen readers get the digits spaced out, once. */
export const CodeTiles: React.FC<{ code: string }> = ({ code }) => (
  <div role="group" aria-label={`Your code: ${code.split('').join(' ')}`} className="flex justify-center gap-2">
    {code.split('').map((digit, index) => (
      <span
        key={index}
        aria-hidden="true"
        className="num flex h-14 w-11 items-center justify-center rounded-control border border-field-border bg-raised text-display font-bold sm:h-16 sm:w-12"
      >
        {digit}
      </span>
    ))}
  </div>
);
