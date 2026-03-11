import { ReactNode } from 'react';

type Tone = 'good' | 'warn' | 'bad' | 'info';

export default function Badge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
