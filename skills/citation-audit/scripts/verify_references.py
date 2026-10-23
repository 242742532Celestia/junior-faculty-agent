#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""引用真实性核验：逐条检查一条参考文献是否真实存在、字段是否相符。

四档判定：
  证实 confirmed  —— 命中权威数据源，标题匹配且年份/作者相符
  存疑 suspicious  —— 命中数据源但字段存在偏差（标题相似度偏低、年份差 > 2、作者不符）
  证伪 refuted     —— 命中数据源但标题相似度 < 0.70，基本可判定不是该文献
  查不到 unknown   —— 数据源未收录或网络不可用（不等于错！）

仅使用 Python 标准库。Python 3.9 兼容。
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 15
MAX_RETRY = 3
BACKOFF_BASE = 1.5
UA = "junior-faculty-agent/citation-audit (https://github.com/; offline-friendly)"

STATUS_CONFIRMED = "证实"
STATUS_SUSPICIOUS = "存疑"
STATUS_REFUTED = "证伪"
STATUS_UNKNOWN = "查不到"

TITLE_STRONG = 0.85
TITLE_WEAK = 0.70
YEAR_TOLERANCE = 2

DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", re.IGNORECASE)
ARXIV_RE = re.compile(
    r"(?:arxiv\.org/(?:abs|pdf)/)?"
    r"((?:\d{4}\.\d{4,5})(?:v\d+)?|(?:[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?)",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"(?<!\d)(1[89]\d{2}|20\d{2})(?!\d)")


# --------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------
def normalize_title(text):
    """归一化标题：小写、去标点、压缩空白，便于比较。"""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def title_ratio(a, b):
    """标题相似度。difflib.SequenceMatcher(None, a, b).ratio()。"""
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def extract_doi(text):
    if not text:
        return None
    m = DOI_RE.search(text)
    if not m:
        return None
    doi = m.group(0).rstrip(".,;)")
    return doi


def extract_arxiv_id(text):
    if not text:
        return None
    m = ARXIV_RE.search(text)
    if not m:
        return None
    return m.group(1)


def extract_year(text):
    if not text:
        return None
    m = YEAR_RE.search(text)
    return int(m.group(1)) if m else None


def extract_title(text):
    """从一行引用文本里猜标题。

    优先取引号/书名号内文本；否则取第一个像标题的长片段。
    """
    if not text:
        return ""
    s = text.strip()
    m = re.search(r"[\"“”‘’「」『』《》]([^\"“”‘’「」『』《》]{6,})[\"“”‘’「」『』《》]", s)
    if m:
        return m.group(1).strip()
    # 常见形态："作者. 标题. 期刊, 年份."  —— 取第一段后按句点切
    parts = [p.strip() for p in re.split(r"[.。]", s) if p.strip()]
    for p in parts:
        p2 = re.sub(r"^\(?\d{1,3}\)?[\s\.,]+", "", p)
        p2 = re.sub(r"^\[[0-9]+\]\s*", "", p2)
        if len(p2) >= 15:
            return p2
    return parts[0] if parts else s


def extract_surname(text):
    """猜第一作者姓氏。

    支持 "Zhang et al." / "Zhang, W." / "Zhang W." / "（Smith, 2020）"
    """
    if not text:
        return None
    s = text.strip()
    s = re.sub(r"^\[?\d{0,3}\]?[\s\.,]*", "", s)
    s = re.sub(r"^[\(（]\s*", "", s)
    # 去掉 et al.
    s = re.sub(r"\bet\s+al\.?", "", s, flags=re.IGNORECASE)
    s = re.sub(r"等\s*$", "", s)
    # 括号内作者形式
    m = re.match(r"^([A-Za-z\u4e00-\u9fff][A-Za-z\u4e00-\u9fff'\-]*)\s*[,，]", s)
    if m:
        return m.group(1)
    # 空格分隔形式 "Zhang W."
    m = re.match(r"^([A-Za-z\u4e00-\u9fff][A-Za-z\u4e00-\u9fff'\-]*)\s", s)
    if m:
        return m.group(1)
    m = re.match(r"^([A-Za-z\u4e00-\u9fff][A-Za-z\u4e00-\u9fff'\-]*)$", s)
    if m:
        return m.group(1)
    return None


