#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Shorts Uploader - Open Source
=====================================
يرفع فيديوهات شورتس إلى يوتيوب مع عناوين، أوصاف، هاشتاغات، وتصنيف أطفال.

ملاحظة مهمة:
- إفصاح المحتوى الاصطناعي (Altered or Synthetic Content Disclosure)
  لا يوجد حقل له في YouTube Data API v3 حالياً، ويجب تفعيله يدوياً
  من YouTube Studio لكل فيديو بعد الرفع.
"""

import os
import sys
import json
import argparse

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.http import MediaFileUpload

# ---------- إعدادات عامة ----------
CLIENT_SECRETS_FILE = "client_secrets.json"
TOKEN_FILE = "token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"

# الهاشتاغات الثابتة التي تُضاف إلى نهاية الوصف
DEFAULT_HASHTAGS = [
    "#NurseryRhymes",
    "#KidsSongs",
    "#NuNuTv",
    "#Shorts",
    "#ToddlerLearning",
    "#3DAnimation",
    "#KidsEntertainment",
    "#BabySongs",
    "#PreschoolActivities",
]

# فيديوهات افتراضية (تُستخدم عند عدم تمرير ملف إعدادات)
DEFAULT_VIDEOS = [
    {
        "file": "sand_castle.mp4",
        "title": "Fun Sandbox Time! 🏰 | Nursery Rhymes",
        "description": "أ_child يلعب في الرمل ويبني قلعة صغيرة في صندوق الرمل. مشاهدة ممتعة للأطفال الصغار!",
        "tags": ["sand castle", "toddler", "3d animation", "nursery rhymes"],
    },
    {
        "file": "balloons.mp4",
        "title": "Colorful Balloons in the Garden 🎈 | Kids Songs",
        "description": "الطفل يحمل بالونات ملونة في حديقة خضراء. جو مرح ومشرق!",
        "tags": ["balloons", "garden", "toddler", "kids songs"],
    },
    {
        "file": "elephant.mp4",
        "title": "Dancing with Baby Elephant 🐘 | Nursery Rhymes",
        "description": "الطفل يرقص مع فيل صغير أصفر صديق في غرفة الأطفال.",
        "tags": ["elephant", "dancing", "toddler", "nursery rhymes"],
    },
    {
        "file": "painting.mp4",
        "title": "Finger Painting Fun 🎨 | Kids Learning",
        "description": "الطفل يرسم بألوان الأصابع على الأرض. إبداع وألوان مبهجة!",
        "tags": ["painting", "colors", "toddler", "kids learning"],
    },
    {
        "file": "helmet.mp4",
        "title": "Yellow Construction Helmet 🦺 | Toddler Learning",
        "description": "الطفل يرتدي خوذة بناء صفراء وينظر بفضول في منطقة اللعب المشرقة.",
        "tags": ["helmet", "construction", "curiosity", "toddler"],
    },
]


# ---------- دوال ----------
def get_authenticated_service():
    """التحقق من الهوية باستخدام OAuth2 المحلي وإرجاع كائن خدمة يوتيوب."""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        print(f"❌ ملف {CLIENT_SECRETS_FILE} غير موجود.")
        print("   حمّله من Google Cloud Console → APIs & Services → Credentials.")
        sys.exit(1)

    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, SCOPES
    )
    # run_local_server يفتح متصفحاً محلياً لإكمال تسجيل الدخول
    credentials = flow.run_local_server(port=0)
    return googleapiclient.discovery.build(
        API_SERVICE_NAME, API_VERSION, credentials=credentials
    )


def build_metadata(
    title,
    description,
    tags=None,
    category_id="24",
    privacy_status="public",
    made_for_kids=True,
    hashtags=None,
    publish_at=None,
):
    """
    بناء جسم البيانات الوصفية للفيديو.
    category_id=24 => 'People & Blogs'
    """
    if tags is None:
        tags = []
    if hashtags is None:
        hashtags = DEFAULT_HASHTAGS

    # إضافة الهاشتاغات إلى نهاية الوصف لتظهر كروابط قابلة للنقر
    hashtags_line = " " + " ".join(hashtags)
    full_description = description + hashtags_line

    status = {
        "privacyStatus": privacy_status,           # public | unlisted | private
        "selfDeclaredMadeForKids": bool(made_for_kids),
        "madeForKids": bool(made_for_kids),
        "embedable": True,
        "publicStatsViewable": True,
    }
    if publish_at:
        # عند الجدولة يجب أن تكون privacyStatus = private
        status["publishAt"] = publish_at
        status["privacyStatus"] = "private"

    return {
        "snippet": {
            "title": title,
            "description": full_description,
            "tags": tags,
            "categoryId": category_id,
            "defaultLanguage": "ar",
            "defaultAudioLanguage": "ar",
        },
        "status": status,
    }


def upload_video(youtube, file_path, title, description, tags=None,
                 privacy_status="public", made_for_kids=True, publish_at=None):
    """رفع فيديو واحد إلى يوتيوب وإرجاع (video_id, url)."""
    body = build_metadata(
        title=title,
        description=description,
        tags=tags,
        privacy_status=privacy_status,
        made_for_kids=made_for_kids,
        publish_at=publish_at,
    )

    insert_request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(file_path, chunksize=-1, resumable=True),
    )

    print(f"⏳ جاري الرفع: {title} ...")
    response = None
    while response is None:
        status, response = insert_request.next_chunk()
        if status:
            print(f"   التقدم: {int(status.progress() * 100)}%")

    video_id = response["id"]
    video_url = f"https://www.youtube.com/shorts/{video_id}"
    print(f"✅ تم الرفع بنجاح: {video_url}")
    return video_id, video_url


def load_videos_from_config(config_path):
    """تحميل قائمة الفيديوهات من ملف JSON."""
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    if "videos" not in config:
        raise ValueError("ملف الإعدادات يجب أن يحتوي على مفتاح 'videos'.")
    return config["videos"]


# ---------- التشغيل الرئيسي ----------
def main():
    parser = argparse.ArgumentParser(
        description="رفع فيديوهات Shorts إلى يوتيوب مع وسوم وهاشتاغات."
    )
    parser.add_argument(
        "--config",
        help="مسار ملف JSON يحوي قائمة الفيديوهات (اختياري).",
        default=None,
    )
    parser.add_argument(
        "--privacy",
        choices=["public", "unlisted", "private"],
        default="public",
        help="حالة الخصوصية الافتراضية.",
    )
    parser.add_argument(
        "--no-kids",
        action="store_true",
        help="تعطيل تصنيف 'Made for Kids' (مخصص للأطفال).",
    )
    args = parser.parse_args()

    if args.config:
        videos = load_videos_from_config(args.config)
    else:
        videos = DEFAULT_VIDEOS

    youtube = get_authenticated_service()

    results = []
    for v in videos:
        file_path = v["file"]
        if not os.path.exists(file_path):
            print(f"⚠️  الملف غير موجود، تخطي: {file_path}")
            results.append({
                "title": v["title"],
                "status": "skipped",
                "reason": "file not found",
            })
            continue

        try:
            vid, url = upload_video(
                youtube=youtube,
                file_path=file_path,
                title=v["title"],
                description=v["description"],
                tags=v.get("tags", []),
                privacy_status=v.get("privacy", args.privacy),
                made_for_kids=v.get("made_for_kids", not args.no_kids),
                publish_at=v.get("publish_at"),
            )
            results.append({
                "title": v["title"],
                "video_id": vid,
                "url": url,
                "status": "success",
            })
        except googleapiclient.errors.HttpError as e:
            err = f"HTTP {e.resp.status}: {e._get_reason() if hasattr(e, '_get_reason') else e}"
            print(f"❌ فشل رفع {file_path}: {err}")
            results.append({
                "title": v["title"],
                "status": "failed",
                "error": err,
            })
        except Exception as e:
            print(f"❌ فشل رفع {file_path}: {e}")
            results.append({
                "title": v["title"],
                "status": "failed",
                "error": str(e),
            })

    # ---------- تقرير نهائي ----------
    print("\n" + "=" * 60)
    print("📋 تقرير التنفيذ النهائي")
    print("=" * 60)
    success = fail = skipped = 0
    for r in results:
        if r["status"] == "success":
            success += 1
            print(f"✅ {r['title']} → {r['url']}")
        elif r["status"] == "skipped":
            skipped += 1
            print(f"⏭️  {r['title']} → تم التخطي ({r.get('reason')})")
        else:
            fail += 1
            print(f"❌ {r['title']} → فشل: {r.get('error')}")

    print(f"\n📊 الإحصاء: {success} نجاح | {fail} فشل | {skipped} تخطي")

    print("\n⚠️  تذكير مهم:")
    print("   افتح YouTube Studio لكل فيديو وشغّل خيار")
    print("   'الإفصاح عن المحتوى الاصطناعي / المعدَّل' (Altered or Synthetic Content).")
    print("   هذا الخيار غير متاح عبر API حالياً.")

    # كتابة تقرير JSON مفصّل
    report_path = "upload_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n💾 تم حفظ التقرير التفصيلي في: {report_path}")


if __name__ == "__main__":
    main()
