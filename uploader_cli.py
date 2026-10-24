#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بديل CLI باستخدام أداة youtube-upload (tokland).
استخدام:
  python uploader_cli.py sand_castle.mp4 \
      --title "Fun Sandbox Time! 🏰" \
      --description "وصف الفيديو..." \
      --tags "sand castle,toddler,3d animation"
"""

import argparse
import subprocess
import sys
import shlex

HASHTAGS_DESCRIPTION = (
    "#NurseryRhymes #KidsSongs #NuNuTv #Shorts "
    "#ToddlerLearning #3DAnimation #KidsEntertainment "
    "#BabySongs #PreschoolActivities"
)

DEFAULT_TAGS = "nursery rhymes,kids songs,toddler,3d animation"


def run_youtube_upload(file_path, title, description, tags, category="24",
                      privacy="public", made_for_kids=True):
    cmd = [
        "youtube-upload",
        f"--title={title}",
        f"--description={description}",
        f"--category={category}",
        f"--privacy={privacy}",
        f"--tags={tags}",
    ]
    if made_for_kids:
        cmd.append("--made-for-kids")

    cmd.append(file_path)
    print("▶️  تنفيذ:", " ".join(shlex.quote(c) for c in cmd))
    try:
        subprocess.run(cmd, check=True)
        print(f"✅ تم رفع {file_path} بنجاح.")
    except FileNotFoundError:
        print("❌ أداة youtube-upload غير مثبّتة.")
        print("   ثبّتها بالأمر: pip install youtube-upload")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"❌ فشل الرفع برمز الخروج {e.returncode}.")
        sys.exit(e.returncode)


def main():
    p = argparse.ArgumentParser(
        description="رفع فيديو يوتيوب عبر أداة youtube-upload (CLI)."
    )
    p.add_argument("file", help="مسار ملف الفيديو.")
    p.add_argument("--title", required=True, help="عنوان الفيديو.")
    p.add_argument(
        "--description",
        default=HASHTAGS_DESCRIPTION,
        help="وصف الفيديو (افتراضياً: قائمة الهاشتاغات).",
    )
    p.add_argument(
        "--tags", default=DEFAULT_TAGS,
        help="وسوم مفصولة بفواصل.",
    )
    p.add_argument("--category", default="24", help="رقم التصنيف (24=People & Blogs).")
    p.add_argument(
        "--privacy", default="public",
        choices=["public", "unlisted", "private"],
        help="حالة الخصوصية.",
    )
    p.add_argument(
        "--no-kids", action="store_true",
        help="تعطيل خيار Made for Kids.",
    )
    args = p.parse_args()

    run_youtube_upload(
        file_path=args.file,
        title=args.title,
        description=args.description,
        tags=args.tags,
        category=args.category,
        privacy=args.privacy,
        made_for_kids=not args.no_kids,
    )


if __name__ == "__main__":
    main()
