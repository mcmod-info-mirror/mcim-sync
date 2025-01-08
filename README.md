# mcim-sync

![mcim-sync](https://socialify.git.ci/mcmod-info-mirror/mcim-sync/image?description=1&font=Inter&issues=1&language=1&name=1&owner=1&pattern=Overlapping%20Hexagons&pulls=1&stargazers=1&theme=Auto)


此仓库用于确保 MCIM 的缓存不过时。

基本上可以保证及时处理所有任务，你可以在 Telegram 频道 [MCIM 同步进度](https://t.me/mcim_sync) 查看最新执行情况。

## 缓存思路

[mcim-api](https://github.com/mcmod-info-mirror/mcim-api) 会提供数个 redis 集合，所有不存在于数据库中的请求参数都会被添加进去，其中有的是真的新 Mod 未收录，大部分为无效请求参数而已

此任务将定时检查所有捕捉到的 `modId` `fileId` `fingerprint` `project_id` `version_id` `hash` 并同时转为对应的 `modId` 和 `project_id`，其后统一拉取。

这将保证 MCIM 可以及时捕捉到新 Mod。

---

同时会定时检查数据库内所有已缓存 Mod，以其 Modrinth Project 的 `updated` 字段或 Curseforge Mod 的 `dateModified` 为 Mod 有新版本需要拉取的根据，然后统一同步其版本列表。

这将保证 MCIM 可以及时捕捉 Mod 的新版本。

---

当前任务执行间隔如下
- 检查已有 Mod 信息：7200s
- 从队列中捕捉新 Mod: 3600s

缓存统计信息见 [mcim-statistics](https://mod.mcimirror.top/statistics)

```json5
// 2025-1-8
{
    "curseforge": {
        "mod": 99911,
        "file": 1067564,
        "fingerprint": 1438482
    },
    "modrinth": {
        "project": 47824,
        "version": 470865,
        "file": 522406
    },
    "file_cdn": {
        "file": 1050858
    }
}
```
