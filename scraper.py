#!/usr/bin/env python3
"""iOS DevPulse scraper — 抓取 Apple / Swift 官方动态与常用开源库发布，输出 data.json。仅依赖 Python 标准库。"""
import gzip, html, json, re, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

OUT = Path(__file__).with_name("data.json")
CST = timezone(timedelta(hours=8))
UA  = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
ATOM = "{http://www.w3.org/2005/Atom}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}encoded"
MAX_ITEMS = 500       # 动态流累积上限
LIB_KEEP  = 5         # 每个库保留最近几个版本
# 详情页用的长文本上限（列表摘要仍是 200 字）
BODY_LIB, BODY_BLOG, BODY_NEWS = 1500, 600, 800

# 关注的开源库：（GitHub 仓库, 展示名）。增删直接改这里
LIBS = [
    ("SnapKit/Masonry",              "Masonry"),
    ("ibireme/YYKit",                "YYKit"),
    ("airbnb/lottie-ios",            "Lottie"),
    ("Instagram/IGListKit",          "IGListKit"),
    ("pujiaxin33/JXCategoryView",    "JXCategoryView"),
    ("pujiaxin33/JXPagingView",      "JXPagingView"),
    ("CoderMJLee/MJRefresh",         "MJRefresh"),
    ("hackiftekhar/IQKeyboardManager", "IQKeyboardManager"),
    ("AFNetworking/AFNetworking",    "AFNetworking"),
    ("SDWebImage/SDWebImage",        "SDWebImage"),
    ("Alamofire/Alamofire",          "Alamofire"),
    ("SnapKit/SnapKit",              "SnapKit"),
]

# Swift Evolution 中「进行中」的状态，全部展示；已实现的只展示最近若干个
EVO_ACTIVE = {"activeReview": "审核中", "accepted": "已接受", "previewing": "预览中",
              "returnedForRevision": "退回修改", "scheduledForReview": "待审核"}
EVO_DONE_KEEP = 30

# ── 工具 ──────────────────────────────────────────────────────────────────────

def fetch(url, timeout=15):
    raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()
    # swift.org 不管请求头都返回 gzip，按魔数判断自行解压
    return gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw

def clean(text, n=200):
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()
    return (text[:n] + "…") if len(text) > n else text

def iso(dt):
    return dt.astimezone(CST).isoformat(timespec="seconds")

def rfc822(s):
    try:
        return iso(parsedate_to_datetime(s))
    except Exception:
        return ""

def item(source, kind, title, url, date, summary="", body_n=0, **extra):
    row = {"id": url, "source": source, "kind": kind, "title": clean(title, 160), "url": url,
           "date": date, "summary": clean(summary), **extra}
    body = clean(summary, body_n) if body_n else ""
    if body and body != row["summary"]:       # 比摘要长才另存，详情页展示
        row["body"] = body
    return row

def html_links(text, base):
    """RSS content:encoded 里的链接（发布说明、下载）→ [{text, url}]"""
    out = []
    for href, label in re.findall(r"<a\s[^>]*href=[\"']?([^\"' >]+)[^>]*>(.*?)</a>", text or "", re.S):
        label = clean(label, 40)
        if label:
            out.append({"text": label, "url": urllib.parse.urljoin(base, html.unescape(href))})
    return out

def rss_items(url):
    return list(ET.fromstring(fetch(url)).iter("item"))

def atom_entries(url):
    return ET.fromstring(fetch(url)).findall(ATOM + "entry")

def atom_link(e):
    el = e.find(ATOM + "link")
    return el.get("href", "") if el is not None else ""

# ── Apple ─────────────────────────────────────────────────────────────────────

PLATFORMS = ["Xcode", "iOS", "iPadOS", "macOS", "watchOS", "tvOS", "visionOS"]

def parse_release(title):
    """'Xcode 27.2 RC (27B48)' → ('Xcode', '27.2', 'RC', '27B48')"""
    m = re.match(r"(Xcode|iOS|iPadOS|macOS|watchOS|tvOS|visionOS)\s+([\d.]+)\s*(.*?)\s*(?:\(([^)]+)\))?$", title.strip())
    if not m:
        return None, "", "", ""
    platform, version, rest, build = m.groups()
    rest = rest.strip()
    if re.match(r"beta", rest, re.I):
        stage = rest.replace("beta", "Beta")
    elif rest.upper().startswith("RC"):
        stage = rest.upper()
    else:
        stage = rest or "正式版"
    return platform, version, stage, build or ""

