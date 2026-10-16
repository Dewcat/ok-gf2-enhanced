# 增强仓自动发布

`Auto Release` 每天北京时间 00:00 检查默认分支。GitHub 定时任务可能延迟。
也可在 Actions 中手动运行，勾选 `dry_run` 只查看计划，不创建 tag、不构建。

- 以默认分支可达的最新正式版本 tag 为基准，增强仓独立递增版本；patch 到 99 后进位。
- `deploy.txt` 中的运行文件，以及打包 action、构建 workflow、启动器选择脚本、图标和 setup.py 的变化触发发布。
- Markdown、RST、AsciiDoc 文档及 `assets/downloads.svg` 不触发发布。
- 新 tag 指向检查时的默认分支 HEAD，显式在该 tag 上启动 `Build fork release`。
- 构建运行测试，生成完整和在线安装包、更新 ZIP、启动器清单及校验值，然后发布 Release。
- Release 说明保留下载提示，具体改动由 GitHub 自动生成。
- 最新正式 tag 缺少完整 Release 附件时，优先重新构建同一 tag；已有构建运行中则跳过。
- API 查询失败时终止，不将网络或权限错误当作需要发布。

失败后可重跑 `Auto Release`，或在对应 tag 上手动运行 `Build fork release`。
重试使用原 tag 的代码；若失败需要修改代码才能修复，应修复后人工处理该失败版本，不能靠重试引入后续提交。
流程使用仓库内置 `GITHUB_TOKEN`，需要 Actions 获准写入 contents 和 actions，无需额外 PAT。
