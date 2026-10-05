# XAUUSD Pro Signal Bot v3.0.0

بوت تداول احترافي متعدد الوحدات لزوج الذهب XAUUSD يرسل إشارات شراء/بيع على تليجرام مع نقطة الدخول والستوب لوس وعدة أهداف (TP1/TP2/TP3).

## المميزات

- **8 استراتيجيات تداول** قابلة للتوصيل (Trend Following, Mean Reversion, Breakout, Scalping, Ichimoku, MACD+RSI, Bollinger Squeeze, Supply/Demand)
- **تحليل متعدد الفريمات** (1m, 5m, 15m, 30m, 1h, 4h) مع نظام تقييم التقاء (Confluence Scoring)
- **+25 مؤشر فني** مكتوب بلغة Python نقية (بدون مكتبات خارجية)
- **حساب ديناميكي لـ SL/TP** يعتمد على ATR + نقاط التأرجح (Swing) + فيبوناتشي
- **إدارة مخاطر كاملة**: حجم اللوت حسب نسبة المخاطرة، حد خسائر يومية، حد أقصى للسحب (Drawdown)، Cooldown بين الإشارات
- **محرك باك تيست** كامل مع Walk-Forward Analysis ومقاييس أداء (Sharpe, Sortino, Calmar, Profit Factor)
- **قاعدة بيانات SQLAlchemy** لحفظ الإشارات والصفقات ولقطات الأداء
- **رابط تليجرام** كامل: أوامر، أزرار inline، تقارير يومية/أسبوعية، تنبيهات عطل
- **لوحة تحكم ويب** (Flask) مع حماية بكلمة مرور تعرض الإشارات والأداء لحظياً
- **Docker + docker-compose** جاهزة للتشغيل على VPS

## التثبيت السريع

```bash
git clone <repo> && cd xauusd_pro_bot
pip install -r requirements.txt
cp .env.example .env   # الاعتمادات جاهزة مسبقاً في .env
python run.py
```

## التشغيل عبر Docker

```bash
docker-compose up -d
```

## الأوامر

```bash
python run.py              # تشغيل كامل (فحص + تليجرام + لوحة ويب)
python run.py --no-web     # بدون لوحة ويب
python run.py --backtest   # تشغيل باك تيست
python run.py --health     # فحص الصحة
pytest tests/              # تشغيل الاختبارات
```

## لوحة التحكم

افتح `http://<server-ip>:8080` — المستخدم `admin` / كلمة المرور في `.env` (WEB_PASSWORD).

## أوامر تليجرام

- `/start` — القائمة الرئيسية
- `/price` — سعر XAUUSD الحالي
- `/signals` — آخر الإشارات
- `/performance` — تقرير الأداء
- `/settings` — الإعدادات
- `/id` — معرفة Chat ID

## هيكل المشروع

```
xauusd_pro_bot/
├── config/          الإعدادات والثوابت
├── core/            أدوات مساعدة + لوغ + استثناءات
├── data/            طبقة البيانات (BiQuote) + كاش + تخزين
├── indicators/      +25 مؤشر فني
├── strategies/      8 استراتيجيات + محرك التقاء متعدد الفريمات
├── signal/          مولد الإشارات + حساب TP/SL + فلاتر
├── risk/            إدارة المخاطر + حجم اللوت + حدود
├── backtest/        محرك الباك تيست + Walk-Forward + تقارير
├── telegram_bot/    رابط التليجرام + تنسيق الرسائل + معالجات
├── database/        SQLAlchemy models + Repository
├── scheduler/       الحلقة الرئيسية + وظائف دورية
├── reporting/       تقارير يومية/أسبوعية + تتبع أداء
├── web/             لوحة تحكم Flask
├── tests/           اختبارات unit
├── scripts/         أدوات مساعدة
└── run.py           نقطة الدخول الرئيسية
```

## تنبيه هام

⚠️ هذا البوت أداة تحليلية ترسل إشارات بناءً على مؤشرات فنية. **ليس نصيحة استثمارية.** التداول في الذهب والعملات ينطوي على مخاطر مالية عالية. استخدم البوت على مسؤوليتك الخاصة واختبره أولاً بحساب تجريبي (Demo).

## الأمان

- التوكن والـ Chat ID مخزنان في `.env` (لا ترفعهما على GitHub)
- لوحة الويب محمية بـ Basic Auth
- حد أقصى لعدد الإشارات اليومية وللخسائر لحماية الحساب
