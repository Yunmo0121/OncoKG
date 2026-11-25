# Task 09 · CIViC 证据逐条审阅

对照版本为 CIViC 2026-11-01 月度快照与 OncoKG v0.2。审阅单位是具体主张。相同 PMID 表明引用了同一篇论文，主张是否重合仍需核对人群或实验模型、研究设计、治疗背景和终点。本表为开发侧的来源对照，独立审阅待完成。

| CIViC 记录 | 原始论文中核对到的范围 | 与 OncoKG 的关系 | 拟议处置 |
| --- | --- | --- | --- |
| EID963 · T790M · PMID 24893891 | Cross 等人的 Cancer Discovery 论文包含细胞和动物实验，以及探索性临床观察。图 2–4 的代表性 T790M 细胞模型 H1975 和 PC-9VanR 分别有 L858R/T790M 与 exon 19 deletion/T790M 背景。CIViC 快照的描述出现 “L858M”，原文图 2–3 标注的相关模型为 L858R。 | 本地五条主张没有引用该 PMID。与 EID4294 同篇，但模型和变异背景不同。单变异的 CIViC 索引粒度不足以表达这些实验的复合变异背景。 | **暂缓纳入。** 先确认变异名称差异，按实验模型记录复合背景，区分临床前数据和探索性临床观察。 [CIViC](https://civicdb.org/links/evidence_items/963) · [原文，图 2–4](https://pmc.ncbi.nlm.nih.gov/articles/PMC4315625/) |
| EID1867 · T790M · PMID 27959700 | AURA3 随机开放标签 III 期主报告。研究人群为一线 EGFR-TKI 治疗中进展的 T790M 阳性晚期 NSCLC；对应本地记录的是总体随机人群的无进展生存期（PFS）比较。CIViC 还摘要了客观缓解率（ORR）。 | 本地 `AURA3-2017-T790M-OVERALL-PFS` 与 CIViC 的 PFS 部分为同一试验、同一人群、同一比较及终点。ORR 是同篇论文里另一个终点。 | **PFS 仅补充来源链接。** 保留一个 PFS 主张和一份底层论文计数。若后续需要 ORR，按独立终点建模，并沿用同一研究标识。 [CIViC](https://civicdb.org/links/evidence_items/1867) · [原文，摘要与结果](https://pmc.ncbi.nlm.nih.gov/articles/pmid/27959700/) |
| EID2158 · T790M · PMID 15737014 | Pao 等人的原文报告五例初始应答后出现获得性耐药，其中两例检出 T790M；第六例为术后辅助吉非替尼治疗中进展，另行描述。论文也包含治疗前样本和体外实验。 | 与本地 `PAO-2005-T790M-GEFITINIB-ERLOTINIB-RESISTANCE` 共享核心的历史耐药关联。CIViC 摘要将临床观察写进同一个六人叙述，原文和本地记录保留两类病例背景的区别。 | **可审阅后补充来源链接。** 病例范围以原文为准，保留本地肺腺癌范围与复核标记。该条关联不触发自动排除。 [CIViC](https://civicdb.org/links/evidence_items/2158) · [原文，摘要、结果与表 1](https://journals.plos.org/plosmedicine/article?id=10.1371/journal.pmed.0020073) |
| EID4294 · L858R · PMID 24893891 | 原文的 H3255（L858R）细胞实验测量 EGFR 磷酸化，并在 H3255 异种移植模型报告肿瘤变化。对应图 2A 与补充图 S6A。 | 本地五条主张没有该论文；与 EID963 共享研究出处，支持的实验模型和观察不同。 | **保留为新的临床前候选。** 主张注明细胞与异种移植模型及其各自终点。进入临床检索前需要独立审阅和单独的证据类型处理。 [CIViC](https://civicdb.org/links/evidence_items/4294) · [原文，图 2A 与补充图 S6A](https://pmc.ncbi.nlm.nih.gov/articles/PMC4315625/) |

## 后续建模可验收标准

- **出版物身份**用 PMID 或 DOI。EID963 和 EID4294 共用一个出版物身份，保留两个候选身份。
- **主张身份**至少记录研究、分子背景、实验模型或人群、比较和观察终点。AURA3 的 PFS 与 ORR 对应不同终点，累计出版物数时仍只算一篇。
- **来源链接**保留 CIViC 记录、月度快照和原文位置。来源链接与主张的新增审阅分别记录。
- **接受前复核**聚焦 EID963 的命名与复合变异范围、EID2158 的病例分组，以及 EID4294 的临床前边界。四条仍是候选记录，本轮为图谱更新提供审阅依据。
