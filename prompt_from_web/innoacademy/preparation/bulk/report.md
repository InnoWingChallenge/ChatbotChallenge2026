# 网站图片批量下载与筛选结果

仅下载和本地筛选；未生成新描述，未修改数据库。

```json
{
  "completed_at": "2026-10-18T12:22:34.070141+00:00",
  "url_records": 6584,
  "unattempted_url_records": 0,
  "download_status": {
    "recovered": 6520,
    "external_reference": 8,
    "failed": 52,
    "non_image": 4
  },
  "unique_downloaded_hashes": 6287,
  "unique_downloaded_bytes": 4621762889,
  "local_photos_checked": 119,
  "screening": {
    "existing_local_photo": 119,
    "near_duplicate_review_needed": 1532,
    "ready_for_description": 3328,
    "version_review_needed": 1232,
    "low_priority_candidate": 135,
    "already_reviewed": 20,
    "format_or_size_review_needed": 4,
    "animated_image_review_needed": 16,
    "pilot_described": 20
  },
  "exact_duplicate_groups": 157,
  "raw_near_duplicate_candidates": 1533,
  "visually_rejected_pairs": 1,
  "near_duplicate_pairs": 1532,
  "cross_source_near_pairs": 0,
  "near_duplicate_candidate_groups": 805,
  "new_descriptions_generated": 0,
  "database_modified": false
}
```

## 筛选分类

| 类别 | 唯一图片数 |
|---|---:|
| already_reviewed | 20 |
| animated_image_review_needed | 16 |
| existing_local_photo | 119 |
| format_or_size_review_needed | 4 |
| low_priority_candidate | 135 |
| near_duplicate_review_needed | 1532 |
| pilot_described | 20 |
| ready_for_description | 3328 |
| version_review_needed | 1232 |

完全重复按实际文件哈希分组，保留所有来源。近似分组仅供核查，未删除原图。

## 待描述队列前 30 张

这里只是规则筛选结果，不代表已经核验图片内容。

