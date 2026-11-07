import type { Metadata } from 'next';
import './taste-app.css';
import './taste-dashboard.css';
import './taste-page.css';
import './glass.css';
import './broadcast.css';
import './playoff-board.css';
import './accessibility.css';
import { SitePreferences } from '@/components/site-preferences';
export const metadata: Metadata = {title: 'Playoff Lab | מעבדת הפלייאוף שלך', description: 'סימולטור פלייאוף NBA אישי. תחזיות, סדרות ואליפות — עם יתרה מדומה בלבד.'};
export default function RootLayout({children}: {children: React.ReactNode}) {
  return <html lang="he" dir="rtl" data-scroll-behavior="smooth"><body><SitePreferences>{children}</SitePreferences></body></html>;
}