def _http_get(url, timeout=TIMEOUT):
    """带指数退避重试的 GET。返回 (status_code, body_text) 或抛出最后一次异常。"""
    last_exc = None
    for attempt in range(MAX_RETRY):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.getcode(), resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code in (429, 500, 502, 503, 504):
                time.sleep(BACKOFF_BASE ** attempt)
                continue
            raise
        except Exception as exc:  # 超时 / DNS / 连接重置
            last_exc = exc
            time.sleep(BACKOFF_BASE ** attempt)
            continue
    raise last_exc if last_exc else RuntimeError("unknown network failure")


def _json_get(url):
    """GET 并解析 JSON。失败抛异常。"""
    _, body = _http_get(url)
    return json.loads(body)


# --------------------------------------------------------------------------
# 数据源
# --------------------------------------------------------------------------
def query_crossref_doi(doi):
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    data = _json_get(url)
    msg = (data or {}).get("message") or {}
    title = " ".join(msg.get("title") or [])
    year = None
    for key in ("published-print", "published-online", "published", "issued", "created"):
        parts = ((msg.get(key) or {}).get("date-parts") or [[None]])[0]
        if parts and parts[0]:
            year = int(parts[0])
            break
    authors = []
    for a in msg.get("author") or []:
        fam = a.get("family")
        given = a.get("given")
        name = (fam or "").strip()
        if name:
            authors.append(name)
        elif given:
            authors.append(given.strip())
    venue = " ".join(msg.get("container-title") or [])
    return {
        "source": "crossref",
        "id": doi,
        "title": title,
        "year": year,
        "authors": authors,
        "venue": venue,
        "url": url,
    }


def query_crossref_title(title):
    q = urllib.parse.quote(title)
    url = (
        "https://api.crossref.org/works?query.bibliographic=" + q + "&rows=3"
    )
    data = _json_get(url)
    items = ((data or {}).get("message") or {}).get("items") or []
    out = []
    for msg in items:
        t = " ".join(msg.get("title") or [])
        year = None
        for key in ("published-print", "published-online", "published", "issued", "created"):
            parts = ((msg.get(key) or {}).get("date-parts") or [[None]])[0]
            if parts and parts[0]:
                year = int(parts[0])
                break
        authors = []
        for a in msg.get("author") or []:
            fam = (a.get("family") or "").strip()
            if fam:
                authors.append(fam)
        out.append(
            {
                "source": "crossref",
                "id": msg.get("DOI"),
                "title": t,
                "year": year,
                "authors": authors,
                "venue": " ".join(msg.get("container-title") or []),
                "url": url,
            }
        )
    return out


def query_arxiv_title(title):
    q = urllib.parse.quote('ti:"' + title.replace('"', "") + '"')
    url = "http://export.arxiv.org/api/query?search_query=" + q + "&max_results=3"
    _, body = _http_get(url)
    entries = []
    for block in re.findall(r"<entry>(.*?)</entry>", body, flags=re.DOTALL):
        t = _tag(block, "title")
        aid = _tag(block, "id")
        published = _tag(block, "published")
        year = None
        if published:
            m = re.match(r"(\d{4})", published)
            if m:
                year = int(m.group(1))
        authors = []
        for a in re.findall(r"<author>\s*<name>(.*?)</name>", block, flags=re.DOTALL):
            nm = re.sub(r"\s+", " ", a).strip()
            if nm:
                authors.append(nm.split()[-1] if " " in nm else nm)
        entries.append(
            {
                "source": "arxiv",
                "id": aid,
                "title": t,
                "year": year,
                "authors": authors,
                "venue": "arXiv preprint",
                "url": url,
            }
        )
    return entries


def query_arxiv_id(arxiv_id):
    q = urllib.parse.quote("id:" + arxiv_id)
    url = "http://export.arxiv.org/api/query?search_query=" + q + "&max_results=1"
    _, body = _http_get(url)
    blocks = re.findall(r"<entry>(.*?)</entry>", body, flags=re.DOTALL)
    if not blocks:
        return []
    block = blocks[0]
    t = _tag(block, "title")
    published = _tag(block, "published")
    year = None
    if published:
        m = re.match(r"(\d{4})", published)
        if m:
            year = int(m.group(1))
    authors = []
    for a in re.findall(r"<author>\s*<name>(.*?)</name>", block, flags=re.DOTALL):
        nm = re.sub(r"\s+", " ", a).strip()
        if nm:
            authors.append(nm.split()[-1] if " " in nm else nm)
    return [
        {
            "source": "arxiv",
            "id": _tag(block, "id"),
            "title": t,
            "year": year,
            "authors": authors,
            "venue": "arXiv preprint",
            "url": url,
        }
    ]


