'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { Accessibility, X, Minus, Plus, RotateCcw, Contrast, Link2, Heading, MousePointer2, MoveHorizontal, Sparkles } from 'lucide-react';
import { LanguageProvider, useLanguage } from '@/lib/i18n';

const STORAGE_KEY = 'playoff-accessibility-v1';
type Preferences = { scale: number; contrast: boolean; grayscale: boolean; links: boolean; headings: boolean; spacing: boolean; motion: boolean; cursor: boolean };
const defaults: Preferences = {scale:1, contrast:false, grayscale:false, links:false, headings:false, spacing:false, motion:false, cursor:false};

function readPreferences(): Preferences {
  const fallback = {...defaults, motion: window.matchMedia('(prefers-reduced-motion: reduce)').matches};
  try {
    const value: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null');
    if (!value || typeof value !== 'object') return fallback;
    const saved = value as Record<string, unknown>;
    const result = {...fallback};
    if (typeof saved.scale === 'number' && Number.isFinite(saved.scale)) result.scale = Math.min(2, Math.max(1, saved.scale));
    for (const key of ['contrast','grayscale','links','headings','spacing','motion','cursor'] as const) {
      if (typeof saved[key] === 'boolean') result[key] = saved[key];
    }
    return result;
  } catch { return fallback; }
}

function AccessibilityTools() {
  const {t} = useLanguage();
  const [preferences, setPreferences] = useState<Preferences>(defaults);
  const [open, setOpen] = useState(false);
  const [storageUnavailable, setStorageUnavailable] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const launcher = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    let active = true;
    void Promise.resolve().then(() => { if (active) setPreferences(readPreferences()); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty('--a11y-scale', String(preferences.scale));
    for (const key of ['contrast','grayscale','links','headings','spacing','motion','cursor'] as const) {
      root.dataset[`a11y${key[0].toUpperCase()}${key.slice(1)}`] = String(preferences[key]);
    }
  }, [preferences]);
  useEffect(() => {
    if (!open) return;
    const element = dialog.current;
    const opener = launcher.current;
    element?.showModal();
    return () => { element?.close(); opener?.focus(); };
  }, [open]);

  function update(next: Preferences) {
    setPreferences(next);
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); setStorageUnavailable(false); }
    catch { setStorageUnavailable(true); }
  }
  const controls = [
    {key:'contrast', icon:Contrast, label:t('ניגודיות גבוהה','High contrast')},
    {key:'links', icon:Link2, label:t('הדגשת קישורים','Underline links')},
    {key:'headings', icon:Heading, label:t('הדגשת כותרות','Highlight headings')},
    {key:'spacing', icon:MoveHorizontal, label:t('ריווח לקריאה','Reading spacing')},
    {key:'motion', icon:Sparkles, label:t('צמצום תנועה','Reduce motion')},
    {key:'grayscale', icon:Contrast, label:t('גווני אפור','Grayscale')},
    {key:'cursor', icon:MousePointer2, label:t('סמן מוגדל','Larger pointer')},
  ] as const;

  return <>
    <button ref={launcher} className="a11y-launcher" type="button" aria-label={t('פתיחת תפריט נגישות','Open accessibility menu')} title={t('אפשרויות נגישות','Accessibility options')} aria-haspopup="dialog" aria-expanded={open} aria-controls="accessibility-tools" onClick={() => setOpen(true)}><Accessibility size={28} aria-hidden="true"/><span className="a11y-launcher-label">{t('נגישות','Accessibility')}</span></button>
    {open && <dialog id="accessibility-tools" ref={dialog} className="a11y-dialog" aria-labelledby="a11y-title" aria-describedby="a11y-description" onCancel={event => {event.preventDefault(); setOpen(false);}}>
      <div className="a11y-panel-heading"><div><h2 id="a11y-title">{t('נגישות ונוחות','Accessibility & comfort')}</h2></div><button type="button" className="a11y-close" autoFocus aria-label={t('סגירת תפריט נגישות','Close accessibility menu')} onClick={() => setOpen(false)}><X size={22} aria-hidden="true"/></button></div>
      <p id="a11y-description">{t('התאימו את התצוגה לנוחותכם. אפשר לשלב התאמות; הבחירות נשמרות בדפדפן.','Adjust the display for your comfort. Options can be combined and are saved in this browser.')}</p>
      <fieldset className="a11y-scale"><legend>{t('גודל התצוגה','Display size')}</legend><div><button type="button" aria-label={t('הקטנת התצוגה','Decrease display size')} disabled={preferences.scale <= 1} onClick={() => update({...preferences, scale:Math.max(1, preferences.scale - .125)})}><Minus size={20} aria-hidden="true"/></button><output aria-live="polite" aria-atomic="true">{Math.round(preferences.scale * 100)}%</output><button type="button" aria-label={t('הגדלת התצוגה','Increase display size')} disabled={preferences.scale >= 2} onClick={() => update({...preferences, scale:Math.min(2, preferences.scale + .125)})}><Plus size={20} aria-hidden="true"/></button></div></fieldset>
      <div className="a11y-options">{controls.map(({key,icon:Icon,label}) => <button key={key} type="button" className={preferences[key] ? 'a11y-option active' : 'a11y-option'} aria-pressed={preferences[key]} onClick={() => update({...preferences, [key]:!preferences[key]})}><Icon size={20} aria-hidden="true"/><span>{label}</span><span className="a11y-option-state" aria-hidden="true">{preferences[key] ? '✓' : '+'}</span></button>)}</div>
      <button className="a11y-reset" type="button" onClick={() => update({...defaults, motion:window.matchMedia('(prefers-reduced-motion: reduce)').matches})}><RotateCcw size={18} aria-hidden="true"/>{t('איפוס התאמות','Reset adjustments')}</button>
      <Link className="a11y-statement-link" href="/accessibility" onClick={() => setOpen(false)}>{t('הצהרת נגישות ומידע נוסף','Accessibility statement & details')} ↗</Link>
      <p className="a11y-help">{t('מקלדת: Tab למעבר, Enter להפעלה, Esc לסגירה. ניתן גם להגדיל באמצעות הדפדפן.','Keyboard: Tab to move, Enter to activate, Esc to close. Browser zoom is also supported.')}</p>
      {storageUnavailable && <p className="a11y-help" role="status">{t('הדפדפן אינו מאפשר שמירת הגדרות. ההתאמות פעילות בביקור הנוכחי.','Browser storage is unavailable. Adjustments remain active for this visit.')}</p>}
    </dialog>}
  </>;
}

export function SitePreferences({children}: {children:React.ReactNode}) {
  return <LanguageProvider><div className="site-content">{children}</div><AccessibilityTools/></LanguageProvider>;
}
