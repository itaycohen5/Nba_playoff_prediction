'use client';

import { useLanguage } from '@/lib/i18n';

const rules = [
  {he: 'לפחות 8 תווים', en: 'At least 8 characters', test: (value: string) => Array.from(value).length >= 8},
  {he: 'לפחות אות אחת באנגלית', en: 'At least one English letter', test: (value: string) => /[A-Za-z]/.test(value)},
  {he: 'לפחות ספרה אחת', en: 'At least one digit', test: (value: string) => /[0-9]/.test(value)},
  {he: 'לפחות תו מיוחד אחד, למשל ! או #', en: 'At least one special character, such as ! or #', test: (value: string) => /[!-/:-@\x5b-\x60{-~]/.test(value)},
  {he: 'עד 72 בתים (תווים מסוימים תופסים יותר מבית אחד)', en: 'Up to 72 bytes (some characters use more than one byte)', test: (value: string) => new TextEncoder().encode(value).length <= 72},
];

export function meetsPasswordRules(value: string) {
  return rules.every(rule => rule.test(value));
}

function passwordIssues(value: string, t: (he: string, en: string) => string) {
  return rules.filter(rule => !rule.test(value)).map(rule => t(rule.he, rule.en));
}

export const passwordPolicyError = 'הסיסמה אינה עומדת בכל הדרישות המוצגות';

export function PasswordPolicyNotice({value}: {value: string}) {
  const {t} = useLanguage();
  const missing = passwordIssues(value, t);
  if (!missing.length) return null;
  return <div className="notice notice-error" role="alert">
    {t('דרישות סיסמה חסרות: ', 'Missing password requirements: ')}{missing.join(' · ')}
  </div>;
}

export function PasswordRules({id, value}: {id: string; value: string}) {
  const {t} = useLanguage();
  return <ul id={id} className="password-rules">
    {rules.map(rule => {
      const met = rule.test(value);
      return <li key={rule.en} data-met={met}>
        <span className="password-rule-mark" aria-hidden="true">{met ? '✓' : '○'}</span>
        <span className="visually-hidden">{met ? t('הושלם: ','Met: ') : t('חסר: ','Missing: ')}</span>
        {t(rule.he, rule.en)}
      </li>;
    })}
  </ul>;
}
