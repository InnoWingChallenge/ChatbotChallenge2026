# 第二轮图片验收

本轮只修复输出格式，没有更换 embedding、调整检索或重建数据库。`bot/answer.py` 在返回答案前将换行等空白归一化为单个空格；保留 `main.py`。已用模拟模型输出检查 CRLF、Unicode 换行及实际 main 入口的多题行数与顺序。

新增 `image_holdout_v1.json` 和便于人工阅读的 `image_holdout_questions.md`：24 题，包括中文、同义改写、无文件名提示、相似房间/奖项区分、多事实汇总、证据不足和日期来源辨别。16 题重组或改写第一批事实，8 题涉及第一批未考过的事实或证据边界；它不是独立图片数据集。

题集在首次在线运行前冻结，仅检查金标准摘录是否存在，不用这些题调参，也不把题目或答案入库。原图人工核验仍待完成。若今后根据这些题调参，应另留新的验收题，不再称它们为未见题。

在 image worktree 的 submission_repo 中激活环境、连接 VPN 并确认配置后运行：

```powershell
# 先复测之前出现两行输出的题
python -m eval.check_images --mode answers --ids image_007 --output eval/image_runs/format-fix-01

# 新题集完整问答（24 题，调用线上 API）
python -m eval.check_images --dataset eval/image_holdout_v1.json --mode answers --output eval/image_runs/holdout-v1-answers-01
```

每个输出目录保存 report.json 和 report.md；使用新的目录名以保留历次报告。参考答案支持中英文等价表述，只有题目明确要求解释时才因缺少解释扣分。正确内容与单行输出约束分别检查。首次验收后如有错题，可使用相同 `--dataset` 加 `--mode hybrid --ids ...` 检查候选证据；hybrid 模式调用 embedding，不含最终 LLM 重排，不能把候选命中直接等同于生成上下文命中。

依据 AGENTS.md，线上调用由用户连接 VPN 后执行；本轮只执行离线测试，未复跑在线答案。原有 answers-01 报告及已生成 Chroma 保留不变。

## 后续图片工作：待确认后开始

2026-10-17 仅核查现有 manifest/manual_reviews，没有打开剩余图片进行描述、没有下载或入库。网站清单有 6,584 个 URL；按内容哈希有 4,806 张已下载的唯一图片，其中 24 张已完成直接描述，余下 4,782 张有哈希但未完成描述。另有 1,684 个待下载 URL、38 个下载失败 URL、8 个外部引用；URL 数不能当成唯一图片数。

manual_reviews 是已完成状态的依据；manifest 中 description_status 尚未同步完成记录，不能直接把其中 pending 数当作剩余唯一图片数。当前主/image 两个 worktree 的清单指定原图路径均未找到这 4,782 张原图，需要先定位已有下载目录或确认是否重新下载。历史 downloaded 标记不代表文件现在仍在本机路径中。

建议先选 20 张有价值的海报、设备、标牌或活动照片试做，跳过重复页眉/logo；用 gpt-6-sol 子代理描述，抽查 OCR、数量、空间关系及不确定性，再考虑让 gpt-6-luna 批量处理简单图片。模型可显式指定，实际额度/计费没有在此环境验证，不承诺固定节省比例。用户确认批量范围、模型和原图来源后才启动；本轮未启动图片子代理。
