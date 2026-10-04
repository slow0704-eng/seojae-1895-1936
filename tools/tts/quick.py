# -*- coding: utf-8 -*-
"""낭독 작업용 빠른 재빌드: 서재/index.html 과 서재/tts/ 만 다시 씁니다(본문 데이터·글꼴은 그대로).

    python tts/quick.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import build

cat = build.build_catalog()
idx = build.index_page(cat, cat["works"])
with open(os.path.join(build.SITE, "index.html"), "wb") as f:
    f.write(idx.encode("utf-8"))
build.write_tts()
print("index.html %s bytes, tts/ written" % "{:,}".format(len(idx)))
