# mcim sync

定时刷新过期的数据

1. 从数据库中读取所有的数据，列出所有的 Mod 和 Project

2. 遍历所有的数据，判断是否过期

3. 如果过期，更新数据；如果未过期，跳过

Tips:

为了避免过多的请求，在检测到 Curseforge 403 时，暂停请求 5 分钟；根据 Modrinth API 的 headers，可以判断是否需要暂停

先更新 Mod 的 latestFiles，然后再从数据库中获取对应 Mod 的 latestFiles 给 Fingerprint

当前定时刷新间隔为 7200 s