| 图片 ID | 优先级依据 | 原图 |
|---|---|---|
| d5b1ccdc75632671ce67073c | poster, innoshow | [打开](../../../../submission_repo/data/web_academy/recovered/70b79c1596417b9ca61de5705b99eb075db720ade62f36d852505d4cc746dc68.jpg) |
| 3d54b77b15bd2d92cf7dd1b7 | poster, innoshow | [打开](../../../../submission_repo/data/web_academy/recovered/4bcb0a6cf31735ddc89362d578f3aae0e7be1c8ce98e2432651d8e3c54de8e44.jpg) |
| 5508d0a26b00b89f2017c30a | poster, innoshow | [打开](../../../../submission_repo/data/web_academy/recovered/134e2d7dc35faff34f16c7892223b76ad8c37a02326bc7f9e068a5bbb61dceda.jpg) |
| f77f5074295b8f00260a3341 | machine, robot | [打开](../../../../submission_repo/data/web_academy/recovered/5bf8d1a187cff5a842d604f157012186ae033c4b9dfd6cdb648b757b773fa918.jpg) |
| b24256e8742f6854505da446 | poster, innoshow | [打开](../../../../submission_repo/data/web_academy/recovered/da3fd6f8e96fc62e2772165cabc54bc858a2f87d7f4a3a0a40581c4e1b6d707e.png) |
| 66bae88cda03ed57b4aa58b6 | poster, innoshow | [打开](../../../../submission_repo/data/web_academy/recovered/d39242ef616a81b21f935762fa9259b85761278b020d2e5c60689bb8397e1137.jpg) |
| 87dd45d74075101fccf35d9c | poster, innoshow | [打开](../../../../submission_repo/data/web_academy/recovered/df2be1421e0d517fe2281ff0345b459fb7fdce4e56ce9f15ea4f68d14f877657.jpg) |
| aa160fe99cf1aaccc353e331 | poster, innoshow | [打开](../../../../submission_repo/data/web_academy/recovered/5fda714d99c134598b58e1af49f9fd55a48cd45e6a55e383a00c872ddaedd026.jpg) |
| fdd95f9c7ccc2383429d58bf | poster, innoshow | [打开](../../../../submission_repo/data/web_academy/recovered/578703ddd023788d636cf49ee87fa4baab8167a181b2f6755f019684a3bdcb5f.jpg) |
| fbd84b9034e396b9082ecc94 | poster, innoshow | [打开](../../../../submission_repo/data/web_academy/recovered/2533cdef4438bdd7d84e387ada256925c3e83f7515ab2a7c7ed4f6c92067cb59.jpg) |
| e39ad0c49a4d3bc1aeb4aed3 | poster, innoshow | [打开](../../../../submission_repo/data/web_academy/recovered/63d056c04ebcb906a28aab877852faf46f4e970d8cbfc624a61c3f76d988d81a.jpg) |
| c7ae434f71e385b0d6e1e696 | poster, innoshow | [打开](../../../../submission_repo/data/web_academy/recovered/9ccbd9cbe40b4e9112abf6639f26c1ff18b351147df8cbe34b8a3b2f18fbbf6f.png) |
| e3075a260fd0d080d4b3381e | poster, innoshow | [打开](../../../../submission_repo/data/web_academy/recovered/dd40466a7d8cb941531fa6fc81098f19cf8955177a1fa176767d2155a2190249.jpg) |
| e53b67fbee791122f3692624 | poster, innoshow | [打开](../../../../submission_repo/data/web_academy/recovered/ad5bea4cd9a373b259bef6c3069b340b3bbf04c1bb87deab48506b40c7cb9594.jpg) |
| aab2c8ec4ea6205355945e8c | poster | [打开](../../../../submission_repo/data/web_academy/recovered/a3e1c7a68847eb91a47eecb8d2898f0d72b709d0f573ca63d96326c7d39c2b36.jpg) |
| 07f1883401926d7949a516b3 | poster | [打开](../../../../submission_repo/data/web_academy/recovered/0e3436f5b207e2bf6b10420299f71b30d0ae6962e17042b06daee5f9075a3208.png) |
| 68fec371554f8779cd75bbf1 | poster | [打开](../../../../submission_repo/data/web_academy/recovered/9a3328472d3b8e092c66c099b7fd5f5567a1fa0a9a2dd37b94d698ae1fb95207.jpg) |
| 51d8620a83598255059489b0 | poster | [打开](../../../../submission_repo/data/web_academy/recovered/1786b3093c565382f69975cb95c55902c258ba54723a9afc97f87cf616bf479c.jpg) |
| af324c06d25c4a163572a29a | poster | [打开](../../../../submission_repo/data/web_academy/recovered/611129032ce65d6f7b3fc01514ec12f54e615a40cfbb4c3829533c9e86f7f5e3.jpg) |
| f5b1fd954e8eb4c765a1fd4d | poster | [打开](../../../../submission_repo/data/web_academy/recovered/8c0113f65b0fd67e99cd9a30159be071970ece843692a288c6bb127758e7280d.jpg) |
| 8ac563d9af710db5e74d2dab | poster | [打开](../../../../submission_repo/data/web_academy/recovered/9def85d7c4a9972f3bb10f4e4021cd8fd25d3517835d20e1e6d0a46887702a85.png) |
| d4c5c33fcbccf80d10e6fde3 | poster | [打开](../../../../submission_repo/data/web_academy/recovered/cadafb16e78adfa5aaf5236fd6ac3c35c8b80e6d5cf68ba0d88c7ced2606d651.png) |
| be45eec0a59cb0b9ca0f73c1 | poster | [打开](../../../../submission_repo/data/web_academy/recovered/ac83f6dd6c82652aa0c5d0acd23699467f812fb634820e93a426ef18d166d0ce.jpg) |
| 54669266ccd1926336a35a8b | poster | [打开](../../../../submission_repo/data/web_academy/recovered/f4531bece631e997afdf328eb3897e401aad1171c6874b2cc679316a0148f97c.png) |
| 84907f19af5d799c969a975b | poster | [打开](../../../../submission_repo/data/web_academy/recovered/c55dfe7030777889a793f731b9baddd0307844618d10d45575a1bcfc7e71035e.jpg) |
| 06b1ccdba98a3ca8d83bb5ff | poster | [打开](../../../../submission_repo/data/web_academy/recovered/18b9dd3607ab8d1cbe076d1f699cca140961710e93c7d6d0c96370e82bde07dc.jpg) |
| 3b1d923f41211d858d442033 | poster | [打开](../../../../submission_repo/data/web_academy/recovered/5b9fec9be1d1d2d7d932bbf1b5c9a13bb449dfd9318fb16b46e60840533bce5f.jpg) |
| c38e2224c415bf56a1375234 | poster | [打开](../../../../submission_repo/data/web_academy/recovered/3937d2c2a2b0d66b5e542725e620947fdf7ceb7fd025b307024acfadf1af9150.jpg) |
| 1634e82aaa194e11742a044e | poster | [打开](../../../../submission_repo/data/web_academy/recovered/da6c4e80a765ce5f87d6856afb1f43a5a3dc1a8197d3583e17f28bbeeb0ce3c7.png) |
| ab4c1f724bf19995d797bfbf | poster | [打开](../../../../submission_repo/data/web_academy/recovered/c88fd2de7af8e071fbab03c7729eda010d8ac2f6ae02481d49b5010167b6df53.jpg) |

