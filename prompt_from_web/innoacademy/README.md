# InnoAcademy 图片资料导航

这里保存网站图片的来源、下载进度、试做描述和筛选结果。**原图不在这个目录**，位于 `submission_repo/data/web_academy/recovered/`；预览图位于其旁边的 `selection_previews/`。

## 日常只需打开这三个入口

1. **[图片筛选台](preparation/selection/review.html)**：看图、比较相似图、批量保留或暂缓、记录人工判断。
2. **[当前筛选报告](preparation/selection/report.md)**：了解本轮结果和未完成事项。
3. **[当前状态](preparation/selection/summary.json)**：机器统计；`complete: false` 表示还有视觉复核未完成。

当前保留清单为 [selection/keep.json](preparation/selection/keep.json)。它是初筛候选，不是已经描述、入库或全部人工核验的图片。

## 更快地筛选图片

- **先看例外**：页面默认显示“待复核、尚未人工判断”。“等待 AI 的图片”单独显示尚未补完的视觉任务，你也可以自行判断。
- **连续看图**：点击缩略图进入放大模式；按 **1 保留、2 暂缓、3 待定**，自动进入下一张。方向键切换，Esc 关闭。需要读小字时点击“打开原图”。
- **批量处理**：勾选多张或“全选本页”，一次保留、暂缓或待定。选择可以跨页，页面会显示已选数量；误操作可撤销。
- **比较重复版本**：点击“比较相似图”，会按分辨率从高到低排列同组候选。保留清楚、完整的版本；文字、年份或设备细节不同的图不要直接当重复图。
- **抽查**：使用“抽查候选 / 抽查暂缓”，结合类型、来源网址搜索缩小范围。

判断暂存于当前浏览器；**关闭前请点击“导出人工判断”保存 JSON**。清理浏览器数据、换浏览器或移动页面后可能无法读取旧暂存，可用“导入之前的判断”恢复。任何操作都不会删除原图、调用模型或写入 Chroma。

网页导出不等于更新项目清单。导出后，可以把文件路径交给助手导入；也可以在 image worktree 的 `submission_repo` 运行：

```powershell
python -m build.review_image_candidates apply --input "你的下载目录\innowing-human-reviews.json"
```

导入后生成：

| 文件 | 用途 |
|---|---|
| `selection/human_reviews.json` | 人工判断记录，按图片 ID 和哈希验证 |
| `selection/reviewed_keep.json` | 在原始 AI 清单上应用人工修改后的候选 |
| `selection/reviewed_review.json` | 应用人工修改后仍待复核的图片 |
| `selection/reviewed_defer.json` | 应用人工修改后暂缓的图片 |

原始 `keep.json / review.json / defer.json` 和 AI 票据保留，人工操作可追溯。`reviewed_keep.json` 也可能包含尚未经人工查看的原始候选；带 `resolved_by_human: true` 的记录才表示人工明确判断过。

## 目录与 JSON 对照

| 位置 | 用途 | 是否日常查看 |
|---|---|---|
| 根目录 | 原始网站采集与图片来源 | 查来源时看 |
| `descriptions/` | 早期正式描述 | 描述和入库时使用 |
| `pilot_descriptions/` | 20 张试做描述 | 历史参考 |
| `preparation/` 根层 | 早期小批量恢复和 Sol/Luna 试验 | 通常不用 |
| `preparation/bulk/` | 全量下载、文件校验和脚本去重 | 查下载问题时看 |
| `preparation/selection/` | 当前 Luna medium 筛选、人工审核及续跑 | **主要使用这里** |

### 原始采集

- `manifest.json`：6,584 条图片 URL 的来源总清单，包括出现在哪些网页和历史下载信息。
- `pages.json`：668 个网页的标题、正文、图片与页面信息；`discovered_pages.json` 是网页地址列表。
- `manual_reviews.json`：早期图片审阅记录。
- `failures.json / status.json / vision_access.json`：早期错误、采集统计和视觉接口测试记录，不代表当前状态。

### 下载与脚本去重：`preparation/bulk/`

- `recovery.json`：各 URL 的下载状态、文件路径、哈希和错误。
- `download_plan.json`：哪些文件能复用、哪些需要重试、哪些暂缓。
- `fingerprints.json`：尺寸、帧数、视觉指纹缓存；`screening.json` 是脚本筛选结果。
- `similarity_groups.json / pair_reviews.json`：相似候选组与复核记录。相似不代表同一张图。
- `description_queue.json`：**AI 筛选之前的旧候选队列**，后续请优先看 selection 的清单。
- `summary.json`：下载与脚本去重阶段的汇总，不是最新内容筛选汇总。

### 当前筛选：`preparation/selection/`

- `keep / review / defer / existing.json`：候选、待复核、暂缓、既有资料四份清单。
- `decisions.json`：四份清单的完整合并记录；`assets.json` 是本轮输入和预览资料。
- `sheets.json / assignment-*.json / votes/`：拼图内容、代理任务、逐拼图 AI 判断。票据多是为了断点续跑，不必逐个读。
- `alpha_assignment.json / transparency_check.json`：透明背景图片检查。
- `audit.json / refine-*.json`：放大抽查及针对性复核任务。
- `resume_assignment.json`：本轮已生成的缺失任务快照。续跑时以实际缺失票据为准。
- [技术说明](preparation/selection/README.md)：分类代码、模型、边界和复核细节。

### 历史试验：`preparation/` 根层

`inventory / recovery / similarity / exact_duplicates` 是当时的盘点、恢复与去重；`pilot_batch / sol_batch / luna_batch` 是试做任务；`sol_descriptions / luna_descriptions / pilot_reviews / quality_review` 是试做描述及检查。文件同名时请先看所在目录，避免把试验阶段统计当成当前进度。

暂不移动或删除历史文件，已有脚本仍通过这些路径读取资料。整理以导航和入口为主。
