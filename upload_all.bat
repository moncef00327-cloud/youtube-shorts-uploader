@echo off
REM ============================================================
REM رفع دفعة من 5 فيديوهات شورتس إلى يوتيوب (Windows)
REM يستخدم أداة youtube-upload من سطر الأوامر
REM ============================================================

set HASHTAGS=#NurseryRhymes #KidsSongs #NuNuTv #Shorts #ToddlerLearning #3DAnimation #KidsEntertainment #BabySongs #PreschoolActivities
set BASE_DESC=أ_child يلعب في الرمل ويبني قلعة صغيرة.

echo [بدء] رفع دفعة من 5 فيديوهات...

youtube-upload --title="Fun Sandbox Time! 🏰" --description="%BASE_DESC% %HASHTAGS%" --category=24 --privacy=public --tags="sand castle,toddler,3d animation,nursery rhymes" --made-for-kids sand_castle.mp4
if %ERRORLEVEL% NEQ 0 goto :error

youtube-upload --title="Colorful Balloons in the Garden 🎈" --description="الطفل يحمل بالونات ملونة. %HASHTAGS%" --category=24 --privacy=public --tags="balloons,garden,toddler,kids songs" --made-for-kids balloons.mp4
if %ERRORLEVEL% NEQ 0 goto :error

youtube-upload --title="Dancing with Baby Elephant 🐘" --description="الطفل يرقص مع فيل صغير. %HASHTAGS%" --category=24 --privacy=public --tags="elephant,dancing,toddler,nursery rhymes" --made-for-kids elephant.mp4
if %ERRORLEVEL% NEQ 0 goto :error

youtube-upload --title="Finger Painting Fun 🎨" --description="الطفل يرسم بألوان الأصابع. %HASHTAGS%" --category=24 --privacy=public --tags="painting,colors,toddler,kids learning" --made-for-kids painting.mp4
if %ERRORLEVEL% NEQ 0 goto :error

youtube-upload --title="Yellow Construction Helmet 🦺" --description="الطفل يرتدي خوذة بناء. %HASHTAGS%" --category=24 --privacy=public --tags="helmet,construction,curiosity,toddler" --made-for-kids helmet.mp4
if %ERRORLEVEL% NEQ 0 goto :error

echo.
echo [اكتمل] تم رفع جميع الفيديوهات الخمسة بنجاح.
echo.
echo ⚠️  تذكير: افتح YouTube Studio لكل فيديو وشغّل
echo    "الإفصاح عن المحتوى الاصطناعي / المعدَّل" يدوياً.
exit /b 0

:error
echo.
echo [فشل] توقف السكربت بسبب خطأ في الرفع.
exit /b 1
