# InnoWing 网站来源清单（爬取前评估）

核查日期：2026-09-23

目的：先确定未来 RAG 数据库的候选来源，不在本阶段批量抓取网页或建立索引。

## 比赛允许的知识边界

[Challenge Rules](https://innoacademy.engg.hku.hk/aichallenge/) 明确只允许以下知识来源：

1. Tam Wing Fan Innovation Wing **One** websites；
2. Innovation Academy websites；
3. 五个指定现场区域：入口附近照片墙、Makerspace A、Brainstorming area、Open event area、Digital Learning Studio。

因此正式比赛语料应限定在前两个网站和之后的现场采集。Wing Two、HKU 新闻、HKU Giving 等资料虽属官方来源，但只适合作背景核验，不应默认写入正式索引。规则同时说明比赛知识在比赛期间是静态的，团队须预先准备 corpus，不能依赖现场网页搜索。

## 建议优先级

| 优先级 | 来源 | 建议范围 | 主要内容 | 对 Benchmark 的价值 |
|---|---|---|---|---|
| P0 | [Innovation Academy](https://innoacademy.engg.hku.hk/) | 全站，但排除后台、作者页及低价值附件页 | 项目、Inno Show、课程、Workshop、Sharing、Pitching、Study Tour、新闻与活动 | 题目明确说明文本检索来自 Innovation Academy；也是视觉题与聚合题最可能的主来源 |
| P0 | [Innovation Wing One](https://innowings.engg.hku.hk/innowing1/) | 核心页面、设备、导师、SIG、活动档案、联络/到访信息 | 场地、设备参数与使用要求、人员、学生团队、活动及位置 | 补齐一般知识、精确文本、设备图片、计数/比较以及接近现场知识的信息 |
| P1 | Wing One 场地详情页 | Makerspace、Brainstorming、Open Event Area、Digital Learning Studio 等 | 场地用途、布局、附近设施、图片 | 与指定现场区直接相关，可辅助规划实地采集，但不能代替现场证据 |
| 背景核验 | [Innovation Wing Two](https://innowings.engg.hku.hk/innowing-two/) | 不进入正式比赛语料 | Wing Two 的研究展览、讲座与主题 | 规则只允许 Wing **One**；避免越界混入 |
| 背景核验 | [HKU Faculty of Engineering：News & Events](https://engg.hku.hk/News-Events) | 不进入正式比赛语料 | 开幕、专题报道、比赛成绩、活动新闻 | 可人工核验历史，但不是规则列出的来源 |
| 背景核验 | [HKU Giving：Tam Wing Fan Innovation Wing](https://www.giving.hku.hk/named-building/tam-wing-fan-innovation-wing) | 不进入正式比赛语料 | 捐赠人、命名、面积、楼层、设施概览和照片 | 权威背景补充，但不是规则列出的来源 |
| 背景核验 | [HKU Lead：2018 捐赠与愿景](https://lead.hku.hk/en/article/2018/02/tam-wing-fan-innovation-wing-a-gift-to-the-young-generation/) | 不进入正式比赛语料 | HK$100 million 捐赠、命名缘由与愿景 | 权威背景补充，但不是规则列出的来源 |
| 背景核验 | [HKU Lead：2020 maker space 介绍](https://lead.hku.hk/en/article/2020/07/hku-engineering-s-brand-new-maker-space-for-studentstam-wing-fan-innovation-wing-one-of-the-largest-maker-spaces-in-asia/) | 不进入正式比赛语料 | 2,400 m²、G/F 与 LG/F、设施和空间布局 | 权威背景补充，但不是规则列出的来源 |

## P0：Innovation Academy 建议栏目

- [About us](https://innoacademy.engg.hku.hk/aboutus/)：组织使命、负责人、地址和联系方式。
- [Equipment / facilities](https://innoacademy.engg.hku.hk/equipment/)：设备型号、规格、权限、预约和监督要求；含大量图片与 Google Calendar iframe。此页可能是旧版设备清单，宜与 Wing One 当前设备页同时保留并记录抓取日期。
- [Student Development Projects](https://innoacademy.engg.hku.hk/sharing/projects/) 与 [SRA Projects](https://innoacademy.engg.hku.hk/sra-projects/)：项目名称、合作机构和简介，适合表格级检索与计数。
- [Inno Show and Carnivals](https://innoacademy.engg.hku.hk/innoshow/)：历届入口和项目档案；项目正文可按届次与类别保留元数据。例如 [第 10 届归档](https://innoacademy.engg.hku.hk/category/engineering-innoshow/the-10th-engineering-inno-show/)。
- [SIG Projects](https://innoacademy.engg.hku.hk/category/sig-projects/) 与 [SRA 项目类别](https://innoacademy.engg.hku.hk/category/sra-projects/)：学生团队、项目、奖项、海报、视频和图片，是文本、视觉及聚合题的重要来源。
- [Sharing](https://innoacademy.engg.hku.hk/sharing/)、[Workshop](https://innoacademy.engg.hku.hk/workshop/)、[Pitching](https://innoacademy.engg.hku.hk/pitching/)、[Student-initiated courses](https://innoacademy.engg.hku.hk/sic/) 与 [Study Tour](https://innoacademy.engg.hku.hk/studytour/)：活动介绍、历届条目、课程要求和相册。
- [Funding Scheme](https://innoacademy.engg.hku.hk/funding-scheme/)：申请资格、资助上限、报告及分享要求，适合精确数字问题。
- [Robot Arm Challenge 2026](https://innoacademy.engg.hku.hk/robotarm2026/)：挑战规则、timeline 与 leaderboard。
- [挑战主页](https://innoacademy.engg.hku.hk/aichallenge/)：规则来源及五级示例。示例显示 Level 2 可能问 Funding Scheme deadline、Level 3 可能问 Pitching 海报中的 winners、Level 4 可能统计某年份 workshop posters；这些只用于指导数据建模，不能视作私有题泄漏。

## P0/P1：Innovation Wing One 建议栏目

- [Wing One 设备与设施](https://innowings.engg.hku.hk/innowing1/equipment/)：比 Academy 的设备页更完整，包含 FDM/SLA 3D 打印机、3D 扫描、激光切割、机床、水刀、喷漆、CAD/CAM、VR 等设备及型号、尺寸、权限与预约规则。该页文字与图片都应入库，但分开保存原始图片和派生视觉描述。
- [Contact / directions / opening hours](https://innowings.engg.hku.hk/innowing1/contact/)：地址、从 HKU MTR A2 的路线、门禁和开放时间。开放时间会变化，必须保留抓取日期，回答时优先采用最新记录。
- [Membership](https://innowings.engg.hku.hk/innowing1/membership/) 与 [affiliated SIG](https://innowings.engg.hku.hk/innowing1/sig/)：入场资格和团队制度。
- [Tutor team](https://innowings.engg.hku.hk/tutor/)：人员、专业背景和可协助的设备/领域；遇到带学年的旧页面时，应保留年份元数据。
- [Job opportunities](https://innowings.engg.hku.hk/innowing1/job/)：SRA / tutor 招聘与项目机会。
- [Past events](https://innowings.engg.hku.hk/past-events/)：大型历史活动档案，适合按事件拆分，避免整页形成超长 chunk。
- 场地页：[Makerspace](https://innowings.engg.hku.hk/makerspace/)、[Brainstorming area](https://innowings.engg.hku.hk/brainstorming/)、[Open event / social area](https://innowings.engg.hku.hk/social/)、[Digital project studio](https://innowings.engg.hku.hk/digitalprojectstudio/)、[Event hall](https://innowings.engg.hku.hk/eventhall/)、[Machine shop](https://innowings.engg.hku.hk/machineshop/)、[Wet lab](https://innowings.engg.hku.hk/wet-lab/) 与 [VR room](https://innowings.engg.hku.hk/vr-room/)。这些页面可帮助建立空间词汇和实地采集清单；发现模板复制错误时必须以页面标题、canonical URL 和现场记录为准。
- 动态辅助页：[Schedule](https://innowings.engg.hku.hk/innowing1/schedule/) 多为 iframe，[Special arrangements](https://innowings.engg.hku.hk/innowing1/special/) 内容易变；建议登记链接和抓取时间，不把 iframe 空壳当正文。

## BeautifulSoup 前的技术判断

1. 两个核心站均为 WordPress，并提供官方 sitemap：
   - Innovation Academy：[robots.txt](https://innoacademy.engg.hku.hk/robots.txt)、[wp-sitemap.xml](https://innoacademy.engg.hku.hk/wp-sitemap.xml)
   - Innovation Wing：[robots.txt](https://innowings.engg.hku.hk/robots.txt)、[wp-sitemap.xml](https://innowings.engg.hku.hk/wp-sitemap.xml)
   - robots 目前只禁止 `/wp-admin/`，允许 `/wp-admin/admin-ajax.php`。仍应限速，并以每次运行时的 robots 内容为准。
2. 2026-09-23 的只读核查中，Academy sitemap 约列出 425 个 posts、241 个 pages、36 个 categories；Wing sitemap 约列出 543 个 posts、45 个 pages、41 个 categories。数量会变化，只应用来估算范围。
3. 主要正文由服务器直接返回，BeautifulSoup 可处理；不必先上浏览器渲染。应以 `main/article` 或 WordPress 内容容器为目标，移除导航、footer、cookie UI、重复轮播和 “Read More” 卡片文本。
4. 图片不能只取 `img.src`：同时检查 `srcset`、lazy-load 属性、`alt`、`figcaption`、链接到的原图以及 Open Graph image。视觉题可能依赖海报或照片内文字，需保存原图 URL、所在页面、顺序和说明文字，之后再做 OCR/VLM 描述。
5. 多页包含外部 iframe 或文件：Google Calendar/Docs/Drive、Dropbox、YouTube、Microsoft Forms 以及厂商规格页。第一轮建议只登记外链与类型，不自动跟随抓取；是否纳入应单独决定。
6. WordPress 的 page、post、category、author 页面高度重复。发现 URL 时以 sitemap 为主，canonical URL 去重；作者页、搜索页、分页归档和 taxonomy 页面通常只作发现入口，不当正文证据。
7. 聚合题需要结构化记录，至少保存 `title`、`url`、`canonical_url`、`content_type`、`section/category`、`event/project name`、`year/semester`、`date`、`people/team`、`equipment`、`image_id` 与页面内位置，不能只建立无元数据的纯文本 chunks。
8. 旧页面与新页面可能冲突，例如设备清单、开放时间和负责人会更新。不要覆盖旧事实；保存 `retrieved_at` 和页面标示的年份，以当前页面优先、历史页面用于时间限定问题。

## 与五级题型的覆盖关系

| 题型 | 首选来源 | 数据处理重点 |
|---|---|---|
| General Knowledge | Academy About、Wing One、HKU Lead / Giving | 保存简洁事实及同义名称（Inno Wing、Innovation Wing、Tam Wing Fan Innovation Wing） |
| Text Retrieval | Academy 全站 page/post | 保留标题、段落、列表与表格行；避免导航噪声 |
| Visual Retrieval | Academy 项目海报/相册、Inno Show、Wing 设备/展览图片 | 下载原图并记录上下文，后续 OCR + 视觉描述 |
| Aggregated Reasoning | Inno Show/SIG/SRA 类别、项目表、活动档案、设备清单 | 一项一条结构化记录，保留届次、年份和类别以支持可靠计数 |
| Physical World RAG | 入口照片墙、Makerspace A、Brainstorming area、Open event area、Digital Learning Studio | 网站不能替代现场观察；需现场拍摄标牌、布局、物件、颜色、数量和位置，并记录区域、方向与日期 |

## 建议的首轮选择

若目标是在控制规模的同时最大化 Benchmark 覆盖，建议首轮选择：

1. Innovation Academy sitemap 中的正式 `page` 与 `post`，优先 About、Equipment、Inno Show、SIG、SRA、Sharing、Workshop、Pitching、SIC、Study Tour。
2. Innovation Wing One 的 Equipment、Contact、Membership、Tutor、SIG、Past Events。
3. Wing One 场地详情页，尤其与五个指定现场区域对应的页面；将它们作为现场采集导航和辅助文字，而非现场证据的替代品。

暂不建议首轮自动跟随 Google Drive/Dropbox/YouTube/Calendar/表单和厂商网站；先保留外链清单，待确认版权、访问稳定性及实际题型价值后再决定。

Wing Two、HKU Lead、HKU Giving 和 Faculty 新闻不属于 Challenge Rules 列出的正式知识源，不进入比赛索引。
