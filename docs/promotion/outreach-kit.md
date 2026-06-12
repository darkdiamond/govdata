# govil.ai — outreach kit (owner actions)

Everything below needs your identity/accounts, so it's drafted ready-to-send.
Order is by expected value. Keep the one positioning rule: govil.ai is a free
AI-explainer layer over the official data.gov.il — never imply official status,
always disclose that page text is AI-written and validated against the data.

---

## 0. Search consoles (15 min, do first — also our measurement tool)

1. **Google Search Console** — https://search.google.com/search-console → add
   property `govil.ai` (domain property; verify via DNS TXT at your registrar)
   → Sitemaps → submit `https://govil.ai/sitemap.xml`.
   The **Links report** there is how we'll track backlink growth.
2. **Bing Webmaster Tools** — https://www.bing.com/webmasters → "Import from
   Google Search Console" (one click after #1) — IndexNow pings are already
   automated from CI, this just gives you the dashboard.

---

## 1. data.gov.il portal team (highest-value backlink: gov.il domain)

Where: the contact form on data.gov.il (or the מערך הדיגיטל הלאומי contact channel).

> שלום רב,
>
> בניתי אתר חינמי בשם govil.ai שמלווה את פורטל data.gov.il: לכל מאגר בפורטל
> נוצר דף הסבר בעברית פשוטה עם גרפים ומפות אינטראקטיביים, טבלת חיפוש על
> ה-datastore, וקישורים חזרה לקבצי המקור הרשמיים. הדפים נכתבים על ידי סוכן AI
> שרץ מדי יום על מאגרים חדשים ומעודכנים, ומאומתים מול הנתונים לפני פרסום —
> נכון להיום מכוסים כ-483 מאגרים. האתר מציין במפורש שהוא אינו אתר רשמי ושהטקסט
> נכתב על ידי AI.
>
> האם קיים אצלכם עמוד "אפליקציות/שימושים בקהילה" שמציג פרויקטים שנבנו על
> הנתונים הפתוחים? אשמח אם govil.ai יוכל להופיע בו. אשמח גם לכל משוב, ולתקן
> כל דבר שנראה לכם לא מדויק.
>
> תודה רבה!

## 2. הסדנא לידע ציבורי (HaSadna) — partnership / listing

Where: https://www.hasadna.org.il/ contact form (or their Slack if you join).

> שלום לצוות הסדנא,
>
> אני מפתח את govil.ai — פרויקט אזרחי חינמי שהופך כל מאגר ב-data.gov.il לדף
> הסבר בעברית עם ויזואליזציות אינטראקטיביות, באמצעות סוכן AI שרץ יומית ומאומת
> מול נתוני המקור (כ-483 מאגרים עד כה). זה מרגיש קרוב ברוחו לפרויקטים שלכם,
> ואשמח: (א) לשמוע משוב מהקהילה שלכם, (ב) לבדוק אם מתאים לאזכר את הפרויקט
> ברשימת הפרויקטים/הקהילה שלכם, (ג) לשתף פעולה אם יש כיוון מתאים.
>
> תודה!

## 3. Press tips — Geektime / Calcalist / TheMarker

Where: https://www.geektime.co.il/contact/ · calcalist tech desk · themarker.com tips.
Angle: "סוכן AI שכותב דף הסבר בעברית לכל מאגר מידע ממשלתי — חינם". Attach 2–3
concrete examples readers care about (מקלטים בבאר שבע על מפה, מאגר קבלני כוח
אדם ורישיונות, מחירי סופר). Short version:

> היי, טיפ לסיקור: govil.ai הוא אתר חינמי שבו סוכן AI סורק מדי יום את פורטל
> המידע הממשלתי data.gov.il וכותב לכל מאגר דף הסבר בעברית פשוטה עם גרפים
> ומפות אינטראקטיביים — בלי להוריד אקסלים. כ-483 מאגרים כבר מכוסים והקטלוג
> גדל אוטומטית. הזווית: ממשל פתוח פוגש AI אג'נטי, פרויקט צד של מפתח יחיד,
> והכול שקוף לגבי היותו כתוב-AI ומאומת מול נתוני המקור. דוגמאות שכיף להראות:
> [מפת מקלטים] https://govil.ai/datasets/023b7883-3599-4cb7-adef-1a76ea051cf0/
> [קבלני כוח אדם] https://govil.ai/datasets/90b08091-d516-4b89-bea5-cce542ac61fb/
> אשמח לשיחה או לכל פרט נוסף.

## 4. Communities (post under your name; one post per community, no cross-spam)

**Hebrew Facebook/Telegram groups** (search by name, join, then post):
- "נתונים פתוחים ישראל" / Open Data Israel
- "Data Science & Machine Learning Israel"
- "סטארטאפיסטים" (Facebook)
- Telegram: ערוצי AI בעברית (e.g. "AI ישראל", "GenAI Israel")

> בניתי אתר חינמי שאולי יעניין פה: govil.ai. סוכן AI שסורק כל יום את
> data.gov.il וכותב לכל מאגר ממשלתי דף הסבר בעברית עם גרפים ומפות
> אינטראקטיביים. הכול שקוף (כתוב-AI, מאומת מול המקור) ובחינם. אשמח לפידבק —
> במיוחד על מאגרים שיצאו לכם לחפש ולא הצלחתם להבין.

**Reddit** — r/datasets (tool posts allowed; flair "Resource"), r/Israel (check
self-promo rule — usually fine as a free civic tool with engagement). Title:
"I built a free site that explains every Israeli government dataset in Hebrew
(AI-written, validated against the source)". Be present in comments.

**Show HN** — worth one shot; the architecture story is what HN wants:
title `Show HN: AI agent that writes an explainer page for every Israeli
government dataset`. In the text: the pipeline (scanner → agent sessions with
self-validation → static publish), the fabricated-chart guard, cost per page,
why Hebrew-first. Expect "is this just AI slop?" — answer with the validation
pipeline. Post morning US time, reply to every comment for the first hours.

**Product Hunt** — optional after HN; needs gallery screenshots + a tagline:
"Every Israeli government dataset, explained in Hebrew by an AI agent".

## 5. Already done for you (see log.md)

Two GitHub PRs (Israel-Open-Data-Resources, Israeli-AI), OKFN dataportals.org
eligibility issue, Open Data Inception + Civic Tech Field Guide submissions
(confirmation → admin@govil.ai), IndexNow automation in CI.
