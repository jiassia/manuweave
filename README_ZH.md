<p align="center">
  <img src="assets/logo.png" width="180" alt="ManuWeave 标志">
</p>
<h1 align="center">ManuWeave</h1>
<p align="center">面向 AI Agent 的原生 Word 与 LaTeX 学术排版 Skill</p>
<p align="center">
  <a href="README.md">English</a> · <a href="README_ZH.md">简体中文</a>
</p>
<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-0f766e?style=flat-square" alt="MIT 许可"></a>
  <img src="https://img.shields.io/badge/Python-3.11%2B-22354d?style=flat-square" alt="Python 3.11+">
  <a href="SKILL.md"><img src="https://img.shields.io/badge/Agent-Skill-0f766e?style=flat-square" alt="Agent Skill"></a>
</p>

ManuWeave 是一个轻量学术文档 Skill，适用于 Codex、Claude Code 等宿主。通过参考文档或**内置期刊模板**整理 Word 和 LaTeX，保留原生对象并检查结果，无须额外配置 AI API。

## 通过 Agent 安装

将以下提示词粘贴到 Agent，即可下载 Skill、安装其本地 Python 依赖并读取使用说明。

```text
安装并使用 https://github.com/jiassia/manuweave 的 ManuWeave，采用 main 分支。

先识别当前宿主的个人 Skill 目录，例如 ~/.codex/skills/manuweave
或 ~/.claude/skills/manuweave。通过 Git clone 或下载 ZIP 安装到新目录。
如已安装，先检查并复用，保留本地修改，不直接覆盖。

读取 SKILL.md，只按任务需要加载 static 片段。
使用 Python 3.11 及以上版本，为本 Skill 创建独立 .venv，
通过该环境的 Python 安装 requirements.txt，
再用同一环境运行 scripts/manuweave.py doctor。
使用本机已有的 Word、LibreOffice 和 TeX，不自动安装字体或系统工具。
无须额外配置 AI API。

准备完成后，提示提供原稿，以及参考模板或目标期刊与格式要求。
```

## 使用

提供 Word 原稿或原生 LaTeX 工程，再附参考模板，或指定目标期刊和投稿阶段。例如：

> 使用 ManuWeave，按 B.docx 的版式整理 A.docx，保留公式和图表，检查缺失结构，交付可编辑文档和检查报告。

支持标题、摘要、正文、公式、图表和参考文献等格式调整。宿主负责调用工具和检查页面；实质内容补全需要授权与原文依据。