def _tag(block, name):
    m = re.search(
        r"<%s[^>]*>(.*?)</%s>" % (re.escape(name), re.escape(name)),
        block,
        flags=re.DOTALL,
    )
    if not m:
        return ""
    return re.sub(r"\s+", " ", m.group(1)).strip()


def query_s2_doi(doi):
    url = (
        "https://api.semanticscholar.org/graph/v1/paper/DOI:" + urllib.parse.quote(doi, safe="")
        + "?fields=title,year,authors,venue"
    )
    data = _json_get(url)
    authors = []
    for a in (data or {}).get("authors") or []:
        nm = (a.get("name") or "").strip()
        if nm:
            authors.append(nm.split()[-1] if " " in nm else nm)
    return {
        "source": "semantic_scholar",
        "id": doi,
        "title": (data or {}).get("title") or "",
        "year": (data or {}).get("year"),
        "authors": authors,
        "venue": (data or {}).get("venue") or "",
        "url": url,
    }


# --------------------------------------------------------------------------
# 判定
# --------------------------------------------------------------------------
def judge_against(candidate, ref):
    """用候选记录与引用文本比对，返回 (status, reasons, ratio)。"""
    reasons = []
    ratio = title_ratio(ref.get("title", ""), candidate.get("title", ""))
    if ratio >= TITLE_STRONG:
        status = STATUS_CONFIRMED
    elif ratio >= TITLE_WEAK:
        status = STATUS_SUSPICIOUS
        reasons.append("标题相似度 %.2f 介于 %.2f 与 %.2f 之间" % (ratio, TITLE_WEAK, TITLE_STRONG))
    else:
        status = STATUS_REFUTED
        reasons.append("标题相似度 %.2f 低于 %.2f" % (ratio, TITLE_WEAK))

    ref_year = ref.get("year")
    cand_year = candidate.get("year")
    if ref_year and cand_year:
        diff = abs(ref_year - cand_year)
        if diff > YEAR_TOLERANCE:
            status = STATUS_SUSPICIOUS if status != STATUS_REFUTED else status
            reasons.append("年份不符：引用 %d，数据源 %d（相差 %d 年）" % (ref_year, cand_year, diff))

    ref_sur = ref.get("surname")
    cand_authors = candidate.get("authors") or []
    if ref_sur and cand_authors:
        cand_sur = cand_authors[0]
        if norm_surname(ref_sur) != norm_surname(cand_sur):
            status = STATUS_SUSPICIOUS if status != STATUS_REFUTED else status
            reasons.append("作者不符：引用 %s，数据源 %s" % (ref_sur, cand_sur))
    return status, reasons, ratio


def norm_surname(name):
    if not name:
        return ""
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]", "", name.lower())


def parse_reference(text):
    """把一条引用文本解析成 ref 字典。"""
    ref = {
        "raw": text,
        "doi": extract_doi(text),
        "arxiv_id": extract_arxiv_id(text),
        "title": extract_title(text),
        "year": extract_year(text),
        "surname": extract_surname(text),
    }
    return ref


