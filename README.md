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

## 数据来源

| 来源 | 内容 |
|---|---|
| [Apple Developer Releases](https://developer.apple.com/news/releases/) | Xcode / iOS / macOS 等 Beta、RC、正式版 |
| [Apple Developer News](https://developer.apple.com/news/) | 政策、审核规则、活动 |
| [Swift.org Blog](https://www.swift.org/blog/) | Swift 官方文章 |
| [Swift Evolution](https://www.swift.org/swift-evolution/) | 提案及状态 |
| GitHub `releases.atom` | 关注的开源库发布（没有 Release 的库自动改读 `tags.atom`） |

关注的库在 `scraper.py` 开头的 `LIBS` 列表里，增删直接改这一处。

---

## 技术架构

```
GitHub Actions（每 6 小时 / 手动 / 修改爬虫后 push）
  ↓ python scraper.py（只用标准库，无需安装依赖）
  ↓ 并发抓取 5 类来源 → 与上一份 data.json 合并去重（最多保留 500 条）
  ↓ 写入 data.json 并 commit
       ↓
GitHub Pages（index.html）
  ↓ 前端读取同目录 data.json 渲染
```

- 不用数据库，历史条目随每次运行慢慢累积在 `data.json` 里
- 某个来源本次抓取失败时沿用上一次的数据，页面上标注「旧数据」
- `data.json` 里的更新时间每次都变，所以每次运行都会产生提交，仓库保持活跃，定时任务不会因 60 天无活动被 GitHub 停用

本地预览：

```
python3 scraper.py
python3 -m http.server
```