def apple_releases():
    out = []
    for it in rss_items("https://developer.apple.com/news/releases/rss/releases.rss"):
        title = it.findtext("title", "")
        platform, version, stage, build = parse_release(title)
        link = it.findtext("link", "")
        # description 只是「View release notes」之类的按钮文字，不当摘要；content:encoded 里的链接留给详情页
        out.append(item("apple-releases", "release", title, link,
                        rfc822(it.findtext("pubDate", "")),
                        platform=platform or "其他", version=version, stage=stage, build=build,
                        links=html_links(it.findtext(CONTENT, ""), link)))
    return out

def apple_news(limit=60):
    return [item("apple-news", "news", it.findtext("title", ""), it.findtext("link", ""),
                 rfc822(it.findtext("pubDate", "")), it.findtext("description", ""), BODY_NEWS)
            for it in rss_items("https://developer.apple.com/news/rss/news.rss")[:limit]]

# ── Swift ─────────────────────────────────────────────────────────────────────

def swift_blog():
    return [item("swift-blog", "blog", e.findtext(ATOM + "title", ""), atom_link(e),
                 e.findtext(ATOM + "updated", "") or e.findtext(ATOM + "published", ""),
                 e.findtext(ATOM + "content", "") or e.findtext(ATOM + "summary", ""), BODY_BLOG)
            for e in atom_entries("https://www.swift.org/atom.xml")]

def swift_evolution():
    data = json.loads(fetch("https://download.swift.org/swift-evolution/v1/evolution.json"))
    base = "https://github.com/swiftlang/swift-evolution/blob/main/proposals/"
    rows = []
    for p in data["proposals"]:
        st = p.get("status", {})
        rows.append({
            "id":      p["id"],
            "title":   clean(p.get("title", ""), 120),
            "state":   st.get("state", ""),
            "version": st.get("version", ""),
            "start":   st.get("start", ""),
            "end":     st.get("end", ""),
            "url":     base + p.get("link", ""),
            "summary": clean(p.get("summary", ""), 220),
            "authors": [a.get("name", "") for a in p.get("authors", []) if a.get("name")],
            "review_manager": [a.get("name", "") for a in p.get("reviewManagers", []) if a.get("name")],
            # 论坛讨论（pitch / review…）
            "discussions": [{"name": d.get("name", ""), "url": d.get("link", "")} for d in p.get("discussions", []) if d.get("link")],
        })
    num = lambda r: int(re.sub(r"\D", "", r["id"]) or 0)
    active = sorted((r for r in rows if r["state"] in EVO_ACTIVE), key=num, reverse=True)
    done = sorted((r for r in rows if r["state"] == "implemented"), key=num, reverse=True)[:EVO_DONE_KEEP]
    return active + done

# ── 开源库 ────────────────────────────────────────────────────────────────────

def lib_releases(repo, name):
    # 有的库只打 tag 不发 Release，releases.atom 为空时改读 tags.atom
    entries = atom_entries(f"https://github.com/{repo}/releases.atom")
    if not entries:
        entries = atom_entries(f"https://github.com/{repo}/tags.atom")
    out = []
    for e in entries[:LIB_KEEP]:
        version = (e.findtext(ATOM + "id", "") or "").rsplit("/", 1)[-1]
        # 标题常以版本号开头（"8.0.3 Dependency updates"、"Release v6.0.0"），去掉重复部分只留说明
        bare = re.escape(version.lstrip("v"))
        note = re.sub(rf"^\s*(release\s*)?v?{bare}\s*[-–—:·]?\s*", "", e.findtext(ATOM + "title", ""), flags=re.I).strip()
        label = f"{version} · {note}" if note else version
        body = e.findtext(ATOM + "content", "")
        if clean(body).lower() in ("no content.", "no content"):   # GitHub 对空说明的占位文案
            body = ""
        out.append(item("libs", "lib", f"{name} {label}", atom_link(e) or f"https://github.com/{repo}/releases",
                        e.findtext(ATOM + "updated", ""), body, BODY_LIB,
                        lib=name, repo=repo, version=version))
    return out

