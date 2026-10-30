"""Build only confirmed official submission-format facts, without publisher files."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATE = "2026-10-30"


def origin(file, url, sha256, size, kind):
    return {"file": file, "url": url, "sha256": sha256, "bytes": size, "source_kind": kind,
            "retrieved_at": DATE, "original_file_redistributed": False}


AROC = origin("aroc-official-template.doc", "https://www.arocmag.cn/download/template",
              "baf9fce8b2bc56f2320c8bf4541546e43f48a8f3a1c773b40667d7b2a7b872cb", 169984, "official_submission_template")
AROC_INDEX = origin("aroc-template-page.html", "https://www.arocmag.cn/info/instruction/template",
                    "a18e26175e76d4558c970f2c947113de12a5d42b183f13da599817d2bcfb8b74", 15125, "official_template_index")
HYDRA = origin("jcyyy-official-template.docx", "http://www.jcyyy.com.cn/download_upload_file.aspx?file_name=/uploadfile/jcyyy/20230704/《机床与液压》论文投稿模板.docx",
               "303d08e5ddefda7dbf727c5140a7fcc16d2a484402f0e6a3b1e9815d5a7c78db", 1049855, "official_submission_template")
HYDRA_INDEX = origin("jcyyy-template-page.html", "http://www.jcyyy.com.cn/jcyyy/news/view/20230703154824001",
                     "c43a42e74c118172c76532374140736d19ea5f226b6c4c4cc1d0992504baab26", 29244, "official_template_instructions")
MODERN = origin("xddzjs-official-template.docx", "https://publishmedia.cbpt.cnki.net/portal/minio/webs/xddj/media/web/2025/11/12/论文模板.docx",
                "f0fba757547a67ae6bcf7735423cf5f17eb7cea020190ffb05a6b529fca51ed7", 516371, "official_submission_template")
MODERN_INDEX = origin("xddzjs-official-home.html", "https://xddj.cbpt.cnki.net/portal/",
                      "5d391d7cbdd4add3f9bcea092045b4687c061d85773eec22c78fd093d1a81cf8", 568083, "official_template_index")
EMT = origin("emt-official-typesetting-template.doc", "http://emt.cnjournals.com/uploadfile/news_images/emt/2023-03-23/uploadfilenews_imagesemt2017-07-28《电子测量技术》论文排版模版.doc",
             "659302f9924313f843262ea82804b3405924691bf8b4b526924b5a56d4e6c1ec", 81570, "official_submission_template")
EMT_GUIDE = origin("emt-2026-author-instructions.docx", "http://emt.cnjournals.com/uploadfile/news_images/emt/2026-01-15/电子测量技术-投稿须知.docx",
                   "28b054738ea52afc5e44beeb85b351269bde2d2d93d31b78a828fc8c77b1929a", 25245, "official_author_instructions")


def entry(name, sources, rules, page, locators, sections=None, policies=()):
    return {"name": name, "aliases": [name.split("，")[0]], "source_version": "official-download-snapshot-2026-10-30",
            "scope": "中文研究论文投稿；按官方模板中已确认的段落格式与页面要求执行。",
            "sources": sources, "rules": rules, "page": page, "locators": locators,
            "sections": sections, "policies": list(policies)}


def policy(identity, target, prop, expected, locator, source_index=0, detail=""):
    return {"id": identity, "target": target, "property": prop, "expected": expected,
            "locator": locator, "source_index": source_index, "checking": "host", "detail": detail}


DOCUMENTS = {
    "cn-aroc-official-word": entry(
        "计算机应用研究，官方投稿编辑模板", [AROC, AROC_INDEX],
        {"title": {"east_asia_font": "黑体", "size_pt": 16.0, "alignment": "center"},
         "body": {"font": "Times New Roman", "east_asia_font": "宋体", "size_pt": 9.0, "alignment": "justify", "first_line_pt": 18.2},
         "abstract": {"size_pt": 9.0}, "keywords": {"size_pt": 9.0}},
        {"width_mm": 210.0086, "height_mm": 297.0036, "margin_top_mm": 20.0025,
         "margin_bottom_mm": 14.9931, "margin_left_mm": 14.9931, "margin_right_mm": 14.9931},
        {"title": "Official DOC read-only Word OOXML projection: body paragraph 1, Chinese title; size 16pt and 黑体, centered",
         "body": "Official DOC read-only Word OOXML projection: body paragraph 19, anchor 本模板中正文文本的样式为; named style @正文|段落文本 resolves 9pt 宋体/Times New Roman, firstLine=364 twips",
         "abstract": "Official DOC read-only Word OOXML projection: body paragraphs 4 and 10, Chinese and English abstract have 9pt text",
         "keywords": "Official DOC read-only Word OOXML projection: body paragraphs 5 and 11, Chinese and English keywords have 9pt text",
         "page": "Official DOC read-only Word OOXML projection: word/document.xml body section 2; pgSz 11906x16838 twips; pgMar top=1134, other edges=850",
         "sections": "Official DOC read-only Word OOXML projection: front section 1 one column,正文 section 2 cols/@num=2; body begins at first level-one heading"},
        {"front_matter_columns": 1, "body_columns": 2, "body_starts_at": "first_heading1"},
        [policy("inline-figures", "image", "placement", "inline_with_text", "Template page paragraph 对于文档中的图表; explicit 图片版式设为嵌入到文字", 1),
         policy("citation-order", "reference", "bibliography_style", "numeric", "Official DOC projection paragraph 47, explicit 顺序编码制 and half-width square brackets")]),
    "cn-jcyyy-official-word": entry(
        "机床与液压，2023官方论文投稿模板", [HYDRA, HYDRA_INDEX],
        {"title": {"east_asia_font": "宋体", "size_pt": 16.0, "bold": True, "alignment": "center"},
         "body": {"font": "Times New Roman", "east_asia_font": "宋体", "size_pt": 10.5, "line_spacing_rule": "auto", "line_spacing": 1.2},
         "heading1": {"east_asia_font": "黑体", "size_pt": 10.5, "alignment": "left"},
         "heading3": {"east_asia_font": "宋体", "size_pt": 10.5},
         "figure_caption": {"east_asia_font": "宋体", "size_pt": 9.0, "alignment": "center"}},
        {"width_mm": 210.0, "height_mm": 297.0},
        {"title": "word/document.xml body paragraph 2, explicit 三号宋体，加粗，居中",
         "body": "word/document.xml body paragraph 1, explicit 全文汉字宋体/西文Times New Roman/1.2倍; paragraphs 34,39,47,60,67 specify 五号宋体 for normal text",
         "heading1": "word/document.xml body paragraph 22, explicit 五号黑体，顶格，一级标题",
         "heading3": "word/document.xml body paragraphs 39 and 47, numbered third-level headings, explicit 五号宋体",
         "figure_caption": "word/document.xml body paragraphs 72,81,87,93,171, explicit 小五号宋体，居中",
         "page": "Official template index paragraph 页面要求：A4纸", "page_source_index": 1},
        policies=[policy("margin-ui-preset", "page", "word_margin_preset", "适中", "word/document.xml body paragraph 1, explicit 全文页边距适中"),
                  policy("native-equations", "equation", "image_equations_allowed", False, "word/document.xml body paragraphs 1 and 60, explicit 公式不能是图片"),
                  policy("abstract-citations", "abstract", "abstract_citations_allowed", False, "word/document.xml body paragraph 9, explicit 不得使用参考文献号"),
                  policy("keyword-count", "keywords", "count_range", [3, 5], "word/document.xml body paragraph 10, explicit 3～5个词组")]),
    "cn-xddzjs-official-word": entry(
        "现代电子技术，2025官方研究论文投稿模板", [MODERN, MODERN_INDEX],
        {"title": {"east_asia_font": "黑体", "size_pt": 16.0, "alignment": "center"},
         "body": {"font": "Times New Roman", "east_asia_font": "宋体", "size_pt": 10.5, "line_spacing_rule": "auto", "line_spacing": 1.5},
         "heading1": {"east_asia_font": "黑体", "size_pt": 12.0},
         "heading2": {"east_asia_font": "黑体", "size_pt": 10.5},
         "heading3": {"east_asia_font": "楷体", "size_pt": 10.5},
         "abstract": {"size_pt": 9.0}, "keywords": {"size_pt": 9.0},
         "figure_caption": {"east_asia_font": "黑体", "size_pt": 9.0},
         "table_caption": {"east_asia_font": "黑体", "size_pt": 9.0}},
        {"width_mm": 210.0, "height_mm": 297.0, "margin_top_mm": 20.0, "margin_bottom_mm": 20.0,
         "margin_left_mm": 20.0, "margin_right_mm": 20.0},
        {"title": "word/document.xml body paragraph 1, explicit 中文标题（三号黑体） and centered title alignment",
         "body": "word/document.xml body paragraph 22, explicit 五号宋体/英文及数字Times New Roman/正文文本1.5倍行距",
         "heading1": "word/document.xml body paragraph 31, explicit 一级标题（小四号黑体）",
         "heading2": "word/document.xml body paragraph 32, explicit 二级标题（五号黑体）",
         "heading3": "word/document.xml body paragraph 33, explicit 三级标题（五号楷体）",
         "abstract": "word/document.xml body paragraphs 9 and 17, explicit Chinese and English abstract 小五",
         "keywords": "word/document.xml body paragraphs 10 and 18, explicit Chinese and English keywords 小五",
         "figure_caption": "word/document.xml body paragraph 68, explicit 图题采用小五黑体",
         "table_caption": "word/document.xml body paragraph 84, explicit 表题采用小五黑体",
         "page": "word/document.xml body paragraph 22, explicit A4（21cm×29.7cm）and 页边距上下左右均为2cm; use this instruction, not instruction-document container margins",
         "sections": "word/document.xml body paragraphs 21 and 22: 从正文内容开始设置为双栏; 页眉页脚设置首页不同、奇偶页不同"},
        {"front_matter_columns": 1, "body_columns": 2, "body_starts_at": "first_heading1",
         "different_first_page": True, "different_odd_even_headers": True},
        [policy("abstract-length", "abstract", "minimum_characters", 300, "word/document.xml body paragraph 9, explicit 中文摘要篇幅不少于300字"),
         policy("keyword-count", "keywords", "count_range", [6, 8], "word/document.xml body paragraphs 10 and 18, explicit 6~8个"),
         policy("keyword-separator", "keywords", "separator", "；", "word/document.xml body paragraphs 10 and 18, explicit 以分号分隔"),
         policy("equation-point-size", "equation", "math_size_pt", 10.0, "word/document.xml body paragraph 61, explicit 公式字号10磅"),
         policy("figure-inline-width", "image", "single_column_max_width_mm", 80.0, "word/document.xml body paragraph 67, explicit 占用半栏时宽度不超过80mm"),
         policy("figure-spanning-width", "image", "spanning_max_width_mm", 160.0, "word/document.xml body paragraph 67, explicit 通栏时宽度不超过160mm"),
         policy("table-no-diagonal", "table", "diagonal_header_allowed", False, "word/document.xml body paragraph 24, explicit 表格中的表头不能出现斜线"),
         policy("citation-order", "reference", "bibliography_style", "numeric", "word/document.xml body paragraph 30, explicit 先后顺序用阿拉伯数字连续编码")]),
    "cn-emt-official-word": entry(
        "电子测量技术，官方研究论文排版模板及2026须知", [EMT, EMT_GUIDE],
        {"title": {"east_asia_font": "黑体", "size_pt": 22.0, "alignment": "center"},
         "body": {"font": "Times New Roman", "east_asia_font": "宋体", "size_pt": 9.5, "line_spacing_rule": "auto", "line_spacing": 1.0},
         "abstract": {"size_pt": 9.0},
         "reference": {"east_asia_font": "宋体", "size_pt": 9.0}},
        {"width_mm": 210.0086, "height_mm": 297.0036, "margin_top_mm": 25.4, "margin_bottom_mm": 25.4,
         "margin_left_mm": 17.004, "margin_right_mm": 17.004},
        {"title": "Official DOC read-only Word OOXML projection: title paragraph 1, explicit 2号黑体，居中; actual title run 22pt",
         "body": "Official DOC read-only Word OOXML projection: paragraph 65 contains 9.5磅宋体，正文; paragraph 27 states 英文部分均为Times New Roman; paragraph 125 states 所有正文为单倍行距",
         "abstract": "Official DOC read-only Word OOXML projection: paragraph 20, explicit 小5号宋体; actual abstract text 9pt",
         "reference": "Official DOC read-only Word OOXML projection: bibliography paragraph 110, explicit 小5号宋体 and actual 9pt text",
         "page": "Official DOC read-only Word OOXML projection: body section 2 pgSz 11906x16838 twips, pgMar top/bottom1440, left/right964",
         "sections": "Official DOC projection front section 1 is single-column and body section 2 cols/@num=2; 2026 author guide paragraph 36 also explicitly requires body double columns"},
        {"front_matter_columns": 1, "body_columns": 2, "body_starts_at": "first_heading1"},
        [policy("heading-numbering", "heading1", "numbering_system", "1 / 1.1 / 1.1.1", "2026 author instructions paragraph 46, explicit hierarchical Arabic numbering and left alignment", 1),
         policy("structured-abstract", "abstract", "required_elements", ["目的", "方法", "结果", "结论"], "2026 author instructions paragraph 28, research-article abstract has four elements", 1),
         policy("references-minimum", "reference", "minimum_count", 15, "2026 author instructions paragraph 66, explicit 研究论文参考文献不少于15条", 1),
         policy("citation-order", "reference", "bibliography_style", "numeric", "2026 author instructions paragraph 66, explicit 顺序编码", 1),
         policy("table-form", "table", "structure", "three_line", "2026 author instructions paragraph 50, explicit 使用三线表", 1)])
}


def build():
    facts = {"retrieved_at": DATE,
             "method": "Read explicit official submission instructions and native template styles. Original DOC downloads were opened read-only with macros disabled and converted in a temporary Word workspace for XML inspection; no publisher originals are redistributed.",
             "documents": DOCUMENTS}
    (HERE / "source-facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (HERE / "profiles").mkdir(exist_ok=True)
    for identity, fact in DOCUMENTS.items():
        requirements = []

        def add(identity, target, prop, expected, locator, source_index=0, checking="xml", detail=""):
            source = fact["sources"][source_index]
            requirements.append({"id": identity, "category": "typography" if target not in {"page", "sections"} else "layout",
                                 "target": target, "property": prop, "expected": expected,
                                 "unit": "pt" if prop.endswith("_pt") else "mm" if prop.endswith("_mm") else None,
                                 "source": {"url": source["url"], "file": source["file"], "locator": locator},
                                 "certainty": "verified", "checking": checking, "applies_to": ["docx"], "detail": detail})

        for role, properties in fact["rules"].items():
            for prop, value in properties.items():
                add(f"{role}-{prop}", role, prop, value, fact["locators"][role])
        for prop, value in fact["page"].items():
            add("page-" + prop, "page", prop, value, fact["locators"]["page"], fact["locators"].get("page_source_index", 0))
        for prop, value in (fact["sections"] or {}).items():
            add("sections-" + prop, "sections", prop, value, fact["locators"]["sections"])
        for item in fact["policies"]:
            add(item["id"], item["target"], item["property"], item["expected"], item["locator"],
                item["source_index"], item["checking"], item["detail"])
        profile = {"id": identity, "name": fact["name"], "version": "1.0.0", "scope": fact["scope"],
                   "aliases": fact["aliases"], "compliance": "source_backed_template_partial_coverage",
                   "rules": fact["rules"], "page": fact["page"], "latex": {},
                   "sources": [{**source, "source_verified": True, "submission_compliance_verified": False} for source in fact["sources"]],
                   "checks": [{"role": role, "property": prop, "expected": value} for role, properties in fact["rules"].items() for prop, value in properties.items()],
                   "template": {"family": "chinese-engineering", "source_version": fact["source_version"],
                                "license": "rules_only_source_not_redistributed", "source_url": fact["sources"][0]["url"],
                                "assets": [], "engine_support": {"docx": "partial", "latex": "unsupported"},
                                "requirements": requirements, "coverage_notes": [
                                    "仅执行本配置列出的、来源已确认的官方投稿格式与规则。",
                                    "原始投稿模板和指南仅用于核对事实，未随项目再分发。",
                                    "字体字号与页面几何检查、实际页面审查、内容义务检查分别记录。"]}}
        if fact["sections"]:
            profile["sections"] = fact["sections"]
        (HERE / "profiles" / (identity + ".json")).write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    build()
    print("Built four official-source Chinese engineering submission profiles")
