import type { Metadata } from 'next';
import './globals.css';
import Nav from '../components/Nav';
import { Providers } from '../lib/providers';

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
      <body className="min-h-screen bg-gray-50 dark:bg-gray-900">
        <Providers>
          <Nav />
          <main>{children}</main>
        </Providers>
      </body>
    </html>
  );
}