## 未恢复的 URL

| 图片 ID | 状态 | HTTP 状态 |
|---|---|---|
| 00ea82f1d0672cf2a32407ae | failed | 404 |
| 03cf5af74d026b7f6959078f | failed | 404 |
| 0911346354fd145ab7b58671 | failed | None |
| 09187d1adb0ab0b70122427f | failed | None |
| 0bbb2d3d0a34897b2affc138 | failed | 404 |
| 0be770173fa9e105a0639f5b | failed | 404 |
| 0bfe7a04607c13f59bc6efeb | failed | 404 |
| 0d43c176151e332af1d77499 | external_reference |  |
| 0ffee339a9e32323233f38c7 | failed | 404 |
| 15103b205b3cad5e8ab5767b | failed | 404 |
| 1667f9203b97821aabfe3bf9 | external_reference |  |
| 1ae2f69011b25c4825ffe3ef | failed | 404 |
| 21a72906bb2a0685871f7361 | failed | None |
| 2341234950d696e36c871d36 | failed | 404 |
| 24132b636d24b4e0c0341668 | failed | 404 |
| 394ea6ab090da88a1e92bbb4 | failed | 404 |
| 39bc17344845cf09714af289 | failed | 404 |
| 4101d45309bf8784bfee5fa8 | failed | 404 |
| 42a32af192b74699d79c03cb | failed | 404 |
| 462bc2478387d56bd7db4eb3 | failed | 404 |
| 518e78d28e3408a1de73c55f | failed | 404 |
| 58f7fff25079aae00fa10b1f | failed | 404 |
| 594a05c19c61c7ba8fd80ab8 | failed | 404 |
| 5ed00958cd1f875347b3bf75 | failed | 404 |
| 61a8c1a62e844c500db44379 | external_reference |  |
| 6d1025e58ef5f7c358907377 | failed | 404 |
| 784f18c164d6c8ec3df2e3ab | external_reference |  |
| 79835e40033154361e2300d6 | failed | 404 |
| 7cc357438a1a7ac7846fef85 | non_image |  |
| 8dfb6e7ce80ea74637b65687 | non_image |  |
| 8e3116683e240447d2a5265e | failed | 404 |
| 8f7a9293dc24e405f5856b4a | failed | 404 |
| 8fe11391b7faccef4918a3e9 | non_image |  |
| 963c60cd0e569795246c2820 | failed | 404 |
| 9c53f9a5393e81075b51cf85 | failed | 404 |
| 9cf1d8159b453cf6c35ea857 | failed | 404 |
| 9f3e4d467f458c9265fc7724 | failed | 404 |
| 9fc9fcadd8288b5d98d36abc | failed | 404 |
| a74ff36a994aeb8bcf41a02e | failed | 404 |
| a797ac37229369a5a30d02f1 | failed | 404 |
| aa5d67a4d63f9f5ec83ec591 | failed | 404 |
| b41fac18905815448c63e36e | external_reference |  |
| b4bf6fa56362c661dcf24ef8 | external_reference |  |
| b5b98522f894923eae84a902 | failed | 404 |
| b8aee0690ee7a13a1e70d9ce | failed | 404 |
| ba12cbe6f8cf2a0d1ce6c351 | failed | 404 |
| c3c47c14787e84ee28c945cc | external_reference |  |
| c8b496027698c17aae6b12b5 | non_image |  |
| cac9393a50c4021490e5826a | failed | 404 |
| ce59c53b1167b8f4a4c439f8 | failed | 404 |
| d0742da2d571c5400c0d9366 | failed | 404 |
| d59ddb1cf584d7c8d68ab951 | failed | 404 |
| d6de046fc2bb46395a3893ce | failed | 404 |
| d835d8560e3a73152f8acb97 | external_reference |  |
| dbe8f5ff39984fb646f024da | failed | 404 |
| df06738174b8726dd8fb5615 | failed | 404 |
| e6604a330af8578770ba2287 | failed | 404 |
| ec81318d527ba5ab49b80e04 | failed | 404 |
| ecf5df07954ebb2b85a152a2 | failed | 404 |
| f36907c5c076f494188891a5 | failed | None |
| f5fd3c40bba4ba922d5b3b8b | failed | 404 |
| f72d778b6add84c1acc46dac | failed | 404 |
| f89923a382f6ce0d3396305d | failed | None |
| fc18929ce44663f3b5fc15f6 | failed | 404 |

来源网址、文件路径和错误类型见 recovery.json；全部候选见 description_queue.json。
原图被 Git 忽略，迁移 worktree 前需单独备份 recovered 目录。
