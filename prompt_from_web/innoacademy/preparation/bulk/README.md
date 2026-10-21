# 网站原图批量恢复与筛选

本轮覆盖 manifest 中全部 6,584 个 URL。仅下载、校验、整理和筛选，不运行图片描述模型，不写入 Chroma。此前试做的 20 张分工、描述及抽查报告保持不变。

2026-10-18 本地校验结果：6,520 个 URL 对应缓存有效，默认补下载队列只有 5 个临时失败链接，59 个记录暂缓。普通终端执行这些命令不调用模型 API，不需要聊天代理持续监控。两次运行之间如果文件发生变化，以最新 plan 输出为准。

## 查看结果

- `summary.json`：下载和筛选数量；只在筛选完成后生成。
- `report.md`：便于阅读的最终统计、分类、候选图片链接及失败清单。
- `recovery.json`：每个 URL 的当前状态、文件路径、实际/历史哈希、下载时间、失败类型与 HTTP 状态。
- `download_plan.json`：最近一次离线校验后的跳过名单、真正待下载列表和暂缓原因。
- `pair_reviews.json`：人工视觉复核的相似候选；结论绑定双方文件哈希，文件变化后不盲目复用。
- `screening.json`：按当前字节哈希合并后的图片记录，保留全部来源 ID；包含完全重复分组和近似候选对。
- `similarity_groups.json`：近似候选的连通分组及建议优先查看的高分辨率图片。连通关系不能证明组内图片完全相同，仍需核查。
- `description_queue.json`：未描述、无已知版本变化、非近似重复待查、格式正常且非低优先级的候选，按启发式优先级排序；不是已生成描述。
- `fingerprints.json`：按内容哈希缓存的尺寸、帧数和视觉指纹。

所有原图在 `submission_repo/data/web_academy/recovered/`，采用 SHA-256 文件名；相同字节共用一份文件，不丢弃来源网址。原图和过程日志不进入 Git，搬迁 worktree 前应单独备份。

## 筛选状态

| 状态 | 含义 |
|---|---|
| `ready_for_description` | 可进入下一轮描述的候选，尚未调用模型 |
| `near_duplicate_review_needed` | 与其他图片相似，需辨别缩略图、裁剪、不同角度或相似模板 |
| `version_review_needed` | 当前哈希与至少一个对应 URL 的历史哈希不同，需核查压缩变化或内容更新 |
| `low_priority_candidate` | 文件名/尺寸提示 logo、页眉、小图等；启发式判断，未删除 |
| `already_reviewed` / `pilot_described` | 已有相同哈希的正式描述或试做描述 |
| `exact_local_duplicate` | 与现场图片字节完全一致 |
| `format_or_size_review_needed` | 格式不支持、解码失败或超大图需要专项处理 |
| `animated_image_review_needed` | 多帧图片需逐帧检查，不能只根据第一帧描述全部内容 |

完全重复以实际下载文件 SHA-256 为准。视觉相似使用 64 位 dHash、距离不超过 8、长宽比接近；仅生成候选，不自动删除或认定语义相同。算法可能遗漏大幅裁剪、旋转或其他变换，也可能把相似模板误报，因此“未发现近似候选”不是独立性的保证。

## 运行和恢复

在 image worktree 的 submission_repo 中：

```powershell
# 第一步只扫描和核验本地文件，不访问网络
python -m build.bulk_web_images plan

# 第二步重新核验缓存，仅补下载缺失、损坏或临时失败项
python -m build.bulk_web_images download --workers 4

# 可选：下载结束后进行本地去重筛选
python -m build.bulk_web_images screen
```

下载前核对缓存文件的实际哈希，复用有效缓存；失败或缺失的文件可重跑恢复。每条下载写入进度日志，每 100 条保存状态；中断后重跑会继续。使用原有 requests 重试策略、最多 4 个并发连接，并遵循目标站 robots.txt。站外引用不自动扩展下载，单文件超过 300 MB 暂缓。

默认跳过 403、404、410、非图片响应及超限等确定性失败，避免每次重复请求。确认网站恢复后，可使用 `python -m build.bulk_web_images download --retry-all` 将这些记录重新列入，但站外引用仍不下载。`retry` 只处理临时失败；`download --dry-run` 等同于只查看计划。缓存有效的图片即使使用 --retry-all 也仍然跳过。

脚本使用进程锁，避免两个实例同时下载相同文件或写入同一份状态。进程退出后锁自动释放，不需要手动删除 lock 文件。不要同时启动多个下载/筛选窗口。

筛选只需本地文件，不调用 API。超过 8,000 万像素的图片保留原图，暂缓指纹解码；解码错误单独记录。需要先按上一层 README 安装隔离的 Pillow/HEIF 工具。

后续描述须按这些分类再选择批次；历史 hash 变化与近似候选不能直接套用已有描述。此处的筛选不覆盖既有试做报告，也不修改原始 manifest 的历史状态。