def verify_one(text, offline=False):
    """核验单条引用，返回结果字典。"""
    ref = parse_reference(text)
    candidates = []
    errors = []
    notes = []

    if offline:
        return {
            "reference": ref["raw"],
            "status": STATUS_UNKNOWN,
            "reasons": ["离线模式（--selftest / --offline）：未访问任何数据源"],
            "ratio": 0.0,
            "matched": None,
            "candidates": [],
            "notes": notes,
            "errors": errors,
        }

    # 1) DOI 直查：Crossref + Semantic Scholar
    if ref["doi"]:
        try:
            candidates.append(query_crossref_doi(ref["doi"]))
        except Exception as exc:
            errors.append("Crossref DOI 查询失败：%s" % (exc,))
        try:
            candidates.append(query_s2_doi(ref["doi"]))
        except Exception as exc:
            errors.append("Semantic Scholar DOI 查询失败：%s" % (exc,))

    # 2) arXiv ID 直查
    if not candidates and ref["arxiv_id"]:
        try:
            candidates.extend(query_arxiv_id(ref["arxiv_id"]))
        except Exception as exc:
            errors.append("arXiv ID 查询失败：%s" % (exc,))

    # 3) 标题检索：Crossref + arXiv
    if not candidates and ref["title"]:
        try:
            candidates.extend(query_crossref_title(ref["title"]))
        except Exception as exc:
            errors.append("Crossref 标题检索失败：%s" % (exc,))
        try:
            candidates.extend(query_arxiv_title(ref["title"]))
        except Exception as exc:
            errors.append("arXiv 标题检索失败：%s" % (exc,))

    if not candidates:
        notes.append(
            "数据库未收录，可能是预印本/会议论文/非英文文献；查不到不等于错"
        )
        if errors:
            notes.append("数据源访问异常：%s" % "；".join(errors))
        return {
            "reference": ref["raw"],
            "status": STATUS_UNKNOWN,
            "reasons": notes,
            "ratio": 0.0,
            "matched": None,
            "candidates": [],
            "notes": notes,
            "errors": errors,
        }

    best = None
    best_status = STATUS_UNKNOWN
    best_reasons = []
    best_ratio = 0.0
    for cand in candidates:
        status, reasons, ratio = judge_against(cand, ref)
        if best is None or ratio > best_ratio:
            best = cand
            best_status = status
            best_reasons = reasons
            best_ratio = ratio
        # 已确认即可停止
        if status == STATUS_CONFIRMED and ratio >= TITLE_STRONG:
            break

    # 多个数据源都明确指向同一结论时合并理由
    merged = list(best_reasons)
    for cand in candidates:
        if cand is best:
            continue
        st, rs, _r = judge_against(cand, ref)
        if st == best_status:
            for r in rs:
                if r not in merged:
                    merged.append(r)

    if best_status == STATUS_CONFIRMED and errors:
        merged.append("部分数据源访问异常：%s" % "；".join(errors))

    return {
        "reference": ref["raw"],
        "status": best_status,
        "reasons": merged,
        "ratio": best_ratio,
        "matched": best,
        "candidates": candidates,
        "notes": notes,
        "errors": errors,
    }


# --------------------------------------------------------------------------
# 输出
# --------------------------------------------------------------------------
def render_text(results):
    lines = []
    lines.append("=" * 68)
    lines.append("引用真实性核验报告")
    lines.append("=" * 68)
    for idx, r in enumerate(results, 1):
        lines.append("")
        lines.append("[%d] %s" % (idx, r["reference"]))
        lines.append("    判定：%s" % r["status"])
        m = r.get("matched")
        if m:
            lines.append(
                "    命中：%s | %s | %s"
                % (m.get("source"), m.get("title") or "(无标题)", m.get("id") or "(无ID)")
            )
            if m.get("year"):
                lines.append("    数据源年份：%s" % m["year"])
        else:
            lines.append("    命中：（无）")
        if r.get("ratio"):
            lines.append("    标题相似度：%.3f" % r["ratio"])
        for reason in r.get("reasons") or []:
            lines.append("    - %s" % reason)
        for err in r.get("errors") or []:
            lines.append("    ! %s" % err)
    lines.append("")
    lines.append("-" * 68)
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    summary = "，".join("%s %d 条" % (k, counts[k]) for k in
                        (STATUS_CONFIRMED, STATUS_SUSPICIOUS, STATUS_REFUTED, STATUS_UNKNOWN)
                        if counts.get(k))
    lines.append("合计 %d 条：%s" % (len(results), summary or "无"))
    lines.append("提示：「查不到」表示数据源未收录或不可用，不构成引用错误的结论。")
    lines.append("=" * 68)
    return "\n".join(lines)


def has_problem(result):
    return result["status"] in (STATUS_SUSPICIOUS, STATUS_REFUTED)


