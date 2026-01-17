import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Obsidian-Memory',
  description: 'Unified memory management system for Claude Code',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