# ── 主流程 ────────────────────────────────────────────────────────────────────

# id, 名称, 头像缩写, 主题色, 抓取函数
SOURCES = [
    ("apple-releases", "Apple 版本发布", "A",  "#0a84ff", apple_releases),
    ("apple-news",     "Apple 开发者新闻", "A",  "#8e8e93", apple_news),
    ("swift-blog",     "Swift 博客",     "S",  "#f05138", swift_blog),
]

def run(label, fn):
    try:
        res = fn()
        print(f"  ✓ {label:<22} {len(res):>3}")
        return res, ""
    except Exception as e:
        err = f"{type(e).__name__}: {e}"[:200]
        print(f"  ✗ {label:<22}   0 {err}")
        return None, err

def main():
    prev = {}
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text())
        except Exception:
            pass
    prev_src = {s["id"]: s for s in prev.get("sources", [])}
    now = iso(datetime.now(CST))

    print("→ 抓取")
    with ThreadPoolExecutor(max_workers=8) as pool:
        src_futs = [(s, pool.submit(run, s[1], s[4])) for s in SOURCES]
        lib_futs = [(r, n, pool.submit(run, n, lambda r=r, n=n: lib_releases(r, n))) for r, n in LIBS]
        evo_fut = pool.submit(run, "Swift Evolution", swift_evolution)

    new_items, sources = [], []
    for (sid, name, abbr, color, _), fut in src_futs:
        res, err = fut.result()
        p = prev_src.get(sid, {})
        sources.append({"id": sid, "name": name, "abbr": abbr, "color": color, "ok": res is not None,
                        "error": err, "count": len(res or []),
                        # 失败时保留上次成功时间，页面据此标注「旧数据」
                        "updated": now if res is not None else p.get("updated", "")})
        new_items += res or []

    libs, lib_errors = [], 0
    prev_libs = {l["repo"]: l for l in prev.get("libs", [])}
    for repo, name, fut in lib_futs:
        res, err = fut.result()
        if res is None:
            lib_errors += 1
            if repo in prev_libs:
                libs.append({**prev_libs[repo], "stale": True})
            continue
        new_items += res
        latest = res[0] if res else None
        libs.append({"repo": repo, "name": name, "ok": True, "stale": False,
                     "version": latest["version"] if latest else "", "date": latest["date"] if latest else "",
                     "url": latest["url"] if latest else f"https://github.com/{repo}",
                     "summary": latest["summary"] if latest else "",
                     "body": latest.get("body", "") if latest else "",
                     "history": [{"version": r["version"], "date": r["date"], "url": r["url"]} for r in res]})
    sources.append({"id": "libs", "name": "开源库发布", "abbr": "GH", "color": "#6e40c9",
                    "ok": lib_errors == 0, "error": f"{lib_errors} 个库抓取失败" if lib_errors else "",
                    "count": len(libs), "updated": now})

    evo, err = evo_fut.result()
    sources.append({"id": "swift-evolution", "name": "Swift Evolution", "abbr": "SE", "color": "#f05138",
                    "ok": evo is not None, "error": err, "count": len(evo or prev.get("evolution", [])),
                    "updated": now if evo is not None else prev_src.get("swift-evolution", {}).get("updated", "")})
    if evo is None:
        evo = prev.get("evolution", [])

    # 与上一份合并去重，历史条目慢慢累积；同一 id 以新抓到的为准
    merged = {it["id"]: it for it in prev.get("items", [])}
    for it in new_items:
        first_seen = merged.get(it["id"], {}).get("first_seen", now)
        merged[it["id"]] = {**it, "first_seen": first_seen}
    items = sorted(merged.values(), key=lambda it: it["date"] or "", reverse=True)[:MAX_ITEMS]

    data = {
        "updated":   now,   # 每次都变，保证每次运行都有提交，仓库不会因不活跃被停用
        "sources":   sources,
        "items":     items,
        "libs":      sorted(libs, key=lambda l: l["date"] or "", reverse=True),
        "evolution": evo,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    ok = sum(s["ok"] for s in sources)
    print(f"→ 完成：{ok}/{len(sources)} 个来源正常，动态 {len(items)} 条，库 {len(libs)} 个，"
          f"提案 {len(evo)} 个 → {OUT.name}")

if __name__ == "__main__":
    main()
