import { DemoProvider } from '@/contexts/demo-context';

export default function DemoLayout({ children }: { children: React.ReactNode }) {
  return <DemoProvider>{children}</DemoProvider>;
}
