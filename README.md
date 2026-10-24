# YouTube Shorts Uploader — مفتوح المصدر

أداة كاملة لرفع فيديوهات Shorts إلى يوتيوب مع عناوين، أوصاف، **هاشتاغات**،
وسوم (tags)، وتصنيف "مخصص للأطفال" (Made for Kids — COPPA).

---

## ⚠️ ملاحظة مهمة عن "إفصاح المحتوى الاصطناعي"

| الإعداد | متاح عبر API؟ |
|---|---|
| العنوان، الوصف، الهاشتاغات، الوسوم | ✅ |
| Made for Kids (تصنيف أطفال) | ✅ |
| الخصوصية، الجدولة | ✅ |
| **Altered / Synthetic Content Disclosure** | ❌ |

> خيار **"الإفصاح عن المحتوى المُعدَّل أو الاصطناعي"** غير متاح حالياً
> عبر YouTube Data API v3. يجب تفعيله **يدوياً** من YouTube Studio
> لكل فيديو بعد الرفع.

---

## هيكل المشروع

```
يوتيوب short/
├── upload_shorts.py        # السكريبت الرئيسي (YouTube Data API v3)
├── uploader_cli.py         # بديل يستخدم youtube-upload (tokland)
├── upload_one.bat          # رفع فيديو واحد من CMD
├── upload_all.bat          # رفع دفعة 5 فيديوهات من CMD
├── setup_scheduler.ps1     # ينشئ مهمة مجدولة في Windows Task Scheduler
├── run_setup_scheduler.bat # مُشغّل مرتفع لـ setup_scheduler.ps1
├── videos.example.json     # مثال لتكوين قائمة الفيديوهات
├── requirements.txt        # مكتبات Python المطلوبة
├── client_secrets.json     # ⚠️ يجب وضعه يدوياً (لا يُرفع على git)
└── README.md
```

---

## 1. إعداد OAuth2 (مرة واحدة)

1. افتح [Google Cloud Console](https://console.cloud.google.com/)
2. أنشئ مشروعاً جديداً (أو استخدم مشروعاً قائماً)
3. **APIs & Services → Library** → فعّل **YouTube Data API v3**
4. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
   - Application type: **Desktop app**
5. حمّل ملف JSON واحفظه في هذا المجلد باسم `client_secrets.json`
6. في **OAuth consent screen** أضف بريدك كـ *Test user* أثناء فترة الاختبار

---

## 2. تثبيت المتطلبات (مُنفّذ ✅)

```powershell
pip install -r requirements.txt
pip install youtube-upload
```

> ملاحظة: `youtube-upload` غير موجود على PyPI، يُثبَّت من GitHub:
> `pip install https://github.com/tokland/youtube-upload/archive/master.zip`

---

## 3. التشغيل — الطريقة الأولى (Python API)

### أ. رفع الفيديوهات الافتراضية الخمسة

```powershell
python upload_shorts.py
```

في أول تشغيل سيفتح المتصفح لإكمال تسجيل الدخول إلى حساب يوتيوب.

### ب. رفع من ملف إعداد مخصص

أنسخ `videos.example.json` إلى `videos.json` وعدّل ما تريد، ثم:

```powershell
python upload_shorts.py --config videos.json
```

### ج. خيارات إضافية

```powershell
# رفع كـ unlisted للمراجعة قبل النشر
python upload_shorts.py --privacy unlisted

# تعطيل خيار Made for Kids
python upload_shorts.py --no-kids
```

---

## 4. التشغيل — الطريقة الثانية (CLI بدون كود)

### أ. رفع فيديو واحد

```bat
upload_one.bat sand_castle.mp4 "Fun Sandbox Time!" "وصف الفيديو"
```

### ب. رفع الدفعة كاملة

```bat
upload_all.bat
```

### ج. عبر أداة youtube-upload مباشرة

```powershell
youtube-upload `
  --title="Fun Sandbox Time! 🏰" `
  --description="وصف الفيديو #NurseryRhymes #KidsSongs #NuNuTv #Shorts" `
  --category=24 `
  --privacy=public `
  --tags="sand castle,toddler,3d animation,nursery rhymes" `
  --made-for-kids `
  sand_castle.mp4
```

---

## 5. جدولة رفع تلقائي (Windows Task Scheduler) — جاهز للنقر

> تم إنشاء `run_setup_scheduler.bat` و `setup_scheduler.ps1`.
> **يكفي أن تنقر مرتين على `run_setup_scheduler.bat`** فيطلب صلاحيات
> المسؤول تلقائياً ويُسجّل المهمة.

| الإعداد | القيمة |
|---|---|
| اسم المهمة | `YouTube Shorts Daily Upload` |
| المُشغّل | يومياً الساعة **10:00 صباحاً** |
| البرنامج | `python` |
| المعاملات | `upload_shorts.py --privacy public` |
| مجلد العمل | مسار المشروع |
| صلاحيات | SYSTEM، Highest، يعمل حتى على البطارية |

### الإدارة بعد الإنشاء

```powershell
# فتح وحدة المهام المجدولة
taskschd.msc

# تشغيل المهمة فوراً
schtasks /run /tn "YouTube Shorts Daily Upload"

# حذف المهمة
schtasks /delete /tn "YouTube Shorts Daily Upload" /f
```

---

## 6. الملفات المطلوبة قبل التشغيل

| الملف | الحالة |
|---|---|
| `client_secrets.json` | ⚠️ يجب تحميله من Google Cloud Console |
| الفيديوهات (`sand_castle.mp4`, `balloons.mp4`, ...) | ضعها في نفس المجلد |

---

## 7. بعد الرفع — لا تنسَ!

- ✅ افتح [YouTube Studio](https://studio.youtube.com/)
- ✅ لكل فيديو جديد: **Details → Altered Content**
- ✅ فعّل: *"This video contains altered or synthetic content"*

---

## 8. التحقق التقني الذي تم تلقائياً

| الفحص | النتيجة |
|---|---|
| تركيب المكتبات من `requirements.txt` | ✅ |
| تركيب `youtube-upload` من GitHub | ✅ |
| صحة بناء جملة `upload_shorts.py` | ✅ |
| صحة بناء جملة `uploader_cli.py` | ✅ |
| صحة JSON في `videos.example.json` (5 فيديوهات) | ✅ |
| تشغيل `upload_shorts.py --help` | ✅ |
| تشغيل `python -m youtube_upload --help` | ✅ |
| اختبار رسالة الخطأ عند غياب `client_secrets.json` | ✅ |

---

## الرخصة

الكود في هذا المشروع مرخص بموجب **GNU GPLv3**.
أداة [youtube-upload](https://github.com/tokland/youtube-upload) مرخصة GPLv3 أيضاً.