[模板库](#内置模板)

## 内置模板

共 286 项模板。

<details open>
<summary><strong>期刊模板（16）</strong></summary>

| 期刊名称 | **Profile ID** | 来源 |
| --- | --- | --- |
| 计算机应用研究 | `cn-aroc-official-word` | [官方来源](https://www.arocmag.cn/download/template) |
| 电子测量技术 | `cn-emt-official-word` | [官方来源](http://emt.cnjournals.com/uploadfile/news_images/emt/2023-03-23/uploadfilenews_imagesemt2017-07-28%E3%80%8A%E7%94%B5%E5%AD%90%E6%B5%8B%E9%87%8F%E6%8A%80%E6%9C%AF%E3%80%8B%E8%AE%BA%E6%96%87%E6%8E%92%E7%89%88%E6%A8%A1%E7%89%88.doc) |
| 机床与液压 | `cn-jcyyy-official-word` | [官方来源](http://www.jcyyy.com.cn/download_upload_file.aspx?file_name=/uploadfile/jcyyy/20230704/%E3%80%8A%E6%9C%BA%E5%BA%8A%E4%B8%8E%E6%B6%B2%E5%8E%8B%E3%80%8B%E8%AE%BA%E6%96%87%E6%8A%95%E7%A8%BF%E6%A8%A1%E6%9D%BF.docx) |
| 现代电子技术 | `cn-xddzjs-official-word` | [官方来源](https://publishmedia.cbpt.cnki.net/portal/minio/webs/xddj/media/web/2025/11/12/%E8%AE%BA%E6%96%87%E6%A8%A1%E6%9D%BF.docx) |
| 中国全科医学 | `cn-cgp-research-word-2023` | [官方来源](https://www.chinagp.net/fileup/1007-9572/ITEM/20230921140946.docx) |
| 中国医院药学杂志 | `cn-cjhp-research-word-2026` | [官方来源](https://zgyyyx.magtechjournal.com/CN/item/downloadFile.do?id=10) |
| 食品工业科技 | `cn-foodindustry-word-confirmed` | [官方来源](https://www.spgykj.com/supplement/preview/a2c39452-a4d8-4f78-b329-28f9aa7d1c05) |
| 食品科学 | `cn-foodscience-word-2020` | [官方来源](https://www.spkx.net.cn/UserFiles/File/spkxmb-2020.doc) |
| 统计与决策 | `cn-statistics-decision-word-confirmed` | [官方来源](http://www.tjyjc.com/tougao/3.html) |
| 计算机集成制造系统 | `cn-cims-initial-word` | [官方来源](http://www.cims-journal.cn/fileup/1006-5911/ITEM/20241121154611.docx) |
| 计算机集成制造系统 | `cn-cims-revised-word` | [官方来源](http://www.cims-journal.cn/fileup/1006-5911/ITEM/20220128161938.docx) |
| Nature Communications | `int-ncomms-initial-word` | [官方来源](https://www.nature.com/ncomms/submit/how-to-submit) |
| BMC Public Health | `int-bmc-public-health-research-word` | [官方来源](https://link.springer.com/journal/12889/submission-guidelines) |
| Frontiers in Public Health | `int-frontiers-public-health-word` | [官方来源](https://www.frontiersin.org/journals/public-health/for-authors/author-guidelines) |
| PLOS Computational Biology | `int-plos-comp-biol-research-word` | [官方来源](https://journals.plos.org/ploscompbiol/s/submission-guidelines) |
| PLOS ONE | `int-plos-one-research-word` | [官方来源](https://journals.plos.org/plosone/s/submission-guidelines) |

</details>

<details>
<summary><strong>出版方模板（57）</strong></summary>

| 出版方 | **Profile ID** | 来源 |
| --- | --- | --- |
| ACM | `acm-acmcp` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM | `acm-acmengage` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM | `acm-acmlarge` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM | `acm-acmsmall` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM | `acm-acmtog` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM | `acm-manuscript-review-anonymous` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM | `acm-manuscript` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM | `acm-sigconf-review-anonymous` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM | `acm-sigconf` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM | `acm-sigplan` | [官方来源](https://ctan.org/pkg/acmart) |
| Elsevier | `elsevier-1p` | [官方来源](https://ctan.org/pkg/elsarticle) |
| Elsevier | `elsevier-3p-double` | [官方来源](https://ctan.org/pkg/elsarticle) |
| Elsevier | `elsevier-3p-single` | [官方来源](https://ctan.org/pkg/elsarticle) |
| Elsevier | `elsevier-5p` | [官方来源](https://ctan.org/pkg/elsarticle) |
| Elsevier | `elsevier-cas-dc-review` | [官方来源](https://ctan.org/pkg/els-cas-templates) |
| Elsevier | `elsevier-cas-dc` | [官方来源](https://ctan.org/pkg/els-cas-templates) |
| Elsevier | `elsevier-cas-sc-review` | [官方来源](https://ctan.org/pkg/els-cas-templates) |
| Elsevier | `elsevier-cas-sc` | [官方来源](https://ctan.org/pkg/els-cas-templates) |
| Elsevier | `elsevier-preprint-author-year` | [官方来源](https://ctan.org/pkg/elsarticle) |
| Elsevier | `elsevier-preprint-numeric` | [官方来源](https://ctan.org/pkg/elsarticle) |
| Elsevier | `elsevier-review` | [官方来源](https://ctan.org/pkg/elsarticle) |
| IEEE | `ieee-conference-compsoc` | [官方来源](https://ctan.org/pkg/ieeetran) |
| IEEE | `ieee-conference` | [官方来源](https://ctan.org/pkg/ieeetran) |
| IEEE | `ieee-journal-compsoc` | [官方来源](https://ctan.org/pkg/ieeetran) |
| IEEE | `ieee-journal-comsoc` | [官方来源](https://ctan.org/pkg/ieeetran) |
| IEEE | `ieee-journal-transmag` | [官方来源](https://ctan.org/pkg/ieeetran) |
| IEEE | `ieee-journal` | [官方来源](https://ctan.org/pkg/ieeetran) |
| IEEE | `ieee-peerreview` | [官方来源](https://ctan.org/pkg/ieeetran) |
| IEEE | `ieee-peerreviewca` | [官方来源](https://ctan.org/pkg/ieeetran) |
| IEEE | `ieee-technote` | [官方来源](https://ctan.org/pkg/ieeetran) |
| ACM | `acm-word-submission-2023` | [官方来源](https://www.acm.org/binaries/content/assets/publications/taps/acm_submission_template.docx) |
| IEEE | `ieee-word-a4-2019` | [官方来源](https://attend.ieee.org/argencon-2020/wp-content/uploads/sites/171/conference-template-a4.docx) |
| IEEE | `ieee-word-letter-2019` | [官方来源](https://ieee-icps.com/conference-template-letter.docx) |
| Oxford University Press | `oup-contemporary-large` | [官方来源](https://ctan.org/pkg/oup-authoring-template) |
| Oxford University Press | `oup-contemporary-medium` | [官方来源](https://ctan.org/pkg/oup-authoring-template) |
| Oxford University Press | `oup-contemporary-mediumone` | [官方来源](https://ctan.org/pkg/oup-authoring-template) |
| Oxford University Press | `oup-contemporary-small` | [官方来源](https://ctan.org/pkg/oup-authoring-template) |
| Oxford University Press | `oup-modern-large` | [官方来源](https://ctan.org/pkg/oup-authoring-template) |
| Oxford University Press | `oup-modern-medium` | [官方来源](https://ctan.org/pkg/oup-authoring-template) |
| Oxford University Press | `oup-modern-mediumone` | [官方来源](https://ctan.org/pkg/oup-authoring-template) |
| Oxford University Press | `oup-modern-small` | [官方来源](https://ctan.org/pkg/oup-authoring-template) |
| Oxford University Press | `oup-traditional-large` | [官方来源](https://ctan.org/pkg/oup-authoring-template) |
| Oxford University Press | `oup-traditional-medium` | [官方来源](https://ctan.org/pkg/oup-authoring-template) |
| Oxford University Press | `oup-traditional-mediumone` | [官方来源](https://ctan.org/pkg/oup-authoring-template) |
| Oxford University Press | `oup-traditional-small-author-year` | [官方来源](https://ctan.org/pkg/oup-authoring-template) |
| Oxford University Press | `oup-traditional-small` | [官方来源](https://ctan.org/pkg/oup-authoring-template) |
| AIP Publishing | `revtex-aip-apl-reprint` | [官方来源](https://journals.aps.org/revtex) |
| AIP Publishing | `revtex-aip-chaos-reprint` | [官方来源](https://journals.aps.org/revtex) |
| AIP Publishing | `revtex-aip-jcp-preprint` | [官方来源](https://journals.aps.org/revtex) |
| AIP Publishing | `revtex-aip-jcp-reprint` | [官方来源](https://journals.aps.org/revtex) |
| AIP Publishing | `revtex-aip-jmp-reprint` | [官方来源](https://journals.aps.org/revtex) |
| American Physical Society | `revtex-aps-preprint` | [官方来源](https://journals.aps.org/revtex) |
| American Physical Society | `revtex-aps-reprint` | [官方来源](https://journals.aps.org/revtex) |
| American Physical Society | `revtex-prl-reprint` | [官方来源](https://journals.aps.org/revtex) |
| American Physical Society | `revtex-rmp-reprint` | [官方来源](https://journals.aps.org/revtex) |
| Springer | `springer-llncs-author-year` | [官方来源](https://ctan.org/pkg/llncs) |
| Springer | `springer-llncs-numeric` | [官方来源](https://ctan.org/pkg/llncs) |

</details>

<details>
<summary><strong>ACM（41）</strong></summary>

| 期刊名称 | **Profile ID** | 来源 |
| --- | --- | --- |
| Distributed Ledger Technologies: Research and Practice | `acm-dlt-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| Formal Aspects of Computing | `acm-fac-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Computing for Healthcare | `acm-health-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| Journal of the ACM | `acm-jacm-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| Journal on Autonomous Transportation Systems | `acm-jats-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Journal on Emerging Technologies in Computing Systems | `acm-jetc-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| Proceedings of the ACM on Human-Computer Interaction | `acm-pacmhci-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| Proceedings of the ACM on Programming Languages | `acm-pacmpl-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Autonomous and Adaptive Systems | `acm-taas-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Architecture and Code Optimization | `acm-taco-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Algorithms | `acm-talg-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Asian and Low-Resource Language Information Processing | `acm-tallip-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Applied Perception | `acm-tap-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Cyber-Physical Systems | `acm-tcps-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Embedded Computing Systems | `acm-tecs-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Evolutionary Learning and Optimization | `acm-telo-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Human-Robot Interaction | `acm-thri-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Interactive Intelligent Systems | `acm-tiis-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Internet of Things | `acm-tiot-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Intelligent Systems and Technology | `acm-tist-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Knowledge Discovery from Data | `acm-tkdd-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Computing Education | `acm-toce-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Computer-Human Interaction | `acm-tochi-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Computational Logic | `acm-tocl-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Computer Systems | `acm-tocs-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Design Automation of Electronic Systems | `acm-todaes-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Database Systems | `acm-tods-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Graphics | `acm-tog-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Information Systems | `acm-tois-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Internet Technology | `acm-toit-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Multimedia Computing, Communications and Applications | `acm-tomm-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Mathematical Software | `acm-toms-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Programming Languages and Systems | `acm-toplas-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Privacy and Security | `acm-tops-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Recommender Systems | `acm-tors-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Storage | `acm-tos-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Software Engineering and Methodology | `acm-tosem-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Sensor Networks | `acm-tosn-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Quantum Computing | `acm-tqc-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on Reconfigurable Technology and Systems | `acm-trets-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |
| ACM Transactions on the Web | `acm-tweb-article-publication` | [官方来源](https://ctan.org/pkg/acmart) |

</details>

<details>
<summary><strong>IEEE（52）</strong></summary>

| 期刊名称 | **Profile ID** | 来源 |
| --- | --- | --- |
| IEEE Transactions on Human-Machine Systems | `computer-ieee-101-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Transactions on Geoscience and Remote Sensing | `computer-ieee-102-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Transactions on Games | `computer-ieee-107-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Transactions on Fuzzy Systems | `computer-ieee-109-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Transactions on Evolutionary Computation | `computer-ieee-110-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Internet of Things Journal | `computer-ieee-12-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Transactions on Automation Science and Engineering | `computer-ieee-126-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/158/download) |
| IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems | `computer-ieee-129-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Transactions on Communications | `computer-ieee-136-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Transactions on Affective Computing | `computer-ieee-138-original-research` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/183/download) |
| IEEE Transactions on Circuits and Systems I: Regular Papers | `computer-ieee-139-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Transactions on Big Data | `computer-ieee-141-original-research` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/183/download) |
| IEEE Transactions on Computers | `computer-ieee-142-original-research` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/183/download) |
| IEEE Transactions on Cloud Computing | `computer-ieee-144-original-research` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/183/download) |
| IEEE Transactions on Dependable and Secure Computing | `computer-ieee-145-original-research` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/183/download) |
| IEEE Transactions on Knowledge and Data Engineering | `computer-ieee-148-original-research` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/183/download) |
| IEEE Transactions on Mobile Computing | `computer-ieee-150-original-research` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/195/download) |
| IEEE Transactions on Pattern Analysis and Machine Intelligence | `computer-ieee-154-original-research` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/183/download) |
| IEEE Transactions on Parallel and Distributed Systems | `computer-ieee-155-original-research` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/183/download) |
| IEEE Transactions on Services Computing | `computer-ieee-156-original-research` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/183/download) |
| IEEE Transactions on Software Engineering | `computer-ieee-157-original-research` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/183/download) |
| IEEE Transactions on Sustainable Computing | `computer-ieee-158-original-research` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/183/download) |
| IEEE Transactions on Visualization and Computer Graphics | `computer-ieee-159-original-research` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/183/download) |
| IEEE Transactions on Circuits and Systems for Video Technology | `computer-ieee-160-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Transactions on Cybernetics | `computer-ieee-161-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Journal of Biomedical and Health Informatics | `computer-ieee-177-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/401/download) |
| IEEE Journal of Biomedical and Health Informatics | `computer-ieee-177-original-research` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/368/download) |
| IEEE Transactions on Industrial Informatics | `computer-ieee-188-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/418/download) |
| IEEE Transactions on Industrial Informatics | `computer-ieee-188-original-research` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/379/download) |
| Proceedings of the IEEE | `computer-ieee-19-original-research` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Signal Processing Letters | `computer-ieee-194-original-research` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/419/download) |
| IEEE Journal on Selected Areas in Communications | `computer-ieee-21-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Transactions on Computational Social Systems | `computer-ieee-223-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Transactions on Audio, Speech and Language Processing（原 IEEE/ACM Transactions on Audio, Speech and Language Processing） | `computer-ieee-271-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE/ACM Transactions on Computational Biology and Bioinformatics | `computer-ieee-272-original-research` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Transactions on Networking（原 IEEE/ACM Transactions on Networking） | `computer-ieee-273-original-research` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Geoscience and Remote Sensing Letters | `computer-ieee-30-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Transactions on Wireless Communications | `computer-ieee-36-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Transactions on Very Large Scale Integration (VLSI) Systems | `computer-ieee-39-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/680/download) |
| IEEE Transactions on Very Large Scale Integration (VLSI) Systems | `computer-ieee-39-original-research` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Transactions on Medical Imaging | `computer-ieee-4-original-research` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/4/download) |
| IEEE Transactions on Systems, Man,and Cybernetics: Systems | `computer-ieee-60-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Transactions on Robotics | `computer-ieee-73-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Transactions on Reliability | `computer-ieee-76-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Transactions on Network and Service Management | `computer-ieee-82-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Transactions on Neural Networks and learning systems | `computer-ieee-84-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Transactions on Multimedia | `computer-ieee-87-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Transactions on Intelligent Transportation Systems | `computer-ieee-91-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Transactions on Information Theory | `computer-ieee-92-original-research-and-brief-one-column` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/253/download) |
| IEEE Transactions on Information Theory | `computer-ieee-92-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/253/download) |
| IEEE Transactions on Image Processing | `computer-ieee-93-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |
| IEEE Transactions on Information Forensics and Security | `computer-ieee-98-original-research-and-brief` | [官方来源](https://template-selector.ieee.org/api/ieee-template-selector/template/39/download) |

</details>

<details>
<summary><strong>中文期刊（10）</strong></summary>

| 期刊名称 | **Profile ID** | 来源 |
| --- | --- | --- |
| 计算机应用研究 | `cn-aroc-word-template` | [官方来源](https://www.arocmag.cn/download/template) |
| 计算机学报 | `cn-cjc-word-template` | [官方来源](http://cjc.ict.ac.cn/wltg/new/submit/CJC-Templet_Word2003.doc) |
| 计算机研究与发展 | `cn-crad-word-2025` | [官方来源](https://crad.ict.ac.cn/fileJSJYJYFZ/news/jsjyjyfz/a6383fdb-214a-48e1-bd23-3759093cab59.docx) |
| 计算机工程 | `cn-ecice-word-2026` | [官方来源](https://www.ecice06.com/attached/file/20260713/20260713132549_708.doc) |
| 计算机辅助设计与图形学学报 | `cn-jcad-template-2026` | [官方来源](https://www.jcad.cn/supplement/preview/965ed6b2-6bb9-4255-bf94-25a968f74b6f) |
| 中文信息学报 | `cn-jcip-template-current` | [官方来源](http://jcip.cipsc.org.cn/fileZWXXXB/news/zwxxxb/93db5994-c98f-41f6-b4f3-7abc609f27cf.doc) |
| 计算机应用 | `cn-joca-word-2026` | [官方来源](https://www.joca.cn/CN/item/downloadFile.jsp?filedisplay=20260421131814.doc) |
| 计算机工程与科学 | `cn-joces-final-template-2026` | [官方来源](http://joces.nudt.edu.cn/CN/item/downloadFile.jsp?filedisplay=20251103171729.docx) |
| 软件学报 | `cn-jos-word-2025` | [官方来源](https://www.jos.org.cn/uploadfile/news_images/jos/2026-04-02/%E8%BD%AF%E4%BB%B6%E5%AD%A6%E6%8A%A5%E6%8E%92%E7%89%88%E6%A0%B7%E4%BE%8B2025%E5%B9%B4%E7%89%88.doc) |
| 计算机科学 | `cn-jsjkx-word-2024` | [官方来源](https://www.jsjkx.com/attached/image/20240711/20240711091132_401.doc) |

</details>

<details>
<summary><strong>Elsevier（5）</strong></summary>

| 期刊名称 | **Profile ID** | 来源 |
| --- | --- | --- |
| Artificial Intelligence | `computer-elsevier-artificial-intelligence` | [官方来源](https://aij.ijcai.org/formatting-requirements/) |
| Engineering Applications of Artificial Intelligence | `computer-elsevier-engineering-applications-of-artificial-intelligence` | [官方来源](https://shop.elsevier.com/journals/engineering-applications-of-artificial-intelligence/0952-1976) |
| Future Generation Computer Systems | `computer-elsevier-future-generation-computer-systems-rse-2026` | [官方来源](https://lists.mcs.anl.gov/pipermail/hpc-announce/2025-November/011602.html) |
| Pattern Recognition | `computer-elsevier-pattern-recognition` | [官方来源](https://shop.elsevier.com/journals/pattern-recognition/0031-3203) |
| Signal Processing | `computer-elsevier-signal-processing` | [官方来源](https://shop.elsevier.com/journals/signal-processing/0165-1684) |

</details>

<details>
<summary><strong>Wiley（16）</strong></summary>

| 期刊名称 | **Profile ID** | 来源 |
| --- | --- | --- |
| Computer animation &amp; virtual worlds | `computer-wiley-cavw-manuscript` | [官方来源](https://onlinelibrary.wiley.com/page/journal/1546427x/homepage/forauthors.html) |
| Computer animation &amp; virtual worlds | `computer-wiley-cavw-njd-choice` | [官方来源](https://authorservices.wiley.com/asset/WileyNJDv5_Template.zip) |
| Computer Graphics Forum | `computer-wiley-cgf-regular-submission` | [官方来源](https://www.eg.org/wp/wp-content/uploads/2024/12/egPublStyle-cgf.zip) |
| Computational Intelligence | `computer-wiley-ci-njd-choice` | [官方来源](https://authorservices.wiley.com/asset/WileyNJDv5_Template.zip) |
| Concurrency and Computation: Practice and Experience | `computer-wiley-cpe-njd-choice` | [官方来源](https://authorservices.wiley.com/asset/WileyNJDv5_Template.zip) |
| Expert Systems | `computer-wiley-expert-njd-choice` | [官方来源](https://authorservices.wiley.com/asset/WileyNJDv5_Template.zip) |
| IET Communications | `computer-wiley-iet-com-njd-choice` | [官方来源](https://authorservices.wiley.com/asset/WileyNJDv5_Template.zip) |
| IET Computer Vision | `computer-wiley-iet-cvi-njd-choice` | [官方来源](https://authorservices.wiley.com/asset/WileyNJDv5_Template.zip) |
| IET Information Security | `computer-wiley-iet-ifs-njd-choice` | [官方来源](https://authorservices.wiley.com/asset/WileyNJDv5_Template.zip) |
| IET Intelligent Transport Systems | `computer-wiley-iet-its-njd-choice` | [官方来源](https://authorservices.wiley.com/asset/WileyNJDv5_Template.zip) |
| Journal of the Association for Information Science and Technology | `computer-wiley-jasist-njd-2025` | [官方来源](https://authorservices.wiley.com/asset/WileyNJDv5_Template.zip) |
| Journal of Software: Evolution and Process | `computer-wiley-jsep-manuscript` | [官方来源](https://onlinelibrary.wiley.com/page/journal/20477481/homepage/forauthors.html) |
| Journal of Software: Evolution and Process | `computer-wiley-jsep-njd-choice` | [官方来源](https://authorservices.wiley.com/asset/WileyNJDv5_Template.zip) |
| Software: Practice and Experience | `computer-wiley-spe-manuscript` | [官方来源](https://onlinelibrary.wiley.com/page/journal/1097024x/homepage/forauthors.html) |
| Software Testing, Verification and Reliability | `computer-wiley-stvr-manuscript` | [官方来源](https://onlinelibrary.wiley.com/page/journal/10991689/homepage/guide.htm) |
| Software Testing, Verification and Reliability | `computer-wiley-stvr-njd-choice` | [官方来源](https://authorservices.wiley.com/asset/WileyNJDv5_Template.zip) |

</details>

<details>
<summary><strong>更多期刊（80）</strong></summary>

| 期刊名称 | **Profile ID** | 来源 |
| --- | --- | --- |
| Frontiers of Computer Science | `computer-fcs-word-2025` | [官方来源](https://journal.hep.com.cn/hep/EN/file/download/?fileId=JUknhLfWuL4OhMkHGi0CMQ==&type=file&fileName=template%20in%20MS%20Word_2025.docx) |
| Briefings in Bioinformatics | `computer-oup-bib` | [官方来源](https://ctan.org/pkg/oup-authoring-template) |
| Bioinformatics | `computer-oup-bioinformatics` | [官方来源](https://ctan.org/pkg/oup-authoring-template) |
| The Computer Journal | `computer-oup-comjnl` | [官方来源](https://ctan.org/pkg/oup-authoring-template) |
| Interacting with Computers | `computer-oup-iwc` | [官方来源](https://ctan.org/pkg/oup-authoring-template) |
| Journal of the American Medical Informatics Association | `computer-oup-jamia` | [官方来源](https://ctan.org/pkg/oup-authoring-template) |
| International Journal of Software Tools for Technology Transfer | `computer-springer-10009` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| International Journal on Document Analysis and Recognition | `computer-springer-10032` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Pattern Analysis and Applications | `computer-springer-10044` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Knowledge and Information Systems | `computer-springer-10115` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Software and Systems Modeling | `computer-springer-10270` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Autonomous Agents and Multi-Agent Systems | `computer-springer-10458` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Automated Software Engineering | `computer-springer-10515` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Computer Supported Cooperative Work | `computer-springer-10606` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Data Mining and Knowledge Discovery | `computer-springer-10618` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Distributed and Parallel Databases | `computer-springer-10619` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Designs, Codes and Cryptography | `computer-springer-10623` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Empirical Software Engineering | `computer-springer-10664` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Formal Methods in System Design | `computer-springer-10703` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| GeoInformatica | `computer-springer-10707` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Journal of Grid computing | `computer-springer-10723` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Discover Computing（原 Information Retrieval Journal） | `computer-springer-10791` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Journal of Automated Reasoning | `computer-springer-10817` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Journal of Electronic Testing-Theory and Applications | `computer-springer-10836` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Journal of Intelligent Information Systems | `computer-springer-10844` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Journal of Global Optimization | `computer-springer-10898` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Machine Learning | `computer-springer-10994` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Mobile Networks and Applications | `computer-springer-11036` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Multimedia Tools and Applications | `computer-springer-11042` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Natural Computing | `computer-springer-11047` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Neural Processing Letters | `computer-springer-11063` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Software Quality Journal | `computer-springer-11219` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| The Journal of Supercomputing | `computer-springer-11227` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Real-Time Systems | `computer-springer-11241` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| User Modeling and User-Adapted Interaction | `computer-springer-11257` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| International Journal of Computer Vision | `computer-springer-11263` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Wireless Networks | `computer-springer-11276` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| World Wide Web | `computer-springer-11280` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Service Oriented Computing and Applications | `computer-springer-11761` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Peer-to-Peer Networking and Applications | `computer-springer-12083` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| EURASIP Journal on Information Security | `computer-springer-13635` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Machine Vision and Applications | `computer-springer-138` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Theory of Computing Systems | `computer-springer-224` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Acta Informatica | `computer-springer-236` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Data Science and Engineering | `computer-springer-41019` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Cybersecurity | `computer-springer-42400` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| CCF Transactions on Pervasive Computing and Interaction | `computer-springer-42486` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| CCF Transactions on High Performance Computing | `computer-springer-42514` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Distributed Computing | `computer-springer-446` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Algorithmica | `computer-springer-453` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Discrete &amp; Computational Geometry | `computer-springer-454` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Soft Computing | `computer-springer-500` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Neural Computing and Applications | `computer-springer-521` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Multimedia Systems | `computer-springer-530` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Requirements Engineering | `computer-springer-766` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Personal and Ubiquitous Computing | `computer-springer-779` | [官方来源](https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12) |
| Applied Intelligence | `computer-springer-apin` | [官方来源](https://media.springer.com/full/springer-instructions-for-authors-assets/rar/LaTeX_VLDBJ_Template.rar) |
| The VLDB Journal | `computer-springer-vldb` | [官方来源](https://media.springer.com/full/springer-instructions-for-authors-assets/rar/LaTeX_VLDBJ_Template.rar) |
| The Journal of Symbolic Logic | `comp-asl-jsl` | [官方来源](https://aslonline.org/journals/author-resources/) |
| Mathematical Structures in Computer Science | `comp-cambridge-mscs` | [官方来源](https://www.cambridge.org/core/journals/mathematical-structures-in-computer-science/information/author-instructions/preparing-your-materials) |
| Theory and Practice of Logic Programming | `comp-cambridge-tplp` | [官方来源](https://www.cambridge.org/core/journals/theory-and-practice-of-logic-programming/information/author-instructions/preparing-your-materials) |
| Fundamenta Informaticae | `comp-fundamenta-informaticae-34` | [官方来源](https://fundamenta-informaticae.mimuw.edu.pl/home/for-authors/author-guidelines/) |
| International Journal of Information Security and Privacy | `comp-igi-ijisp-apa7-word` | [官方来源](https://www.igi-global.com/publish/contributor-resources/journal-guidelines-for-submission/?titleid=1096) |
| International Journal of Knowledge Management | `comp-igi-ijkm-apa7-word` | [官方来源](https://www.igi-global.com/publish/contributor-resources/journal-guidelines-for-submission/?titleid=1083) |
| International Journal on Semantic Web and Information Systems | `comp-igi-ijswis-apa7-word` | [官方来源](https://www.igi-global.com/publish/contributor-resources/journal-guidelines-for-submission/?titleid=1092) |
| Journal of Database Management | `comp-igi-jdm-apa7-word` | [官方来源](https://www.igi-global.com/publish/contributor-resources/journal-guidelines-for-submission/?titleid=1072) |
| INFORMS Journal on Computing | `comp-informs-ijoc-submission` | [官方来源](https://pubsonline.informs.org/page/ijoc/submission-guidelines) |
| Journal of Artificial Intelligence Research | `comp-jair-2025` | [官方来源](https://www.jair.org/index.php/jair/formatting) |
| The Journal of the Acoustical Society of America | `comp-jasa-word` | [官方来源](https://pubs.aip.org/DocumentLibrary/files/publications/jasa/Information_for_Contributors_to_JASA.pdf) |
| Journal of Functional Programming | `comp-jfp-epi-final` | [官方来源](https://jfp.episciences.org/for-authors) |
| Journal of Machine Learning Research | `comp-jmlr` | [官方来源](https://raw.githubusercontent.com/JmlrOrg/jmlr-style-file/master/sample.tex) |
| Journal of Speech, Language, and Hearing Research | `comp-jslhr-word` | [官方来源](https://academy.pubs.asha.org/wp-content/uploads/JSLHR_Author_Instructions.pdf) |
| Logical Methods in Computer Science | `comp-lmcs` | [官方来源](https://lmcs.episciences.org/page/authors-latex-style) |
| Transactions of the Association for Computational Linguistics | `comp-tacl-2021-accepted` | [官方来源](https://transacl.org/index.php/tacl/about/submissions) |
| Transactions of the Association for Computational Linguistics | `comp-tacl-2021-submission` | [官方来源](https://transacl.org/index.php/tacl/about/submissions) |
| Human-Computer Interaction | `comp-tf-hhci20-word` | [官方来源](https://raw.githubusercontent.com/madpickle/HCIJ_LaTeX_Template/master/articleMainDocument.tex) |
| International Journal of Geographical Information Science | `comp-tf-tgis20-word` | [官方来源](https://authstaging.wpengine.com/wp-content/uploads/2020/12/TF_Template_Word_Windows_2016.zip) |
| Journal of Computer Information Systems | `comp-tf-ucis20-word` | [官方来源](https://authstaging.wpengine.com/wp-content/uploads/2020/12/TF_Template_Word_Windows_2016.zip) |
| Journal of Global Information Technology Management | `comp-tf-ugit20-word` | [官方来源](https://authstaging.wpengine.com/wp-content/uploads/2020/12/TF_Template_Word_Windows_2016.zip) |
| Virtual Reality &amp; Intelligent Hardware | `comp-vrih-word` | [官方来源](https://www.keaipublishing.com/media/omphe3x2/virtual-reality-intelligent-hardware-research-paper-template.docx) |

</details>



<details>
<summary><strong>通用模板（9）</strong></summary>

| 名称 | **Profile ID** | 来源 |
| --- | --- | --- |
| 英文双栏论文 | `en-article-double` | [ManuWeave](https://github.com/jiassia/manuweave) |
| 英文单栏论文 | `en-article-single` | [ManuWeave](https://github.com/jiassia/manuweave) |
| 英文会议论文 | `en-conference` | [ManuWeave](https://github.com/jiassia/manuweave) |
| 英文科技报告 | `en-report` | [ManuWeave](https://github.com/jiassia/manuweave) |
| 中文双栏论文 | `zh-journal-double` | [ManuWeave](https://github.com/jiassia/manuweave) |
| 中文单栏论文 | `zh-journal-single` | [ManuWeave](https://github.com/jiassia/manuweave) |
| 中文硕士学位论文 | `zh-master` | [ManuWeave](https://github.com/jiassia/manuweave) |
| 中文博士学位论文 | `zh-phd` | [ManuWeave](https://github.com/jiassia/manuweave) |
| 中文本科毕业论文 | `zh-undergraduate` | [ManuWeave](https://github.com/jiassia/manuweave) |

</details>

## 许可

[MIT](LICENSE)

## LINUX DO 社区

感谢 [Linux.do](https://linux.do/) 社区的支持与贡献。
