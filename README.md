# 📱 iOS DevPulse · iOS 开发动态

> 一个页面看全 Apple 官方发布、Swift 动态和常用开源库的新版本，每 6 小时自动更新

**🌐 在线访问：[https://climb0516.github.io/ios-dev-news/](https://climb0516.github.io/ios-dev-news/)**

---

## 功能

- **动态流**：所有来源按时间倒序，7 天内的条目带「新」标签；可按分类（版本发布 / 开发者新闻 / Swift 博客 / 开源库）和时间范围（7 / 30 / 90 天）筛选
- **版本发布**：Xcode、iOS、iPadOS、macOS、watchOS、tvOS、visionOS 当前正式版 + 进行中的 Beta / RC，下方是按日期分组的发布时间线
- **开源库**：每个关注的库一张卡片，显示最新版本、发布日期、更新说明和历史版本；7 天内发版的卡片高亮，两年以上没发版的标注「长期未发版」
- **Swift 提案**：Swift Evolution 中审核中 / 预览中 / 已接受 / 退回修改的提案，加上最近实现的 30 个
- **右侧挂件**：当前版本速览、30 天内的库更新、各来源抓取状态
- **右上角**：↻ 重新读取数据，⚡ 跳转 GitHub Actions 手动触发抓取，☾ 切换深浅色
- 全文搜索（`⌘K` / `Ctrl K`），手机适配

---

## 技术架构

```
GitHub Actions（每 6 小时第 23 分 / 手动 dispatch / 修改 scraper.py 或 workflow 后 push）
  ↓ python scraper.py（只用标准库，无需安装依赖）
  ↓ 线程池并发（8 线程）：Apple 版本发布 RSS / Apple 开发者新闻 RSS / Swift 博客 Atom / Swift Evolution JSON / 12 个 GitHub 库 releases.atom
  ↓ 失败来源沿用上一份 → 与上一份 data.json 按 URL 合并去重（保留 first_seen，最多 500 条）
  ↓ 写入 data.json 并 commit
       ↓
GitHub Pages（index.html）
  ↓ 前端读取同目录 data.json（每 10 分钟重读）
  ↓ 动态流 / 版本发布 / 开源库 / Swift 提案四个视图
  ↓ kit 详情抽屉（#/item/post|ver|lib|se/…）+ 列表页（#/list/feed、releases、evolution）
```

- 不用数据库，历史条目随每次运行累积在 `data.json` 里
- 某个来源本次抓取失败时沿用上一次的数据，页面上标注「旧数据」

---

## 数据来源

| 来源 | 方式 | 每次条数 | 备注 |
|------|------|---------|------|
| [Apple Developer Releases](https://developer.apple.com/news/releases/) | RSS：`releases.rss` | 全部（不设上限，实测 42） | Xcode / iOS / macOS 等 Beta、RC、正式版；`content:encoded` 里的发布说明 / 下载链接存进 `links` |
| [Apple Developer News](https://developer.apple.com/news/) | RSS：`news.rss` | 60（`apple_news(limit=60)`） | 政策、审核规则、活动 |
| [Swift.org Blog](https://www.swift.org/blog/) | Atom：`swift.org/atom.xml` | 全部（不设上限，实测 20） | swift.org 总返回 gzip，`fetch()` 按魔数自行解压 |
| [Swift Evolution](https://www.swift.org/swift-evolution/) | 接口：`download.swift.org/swift-evolution/v1/evolution.json` | 进行中的全部 + 最近实现 30 个（`EVO_DONE_KEEP = 30`，实测共 84） | 提案状态、目标版本、审查起止、作者、审查经理、论坛讨论 |
| GitHub 开源库发布 | Atom：`github.com/<repo>/releases.atom`，为空时改读 `tags.atom` | 12 个库 × 最近 5 个版本（`LIB_KEEP = 5`） | Masonry、YYKit、Lottie、IGListKit、JXCategoryView、JXPagingView、MJRefresh、IQKeyboardManager、AFNetworking、SDWebImage、Alamofire、SnapKit |

**增删来源**：
- 关注的库：`scraper.py` 开头的 `LIBS` 列表，每项 `(GitHub 仓库, 展示名)`，增删直接改这一处
- 其它来源：`SOURCES` 列表，每项 `(id, 名称, 头像缩写, 主题色, 抓取函数)`；抓取函数返回 `item(...)` 列表
- Swift Evolution 展示哪些状态：`EVO_ACTIVE` 字典

---

## 数据处理规则

- **统一条目** `item()`：`id` 直接用 URL；标题截断 160 字、列表摘要 200 字；详情用的长文本另存 `body`（库 1500 / 博客 600 / 新闻 800 字，`BODY_LIB` / `BODY_BLOG` / `BODY_NEWS`），只有比摘要长时才存
- **版本解析** `parse_release()`：标题如 `Xcode 27.2 RC (27B48)` 拆成 `platform` / `version` / `stage` / `build`；平台限 `PLATFORMS`（Xcode、iOS、iPadOS、macOS、watchOS、tvOS、visionOS），匹配不上记「其他」；阶段统一成 `Beta N` / `RC` / `正式版`
- **库版本** `lib_releases()`：版本号取 Atom `id` 最后一段；标题去掉重复的版本号前缀（如 "Release v6.0.0"）只留说明；GitHub 空说明占位 "No content." 置空
- **Swift Evolution** `swift_evolution()`：`EVO_ACTIVE`（审核中 activeReview / 已接受 accepted / 预览中 previewing / 退回修改 returnedForRevision / 待审核 scheduledForReview）全部保留，`implemented` 只留编号最大的 30 个，均按编号倒序
- **合并去重**：上一份 `items` 与本次新抓按 `id`（URL）合并，同一 id 以新抓到的为准，但保留最早的 `first_seen`；按 `date` 倒序截到 `MAX_ITEMS = 500`
- **容错**：普通来源失败时保留上次成功的 `updated`（页面据此标「旧数据」）；单个库失败时沿用上一份该库数据并标 `stale: true`；Evolution 失败时沿用上一份 `evolution`
- **前端阈值**：7 天内的条目标「新」（`NEW_DAYS = 7`）；两年以上（730 天）没发版的库标「长期未发版」；时间范围筛选 7 / 30 / 90 天

---

## 数据结构

**data.json** 顶层：

```
{
  "updated":   "2026-10-22T13:01:37+08:00",    北京时间，每次运行都变
  "sources":   [来源状态, …],                    5 个：apple-releases / apple-news / swift-blog / libs / swift-evolution
  "items":     [动态, …],                        最多 500 条，按 date 倒序
  "libs":      [库, …],                          12 个，按最新发版日期倒序
  "evolution": [提案, …]
}
```

来源状态：

```
{ "id": "apple-releases", "name": "Apple 版本发布", "abbr": "A", "color": "#0a84ff",
  "ok": true, "error": "", "count": 42, "updated": "2026-10-22T13:01:37+08:00" }
```

单条动态（`kind` 决定附加字段）：

```
{
  "id": "URL", "source": "apple-releases | apple-news | swift-blog | libs",
  "kind": "release | news | blog | lib",
  "title": "…", "url": "…", "date": "ISO 时间", "summary": "…", "body": "…（可选）",
  "first_seen": "本站首次收录时间",
  release 附加： "platform", "version", "stage", "build", "links": [{ "text", "url" }]
  lib 附加：     "lib", "repo", "version"
}
```

库：

```
{
  "repo": "Alamofire/Alamofire", "name": "Alamofire", "ok": true, "stale": false,
  "version": "5.12.2", "date": "…", "url": "…", "summary": "…", "body": "…",
  "history": [{ "version", "date", "url" }, …]        最近 5 个
}
```

提案：

```
{
  "id": "SE-0559", "title": "…", "state": "activeReview", "version": "", "start": "…", "end": "…",
  "url": "GitHub 提案原文", "summary": "…", "authors": [], "review_manager": [],
  "discussions": [{ "name": "pitch | review …", "url": "…" }]
}
```

没有单独的历史文件：动态流本身就是累积的历史（上限 500 条），每条带 `first_seen`；完整快照在 git 提交记录里。

---

## 前端

**kit 详情抽屉 / 列表页**：点任意条目，电脑上从右侧滑出详情抽屉，手机上从底部升起；地址同步成 `#/item/<类型>/<id>`，列表页是 `#/list/<key>`。地址可以直接分享，打开分享链接会直接弹出详情；条目已过期（被挤出 500 条）或不在当前数据里时，弹出「这条内容已不在当前数据里」的提示。

| 类型 | 地址 | 内容 |
|------|------|------|
| 动态 | `#/item/post/<URL 哈希>` | 版本发布：平台 / 版本号 / 阶段 / Build / 发布日期 / 本站收录、Apple 官方链接、同平台其它版本；开源库：Release Notes、同库其它版本；新闻 / 博客：摘要、同来源最近动态 |
| 平台最新版 | `#/item/ver/<平台>`（如 `#/item/ver/iOS`） | 该平台最新正式版，没有就取最新预览版 |
| 开源库 | `#/item/lib/<库名>` | 最新版本、Release Notes、历史版本、「7 天内发版」/「长期未发版」标签 |
| Swift 提案 | `#/item/se/<SE-xxxx>` | 编号、状态、目标版本、审查起止、作者、审查经理、摘要、论坛讨论、同状态提案 |

| 列表 key | 参数 |
|----------|------|
| `feed` 全部动态 | `kind`：release / news / blog / lib |
| `releases` 版本发布时间线 | `p`：平台名 |
| `evolution` Swift 提案 | `state`：activeReview / scheduledForReview / previewing / accepted / returnedForRevision / implemented |

**本项目特有**：
- 四个视图（动态流 / 版本发布 / 开源库 / Swift 提案），分类 + 时间范围筛选，视图、时间范围、主题存 `localStorage`（前缀 `idp.`）
- 版本发布页：七个平台当前正式版 + 进行中的 Beta / RC 速览，下方按日期分组的时间线
- 右侧挂件：当前版本速览、30 天内的库更新、各来源抓取状态
- 右上角 ⚡ 直接跳到 GitHub Actions 的 `scrape.yml` 页面手动触发抓取
- `⌘K` 搜索；每 10 分钟自动重读 `data.json`

---

## 本地运行

```
python3 scraper.py                 # 抓取一次，生成 data.json
python3 -m http.server 8000        # 浏览器打开 http://localhost:8000
```

- 依赖：只用 Python 标准库（workflow 用 Python 3.12），无需 `pip install`
- 环境变量：无（GitHub Atom 走公开地址，不需要 token）
- 直接双击 `index.html`（file://）读不到 `data.json`，必须通过 HTTP 服务打开

---

## 自动更新机制

| 触发方式 | 时机 |
|---------|------|
| GitHub Actions 定时任务 | `cron: '23 */6 * * *'` = UTC 00/06/12/18 点第 23 分 = **北京时间 08:23 / 14:23 / 20:23 / 02:23**（高峰期可能延迟） |
| 修改爬虫后 push | push 到 main 且改动了 `scraper.py` 或 `.github/workflows/scrape.yml` 时，约 1-2 分钟后触发 |
| GitHub Actions 手动 dispatch | 按需触发（页面右上角 ⚡ 或 Actions → iOS Dev News Scraper → Run workflow） |
| 页面自动刷新 | 已打开的页面每 10 分钟重读 `data.json`，也可点右上角 ↻ |

- **心跳**：没有单独的 `last_*.txt`；`data.json` 的 `updated` 每次运行都变，所以每次运行都会产生 `data: update …` 提交
- **60 天停用**：仓库 60 天没有提交时 GitHub 会自动停用定时任务（需在 Actions 页面重新启用）；正常每 6 小时一次提交，仓库保持活跃，不会被停用；一旦被停用就不再有新提交，需手动启用
