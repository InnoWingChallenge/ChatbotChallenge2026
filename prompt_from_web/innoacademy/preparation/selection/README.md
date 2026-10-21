# 图片描述候选筛选

日常使用请先看 [目录导航与快捷审核说明](../../README.md)。直接打开 [图片筛选台](review.html)，可放大、按键判断、比较相似图、批量操作、撤销和导入/导出人工判断。下文保留处理流程与技术细节。

本轮仅筛选，不生成图片描述，不调用 embedding，不修改 Chroma，不删除原图。

## 范围与方法

- 输入为 `../bulk/screening.json` 中已按下载文件 SHA-256 合并的图片记录。
- 已有描述、试做描述以及既有现场照片单独保留在 `existing.json`，不重新消费视觉筛选额度。
- 脚本重新校验原图哈希；相同尺寸、EXIF 方向校正后的 RGBA 像素完全相同才自动合并。所有来源仍保留在输出记录中。透明图以白底合成预览。
- 分辨率只作为质量标记；不会单独因短边较小删除一张图片。AI 认为有价值但长边小于 400 像素时，转入人工复核。
- 格式异常、超大图、动画单独复核，避免只看首帧得出结论。
- GPT 6 Luna，reasoning effort 为 medium，通过带编号联系表查看图片。每张联系表最多 48 张，单格约 250 × 208 像素；另有长边最多 768 像素的单图预览可供查看。
- 这是内容价值初筛，不是完整分辨率 OCR 或文字可读性保证。无法判断的图片标记复核；保留图片在后续描述时仍需要检查原图。
- 视觉近似组、历史哈希变化不自动等于重复。此轮可能保留同内容的不同分辨率/裁剪版本，不能将 keep 数量称为独立事实数量。

## 分类

Luna 为每张候选图写一个筛选代码，不写图片描述：

| 代码 | 结果 | 理由 |
|---|---|---|
| T | keep | 海报、地图、标牌、信息图等文字资料 |
| E | keep | 设备、设施，可提供具体视觉事实 |
| S | keep | 空间布局 |
| P | keep | 项目、原型、演示 |
| D | defer | 普通活动、头像、合影、装饰，暂未发现明显独特信息 |
| R | review | 内容不确定，或预览不足以判断 |

`defer` 是暂缓，不是确认无用或永久删除。可通过审核页面抽查，特别注意活动照片中的设备与空间信息。

## 输出

- `keep.json`：适合进一步描述的候选图片及其来源。
- `review.json`：不确定、质量或格式问题，优先人工检查。
- `defer.json`：普通图片或像素完全重复的图片，保留理由和替代关系。
- `existing.json`：本轮未重新筛选的既有资料。
- `votes/`：Luna 的逐联系表判断，模型及推理档位记录。
- `summary.json`：覆盖率、数量及限制。
- `review.html`：交互审核页面，默认展示尚未人工判断的 review；支持按键、批量判断、相似图比较、浏览器暂存和 JSON 导入/导出。不会直接修改项目数据。使用 `python -m build.review_image_candidates apply --input 导出文件.json` 导入项目后生成 `human_reviews.json` 和 `reviewed_*.json`，原始 AI 结果保留。

预览图片位于被 Git 忽略的 `submission_repo/data/web_academy/selection_previews/`。JSON 中原图路径相对仓库，来源 URL 和 SHA-256 保留。联系表任务文件中的绝对路径只用于本机执行，移动仓库后应重新生成。

## 重建

在 image worktree 的 `submission_repo`，使用具备 Pillow 的 Python：

```powershell
python -m build.select_image_candidates prepare
# 由指定的 Luna medium 视觉代理读取 assignment-*.json 并逐张查看联系表，写入 votes。
python -m build.select_image_candidates finalize
```

prepare/finalize 都是本地脚本，不能代替中间的视觉查看。finalize 会拒绝缺失票据、长度错误、错误模型字段；不会把未查看的图片默认为已筛选。重新生成输入后，应使用新一轮 votes，不能盲目复用旧联系表序号。

本轮在初次预览之后补做了透明通道检查：135 张图片以白底重新生成了 3 张联系表，已完成 96 张，39 张因模型额度上限尚待重看。`alpha_assignment.json` 和对应 votes 保留这次修正；透明图片中另有 1 张已验证 RGBA 像素完全相同的重复图，无需重看。最终版 prepare 已直接处理透明通道，后续重新构建无需这一补充步骤。票据绑定图片 ID 列表和联系表 SHA-256，防止误用其他批次结果。

## 当前未完成事项与续跑

首轮 6,128 张候选全部由 Luna medium 查看。针对 16 张高优先级图片的单图放大抽查发现小拼图可能漏掉海报、获奖信息等文字内容；这不是随机样本，不能用于估算总体准确率。抽查记录中的 4 个初始代码已根据原始票据正规化结果校正，审计记录保留说明。

因此另将来源优先级 >= 4 且初判 D 的 349 张图片组成 22 张更大的联系表（每张最多 16 图、4 × 4），写入 `refine-0.json` 至 `refine-2.json`。这些补充任务未开始看图，不能当作已完成筛选。与剩余透明图有重合，合计 381 张不同图片等待补充视觉复核。

Luna 子代理返回 usage limit 后，本轮显式使用 `finalize --allow-pending` 输出中间结果：缺失的视觉票据进入 review，`summary.json` 中 `complete` 为 false，网页也显示未完成数量，不会伪造 inspected 标记。

`resume_assignment.json` 记录所有缺失联系表，续跑只需由 **GPT 6 Luna / medium** 完成其中的视觉查看并写 votes，不必重跑 prepare 或重看已有票据。每张任务带列数（透明图为 8 列，精查为 4 列），必须按编号顺序提交代码。票据必填 sheet、ids、sheet_sha256、model、reasoning_effort、codes、inspected。

补齐后运行：

```powershell
python -m build.select_image_candidates finalize
```

这条本地命令只汇总，不能自动调用 Luna 或补齐视觉判断。未补齐时会报错。继续生成明确标记的中间结果时才使用 `--allow-pending`。
