'use client';
import { Shell } from '@/components/ui';
import { useLanguage } from '@/lib/i18n';

const email = process.env.NEXT_PUBLIC_ACCESSIBILITY_EMAIL ?? '';
const operator = process.env.NEXT_PUBLIC_SITE_OPERATOR ?? '';

export default function AccessibilityStatement() {
  const {t} = useLanguage();
  return <Shell><article className="accessibility-copy">
    <h1>{t('הצהרת נגישות','Accessibility statement')}</h1>
    <p className="statement-date">{t('עודכן: 4 בנובמבר 2026','Updated: November 4, 2026')}</p>
    <p>{t('אנחנו פועלים לאפשר שימוש נוח ושוויוני בסימולטור הפלייאוף. עמוד זה מתאר את ההתאמות שבוצעו ואת מגבלות הבדיקה הנוכחית.','We aim to make the playoff simulator usable and welcoming for everyone. This page describes the adjustments implemented and the current limits of our evaluation.')}</p>
    <h2>{t('ההתאמות באתר','Accessibility features')}</h2>
    <ul>
      <li>{t('ניווט באמצעות מקלדת, חיווי מיקוד וקישור דילוג לתוכן הראשי.','Keyboard navigation, visible focus indicators and a skip-to-content link.')}</li>
      <li>{t('תוויות לשדות, כותרות מובנות והודעות על הצלחה ושגיאות המותאמות לטכנולוגיות מסייעות.','Labeled inputs, structured headings, and success and error messages exposed to assistive technology.')}</li>
      <li>{t('התאמה למחשב ולמובייל, תמיכה בהגדלת דפדפן ובצמצום תנועה.','Responsive layouts, browser zoom support and reduced-motion preferences.')}</li>
      <li>{t('בחירת עברית או אנגלית, כולל התאמת שפת העמוד וכיוון הקריאה.','Hebrew and English with matching page language and reading direction.')}</li>
      <li>{t('כפתור נגישות קבוע בתחתית משמאל: הגדלת תצוגה, ניגודיות, ריווח קריאה, הדגשות, גווני אפור וצמצום תנועה.','A fixed bottom-left accessibility menu with display scaling, contrast, reading spacing, highlights, grayscale and reduced motion.')}</li>
    </ul>
    <h2>{t('הפעלה במקלדת','Keyboard operation')}</h2>
    <p>{t('Tab ו־Shift+Tab מעבירים בין רכיבים. Enter או מקש הרווח מפעילים כפתורים. Esc סוגר את תפריט הנגישות וחלונות אישור. אפשר לשנות גודל תצוגה גם באמצעות כלי הזום של הדפדפן.','Use Tab and Shift+Tab to move between controls. Enter or Space activates buttons. Escape closes the accessibility menu and confirmation dialogs. Browser zoom can also change the display size.')}</p>
    <h2>{t('שמירת העדפות ופרטיות','Preferences and privacy')}</h2>
    <p>{t('השפה והתאמות הנגישות נשמרות בדפדפן המקומי. תפריט הנגישות אינו שולח את הבחירות לשירות חיצוני. ניתן לאפס התאמות דרך התפריט.','Language and accessibility adjustments are saved in your local browser. The menu does not send your choices to an external service. Adjustments can be reset in the menu.')}</p>
    <h2>{t('מצב הבדיקה ומגבלות','Evaluation status and limitations')}</h2>
    <p>{t('ההתאמות מכוונות לעקרונות ת״י 5568 ורמת AA. טרם הושלמה בדיקת נגישות מקצועית מלאה עם מגוון קוראי מסך, ולכן אין בעמוד זה הצהרה על עמידה מלאה בתקן. תפריט ההתאמות הוא כלי עזר נוסף להנגשת רכיבי האתר.','These adjustments are guided by Israeli Standard 5568 and AA-level accessibility principles. A complete professional evaluation across screen readers has not been completed, so this page does not claim full conformance. The comfort menu supplements the accessibility of the underlying site.')}</p>
    <p>{t('האתר הוא סימולציה על בסיס נתונים היסטוריים, עם יתרה מדומה. שמות קבוצות NBA נשמרים באנגלית בשתי השפות.','The site is a historical-data simulation with a virtual balance. NBA team names remain in English in both languages.')}</p>
    <h2>{t('פנייה בנושא נגישות','Accessibility contact')}</h2>
    {operator && <p>{t('מפעיל האתר: ','Site operator: ')}{operator}</p>}
    {email ? <p>{t('נתקלתם בקושי? כתבו לנו וציינו את כתובת העמוד, הפעולה שניסיתם לבצע והדפדפן או כלי העזר שבהם השתמשתם: ','If you encounter a barrier, please include the page URL, the action you attempted, and your browser or assistive technology: ')}<a href={`mailto:${email}`}>{email}</a></p> : <p>{t('פרטי יצירת הקשר של מפעיל האתר יפורסמו כאן לפני פתיחת השירות לציבור.','The operator’s accessibility contact details will be published here before the service opens to the public.')}</p>}
    <h2>{t('מידע נוסף','Further information')}</h2>
    <ul><li><a href="https://www.gov.il/he/pages/website_accessibility">{t('נציבות שוויון זכויות לאנשים עם מוגבלות — נגישות אתרי אינטרנט','Commission for Equal Rights of Persons with Disabilities — website accessibility')}</a></li><li><a href="https://www.w3.org/WAI/standards-guidelines/wcag/">{t('הנחיות WCAG של ארגון W3C','W3C Web Content Accessibility Guidelines')}</a></li></ul>
  </article></Shell>;
}
