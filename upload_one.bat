@echo off
REM ============================================================
REM سكربت رفع فيديو شورتس واحد إلى يوتيوب (Windows)
REM ============================================================
REM الاستخدام:
REM   upload_one.bat sand_castle.mp4 "Fun Sandbox Time!"
REM ============================================================

set VIDEO_FILE=%1
set VIDEO_TITLE=%2
set VIDEO_DESC=%3

if "%VIDEO_FILE%"=="" (
    echo [خطأ] يرجى تمرير اسم ملف الفيديو.
    echo   مثال: upload_one.bat sand_castle.mp4 "Fun Sandbox Time!" "وصف..."
    exit /b 1
)
if "%VIDEO_TITLE%"=="" set VIDEO_TITLE=Fun Video
if "%VIDEO_DESC%"=="" set VIDEO_DESC=أ_child يلعب في الرمل ويبني قلعة.

youtube-upload ^
    --title="%VIDEO_TITLE%" ^
    --description="%VIDEO_DESC% #NurseryRhymes #KidsSongs #NuNuTv #Shorts #ToddlerLearning #3DAnimation #KidsEntertainment #BabySongs #PreschoolActivities" ^
    --category=24 ^
    --privacy=public ^
    --tags="nursery rhymes,kids songs,toddler,3d animation" ^
    --made-for-kids ^
    "%VIDEO_FILE%"

if %ERRORLEVEL% NEQ 0 (
    echo [فشل] تعذّر رفع الفيديو.
    exit /b %ERRORLEVEL%
)
echo [نجاح] تم رفع الفيديو.