# --------------------------------------------------------------------------
# 自检（完全离线）
# --------------------------------------------------------------------------
def selftest():
    failures = []

    def check(name, cond, detail=""):
        if cond:
            print("  [PASS] %s" % name)
        else:
            print("  [FAIL] %s %s" % (name, detail))
            failures.append(name)

    print("verify_references.py 自检（离线）")

    # 解析类
    doi = extract_doi("Zhang, W. (2021). A study of X. Nature, 10.1038/nature12373.")
    check("DOI 抽取", doi == "10.1038/nature12373", "got=%r" % doi)
    aid = extract_arxiv_id("arXiv:2103.00012v2 [cs.CL]")
    check("arXiv ID 抽取", aid is not None and aid.startswith("2103.00012"), "got=%r" % aid)
    yr = extract_year("Smith, J. (2019). Title here. Some Journal.")
    check("年份抽取", yr == 2019, "got=%r" % yr)
    check("相似度完全相同为 1.0", abs(title_ratio("abc", "abc") - 1.0) < 1e-9)
    r_sim = title_ratio(
        "A deep study of photovoltaic efficiency in perovskite solar cells",
        "A deep study of photovoltaic efficiency in perovskite solar cells ",
    )
    check("归一化后尾随空格不影响", r_sim >= 0.99, "got=%.3f" % r_sim)
    r_low = title_ratio("Alpha beta gamma delta", "Totally unrelated wording here")
    check("不相关标题比值 < 0.70", r_low < TITLE_WEAK, "got=%.3f" % r_low)

    # 引用形态解析
    ref_doi = parse_reference("Smith, J. (2020). Title of work. J. Name. https://doi.org/10.1000/abc123")
    check("解析：DOI 形态", ref_doi["doi"] == "10.1000/abc123", "got=%r" % ref_doi["doi"])
    ref_yr = parse_reference("Zhang et al. (2021). Some Article Title Here. Journal of Things.")
    check("解析：作者-年份形态", ref_yr["year"] == 2021 and ref_yr["surname"] == "Zhang",
          "got=%r/%r" % (ref_yr["year"], ref_yr["surname"]))
    ref_named = parse_reference('Wang, L. (2022). "A Very Explicit Quoted Title". Nature.')
    check("解析：引号标题", "Very Explicit" in ref_named["title"], "got=%r" % ref_named["title"])

    # 判定逻辑
    cand = {
        "source": "crossref",
        "id": "10.1000/abc123",
        "title": "A Deep Study of Photovoltaic Efficiency in Perovskite Solar Cells",
        "year": 2021,
        "authors": ["Zhang"],
        "venue": "Nature",
        "url": "u",
    }
    ref_ok = {
        "title": "A deep study of photovoltaic efficiency in perovskite solar cells",
        "year": 2020,
        "surname": "Zhang",
    }
    st, reasons, ratio = judge_against(cand, ref_ok)
    check("标题匹配 + 年份差 1 + 作者一致 → 证实", st == STATUS_CONFIRMED,
          "got=%s reasons=%s" % (st, reasons))

    ref_year_bad = {"title": ref_ok["title"], "year": 2015, "surname": "Zhang"}
    st, reasons, _r = judge_against(cand, ref_year_bad)
    check("年份差 > 2 → 存疑", st == STATUS_SUSPICIOUS and any("年份不符" in x for x in reasons),
          "got=%s" % st)

    ref_auth_bad = {"title": ref_ok["title"], "year": 2021, "surname": "Li"}
    st, reasons, _r = judge_against(cand, ref_auth_bad)
    check("作者姓氏不符 → 存疑", st == STATUS_SUSPICIOUS and any("作者不符" in x for x in reasons),
          "got=%s" % st)

    cand_other = dict(cand)
    cand_other["title"] = "Quantum Chromodynamics At High Temperature"
    cand_other["authors"] = ["Zhang"]
    ref_mid = {"title": "A deep study of photovoltaic efficiency in perovskite solar cell",
               "year": 2021, "surname": "Zhang"}
    st, _reasons, _r = judge_against(cand_other, ref_mid)
    check("相似度过低 → 证伪", st == STATUS_REFUTED, "got=%s" % st)

    # 查不到 ≠ 证伪
    res = verify_one("Some, A. (2020). Never Published Anywhere At All.", offline=True)
    check("离线模式返回「查不到」而非「证伪」", res["status"] == STATUS_UNKNOWN, "got=%s" % res["status"])
    check("离线模式标注说明", bool(res["reasons"]))

    # 批量行抽取：正文散句不入选，带编号/年份/DOI 的条目入选
    sample = (
        "正文散句：已有工作表明该方法有效 [1]，另有研究提出相反结论。\n"
        "[1] Zhang, W. (2021). A Study Of Some Method Here. Journal Of Examples.\n"
        "Wang, Q. (2018). Uncited Entry Without Marker. Some Venue.\n"
        "- Li, Y. (2019). Third Reference Here. Third Venue, 3(2), 8-9.\n"
    )
    picked = extract_reference_lines(sample)
    check("批量抽取跳过正文散句", len(picked) == 3, "picked=%r" % picked)
    check("批量抽取保留带编号条目",
          any(p.startswith("[1] Zhang") for p in picked), "picked=%r" % picked)
    check("批量抽取保留带年份条目",
          any(p.startswith("Wang, Q.") for p in picked), "picked=%r" % picked)

    # 渲染
    text = render_text([res])
    check("报告含四档判定提示", "查不到" in text and "引用真实性核验报告" in text)

    # 退出码语义
    check("证实/查不到 不算问题", not has_problem({"status": STATUS_CONFIRMED})
          and not has_problem({"status": STATUS_UNKNOWN}))
    check("存疑/证伪 算问题", has_problem({"status": STATUS_SUSPICIOUS})
          and has_problem({"status": STATUS_REFUTED}))

    if failures:
        print("自检失败：%d 项未通过 -> %s" % (len(failures), ", ".join(failures)))
        return 2
    print("自检全部通过。")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv=None):
    parser = argparse.ArgumentParser(
        description="逐条核验参考文献真实性（Crossref / arXiv / Semantic Scholar）"
    )
    parser.add_argument("--reference", action="append", default=[],
                        help="一条引用文本（可重复传入）")
    parser.add_argument("--file", help="批量核验：每行一条引用（.md/.txt）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    parser.add_argument("--offline", action="store_true", help="不联网，仅做本地解析与判定")
    parser.add_argument("--selftest", action="store_true", help="运行离线自检")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    if not args.reference and not args.file:
        parser.print_usage()
        sys.stderr.write("用法错误：需要 --reference 或 --file。\n")
        return 2

    try:
        refs = list(args.reference)
        if args.file:
            refs.extend(read_reference_lines(args.file))
    except Exception as exc:
        sys.stderr.write("读取失败：%s\n" % (exc,))
        return 2

    if not refs:
        sys.stderr.write("用法错误：没有可核验的引用条目。\n")
        return 2

    results = []
    for text in refs:
        try:
            results.append(verify_one(text, offline=args.offline))
        except Exception as exc:
            results.append({
                "reference": text,
                "status": STATUS_UNKNOWN,
                "reasons": ["运行故障：%s" % (exc,)],
                "ratio": 0.0,
                "matched": None,
                "candidates": [],
                "notes": [],
                "errors": [str(exc)],
            })

    if args.json:
        sys.stdout.write(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(render_text(results) + "\n")

    if any(has_problem(r) for r in results):
        return 1
    return 0


def extract_reference_lines(text):
    """从文本中抽取候选引用行。

    只保留「像参考文献条目」的行：带编号/项目符号前缀的条目行，
    或者含年份括号、含 DOI、含 arXiv 标记的行。
    正文散句不满足这些特征，不会被误当作引用条目。
    """
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#") or line.startswith("<!--"):
            continue
        marked = False
        if re.match(r"^\|?\s*[-*]\s+", line):
            line = re.sub(r"^\|?\s*[-*]\s+", "", line).strip()
            marked = True
        if re.match(r"^\|?\s*\d{1,3}[\.\)]\s+", line):
            line = re.sub(r"^\|?\s*\d{1,3}[\.\)]\s+", "", line).strip()
            marked = True
        if len(line) < 12:
            continue
        if not re.search(r"[A-Za-z\u4e00-\u9fff]{4}", line):
            continue
        # 未带列表标记的行，必须另有明确的引用特征
        if not marked:
            has_year = re.search(r"[\(（]\s*(1[89]\d{2}|20\d{2})[a-z]?\s*[\)）]", line)
            has_doi = bool(DOI_RE.search(line))
            has_arxiv = bool(re.search(r"arxiv", line, re.IGNORECASE))
            if not (has_year or has_doi or has_arxiv):
                continue
        lines.append(line)
    return lines


def read_reference_lines(path):
    """从文件中抽取候选引用行。"""
    return extract_reference_lines(read_text_file(path))


def read_text_file(path):
    if path.lower().endswith(".docx"):
        return read_docx_text(path)
    with open(path, "r", encoding="utf-8-sig") as fh:
        return fh.read()


def read_docx_text(path):
    import zipfile
    import xml.etree.ElementTree as ET

    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs = []
    for para in root.iter(ns + "p"):
        buf = []
        for node in para.iter(ns + "t"):
            buf.append(node.text or "")
        paragraphs.append("".join(buf))
    return "\n".join(paragraphs)


if __name__ == "__main__":
    sys.exit(main())
