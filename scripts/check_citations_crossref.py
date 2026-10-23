#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""check_citations_crossref.py —— 用 Crossref 机器核对「方法论依据」段的引文（纯标准库）

为什么需要它：50 个技能是并行写出来的，引文里的**年份/期刊/卷期/页码**
最容易张冠李戴。逐条肉眼看不出来，也不可复跑。
本脚本对每条引文查 Crossref，**只报矛盾，不报缺失**：

- 查到**同标题**的记录，但年份/第一作者/期刊/卷/页码对不上 → **矛盾**，可判定为错
- Crossref **查不到** → 只进「未收录」清单，不判错
  （Crossref 对 JCOL / JDE / EPP / Higher Education 等教育类期刊收录不全，
   查不到 ≠ 引文不存在。拿「缺失」当错误会制造大量假阳性）

    python scripts/check_citations_crossref.py            # 全量核对
    python scripts/check_citations_crossref.py --report   # 只出报告不改文件

退出码：0 = 无矛盾；1 = 有矛盾。
"""
from __future__ import annotations

import argparse
import difflib
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")
MANIFEST = os.path.join(ROOT, "references", "rewrite-manifest.json")
CACHE = os.path.join(ROOT, ".cache", "crossref")

CROSSREF = "https://api.crossref.org/works"
UA = "jfa-citation-audit/1.0 (local verification script)"
TITLE_SIM = 0.86


# ── 引文解析 ────────────────────────────────────────────────
# 🔴 姓氏字符类必须是 **Unicode 字母**而不是 [A-Za-z]：
#    "Merriënboer" 里的 ë 会让 [A-Za-z] 匹配失败，正则会跳过去抓第二作者，
#    把 "van Merriënboer & Sweller" 判成第一作者 Sweller —— 假阳性。
AUTHOR_RE = re.compile(r"([^\W\d_][\w'’\-]*),\s+([A-Z])\.")


def parse_citation(line):
    """把一行引文解析成 dict；解析不出来返回 None。"""
    s = line.strip()
    s = re.sub(r"^[-*·]\s*", "", s)
    s = re.split(r"\s+——\s+", s)[0].strip()          # 去掉"—— 备注"
    if not s:
        return None
    m = re.search(r"\((19|20)\d{2}\)", s)
    if not m:
        return None
    year = int(m.group(0)[1:-1])
    authors_part = s[:m.start()].strip().rstrip(",").strip()
    rest = s[m.end():].strip()
    # 🔴 `(2006).` 后面的句点必须剥掉 —— 不剥的话 title 会带上前导 ". "，
    #    后面所有按标题比对的判据全部失准（第一版就是这么漏掉 Nicol 的）。
    if rest.startswith("."):
        rest = rest[1:].strip()
    if not rest:
        return None
    authors = [(a.group(1), a.group(2))
               for a in AUTHOR_RE.finditer(authors_part)]
    # 机构作者（AERA / UNESCO / CAST / Council for Higher Education Assessment…）
    # 没有「Surname, X.」形式 —— 仍然可以核对标题/期刊/卷/页，只是不做作者比对。
    if not authors:
        authors = []

    kind = "article"
    title = journal = volume = issue = pages = publisher = None

    if rest.startswith("*"):
        # 专著：*Title*. Publisher.
        e = rest.find("*", 1)
        if e < 0:
            return None
        title = rest[1:e].strip()
        publisher = rest[e + 1:].strip().lstrip(".").strip()
        kind = "book"
    else:
        # 标题可能以 ? 或 ! 结尾（"…What makes an assessment formative?"），
        # 这时期刊前不是 ". *" 而是 "? *" —— 漏了这一种就会整条解析失败。
        j = -1
        for sep in (". *", "? *", "! *"):
            k = rest.find(sep)
            if k >= 0 and (j < 0 or k < j):
                j = k
        if j < 0:
            j = rest.find(". ")
            if j < 0:
                return None
            title = rest[:j].strip()
            tail = rest[j + 1:].strip()
        else:
            title = rest[:j].strip()
            tail = rest[j + 1:].strip()
            if tail.startswith("*"):
                e = tail.find("*", 1)
                if e < 0:
                    return None
                journal = tail[1:e].strip()
                tail = tail[e + 1:].strip()
                # 期刊名后面的 ", 31(2), 199-218." —— 逗号必须剥掉，
                # 否则下面的「卷/期/页」正则匹配不上，页码锚定整条失效。
                tail = tail.lstrip(",").strip()
        vm = re.match(r"(\d+)\s*(?:\((\d+[^)]*)\))?\s*,\s*([0-9ivxlcdm]+(?:\s*[–\-]\s*[0-9ivxlcdm]+)?)",
                      tail)
        if vm:
            volume = vm.group(1)
            issue = vm.group(2)
            pages = vm.group(3).strip()
        elif re.match(r"^\d+", tail):
            volume = re.match(r"^(\d+)", tail).group(1)

    if not title:
        return None
    return {
        "raw": s, "year": year, "authors": authors, "title": title,
        "journal": journal, "volume": volume, "issue": issue,
        "pages": pages, "publisher": publisher, "kind": kind,
        "first_author": authors[0][0] if authors else "",
        "first_initial": authors[0][1] if authors else "",
    }


def norm_title(t):
    t = re.sub(r"[*_\-–—:;,.]", " ", t.lower())
    return re.sub(r"\s+", " ", t).strip()


def norm_pages(p):
    if not p:
        return None
    p = p.replace("–", "-").replace(" ", "")
    return p.lower()


def page_num(p):
    """把 '741-749' / '293-315' 之类转成 (start, end)。"""
    if not p:
        return None
    p = p.replace("–", "-").replace(" ", "")
    m = re.match(r"^(\d+)-(\d+)$", p)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    m = re.match(r"^(\d+)$", p)
    if m:
        return (int(m.group(1)), int(m.group(1)))
    return None


# ── Crossref ───────────────────────────────────────────────
def fetch(title, author, year, rows=8):
    os.makedirs(CACHE, exist_ok=True)
    key = re.sub(r"[^a-z0-9]+", "_", (title + "|" + author + "|" + str(year)).lower())
    key = key[:120] + "_r%d" % rows
    cp = os.path.join(CACHE, key + ".json")
    if os.path.exists(cp):
        try:
            with open(cp, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    q = urllib.parse.urlencode({
        "query.bibliographic": "%s %s %s" % (title, author or "", year),
        "rows": rows,
    })
    url = CROSSREF + "?" + q
    data = None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        items = data.get("message", {}).get("items", [])
        data = [{"title": (it.get("title") or [""])[0],
                 "container": (it.get("container-title") or [""])[0],
                 "volume": it.get("volume"), "issue": it.get("issue"),
                 "page": it.get("page"), "year": ((it.get("issued") or
                          {}).get("date-parts") or [[None]])[0][0],
                 "authors": [(a.get("family", ""), (a.get("given") or "")[:1])
                             for a in (it.get("author") or [])],
                 "doi": it.get("DOI")} for it in items]
    except Exception as e:
        data = {"_error": str(e)}
    try:
        with open(cp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass
    time.sleep(0.25)
    return data


def norm_journal(j):
    """期刊名归一化：HTML 实体、and/& 写法、前导 the —— 期刊改名不算错。"""
    j = html.unescape(j or "").lower()
    j = re.sub(r"\band\b", "&", j)
    j = re.sub(r"^the\s+", "", j)
    return re.sub(r"[^a-z0-9]", "", j)


def journal_equal(cit, rec):
    cj, rj = norm_journal(cit["journal"]), norm_journal(rec.get("container"))
    if not cj or not rj:
        return False
    if cj == rj:
        return True
    # 期刊改名（如 Assessment in Education: Principles, Policy & Practice →
    # Assessment in Education）算同一个刊，不判错
    return cj in rj or rj in cj


def norm_surname(s):
    """姓氏归一化：剥掉前缀小粒子（van / von / de / der / ter / la / le）。

    「van Merriënboer」在 Crossref 里 family 字段是带粒子的整串，
    而引文里正则只能抓到 "Merriënboer"（因为粒子是小写开头），
    不归一化就会把同一个作者判成两个人。
    """
    s = (s or "").lower().strip()
    s = re.sub(r"^(van|von|de|der|den|ter|la|le|di|da|el|bin|ibn)\s+", "", s)
    return s


def compare(cit, rec):
    """返回（硬矛盾列表, 疑似列表）；不是同一篇论文返回 (None, None)。

    🔴 判据要分两层 —— 第一版把「期刊改名」「Crossref 的 online-first 年份」
    「标题近似匹配到另一篇文献」全当成错，134 条里大半是噪声。
      **硬矛盾**：作者首字母不符 / 页码与卷号同时不符 / 期刊同名但首作者不符
      **疑似**：年份差 > 2 年 / 期刊名不同 / 卷号不同 —— 可能引了同一篇的
                另一个版本（online-first vs 印次），需要人工判一次
    年份 ±2 年的差 **不报** —— Crossref 记的是 online-first 日期，与印次年份
    常差 1–2 年，报出来全是噪声。
    """
    ct = norm_title(cit["title"])
    rt = norm_title(rec.get("title") or "")
    ratio = difflib.SequenceMatcher(None, ct, rt).ratio() if (ct and rt) else 0.0
    if ratio < 0.55:
        return None, None               # 标题对不上 → 不是同一篇，不判
    hard, soft = [], []
    ra = rec.get("authors") or []
    vol_same = bool(cit["volume"] and rec.get("volume")
                    and cit["volume"] == rec["volume"])
    cp = page_num(norm_pages(cit["pages"]))
    rp = page_num(norm_pages(rec.get("page")))

    # 🔴 **不使用** Crossref 的 `given` 字段去判作者首字母 ——
    #    实测 Crossref 的 given 字段经常缺失或错位（Adesope 2017 那条把
    #    三位作者的首字母全记错了），拿它判错会产生假阳性。
    #    作者首字母的正确判据是**全仓跨技能一致性**（verify_repo 的
    #    check_citations：同一作者在不同技能里不能有两个首字母），
    #    那条查出来的才是真错。
    # ── 期刊同名、卷号页码一致，但第一作者不同 = 引错了人 ──
    if ra and ra[0][0] and journal_equal(cit, rec) and vol_same and cp and rp and cp == rp:
        if norm_surname(ra[0][0]) != norm_surname(cit["first_author"]):
            hard.append("第一作者 %s ≠ Crossref %s"
                        % (cit["first_author"], ra[0][0]))

    # ── 卷号与页码同时不符 = 引到了同一标题的另一版本/另一篇 ──
    if ratio >= 0.90 and cit["volume"] and rec.get("volume") and not vol_same:
        if cp and rp and cp != rp:
            soft.append("卷 %s/页 %s ≠ Crossref 卷 %s/页 %s"
                        % (cit["volume"], cit["pages"],
                           rec.get("volume"), rec.get("page")))
    # ── 页码：只比**首页** ──
    #    Crossref 对老文献常只存起始页（Topping 1998 只有 "249"），
    #    尾页对不上不等于错；但**首页**对不上一定是引错了。
    if ratio >= 0.90 and vol_same and cp and rp:
        if cp[0] != rp[0]:
            hard.append("起始页 %s ≠ Crossref %s（卷号同为 %s）"
                        % (cit["pages"], rec.get("page"), cit["volume"]))
        elif cp[1] != rp[1]:
            soft.append("尾页 %s ≠ Crossref %s" % (cit["pages"], rec.get("page")))
    # ── 年份差 > 2 年：疑似（online-first 与印次之差通常 ≤2 年）──
    if ratio >= 0.90 and cit["year"] and rec.get("year"):
        d = abs(cit["year"] - rec["year"])
        if d > 2:
            soft.append("年份 %s ≠ Crossref %s" % (cit["year"], rec["year"]))
    # ── 期刊名不同（归一化后仍不同、也不是互为子串）= 疑似 ──
    if ratio >= 0.90 and cit["journal"] and rec.get("container"):
        if not journal_equal(cit, rec):
            soft.append("期刊 %s ≠ Crossref %s"
                        % (cit["journal"], rec["container"]))
    return hard, soft


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="只打印，不写文件")
    ap.add_argument("--out", default="", help="把报告写到该文件（UTF-8）")
    args = ap.parse_args()

    with open(MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f).get("skills", {})

    contradictions, unresolved, unparsed = [], [], []
    total = 0
    for name in sorted(manifest):
        p = os.path.join(SKILLS, name, "SKILL.md")
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            txt = f.read()
        i = txt.find("## 方法论依据")
        if i < 0:
            continue
        sec = txt[i:]
        for line in sec.splitlines():
            if not line.strip().startswith("-"):
                continue
            cit = parse_citation(line)
            if not cit:
                if re.search(r"\((19|20)\d{2}\)", line):
                    unparsed.append((name, line.strip()))
                continue
            total += 1
            res = fetch(cit["title"], cit["first_author"], cit["year"])
            if isinstance(res, dict) and "_error" in res:
                unresolved.append((name, cit["raw"], "查询失败: " + res["_error"]))
                continue
            # 🔴 Crossref 常把同一篇文章的**书章/会议版**也收录进来，
            #    只按标题匹配会挑中它 → 制造大面积假阳性。
            #    正确做法：优先用**期刊同名**的那条记录来比对；
            #    没有期刊同名记录时，才退回按标题匹配的第一条。
            cands = []
            for rec in res:
                hard, soft = compare(cit, rec)
                if hard or soft:
                    cands.append((rec, hard, soft))
            if cands:
                jc = [c for c in cands if journal_equal(cit, c[0])]
                rec, hard, soft = (jc or cands)[0]
                contradictions.append((name, cit, rec, hard, soft))
            else:
                unresolved.append((name, cit["raw"], "Crossref 未收录或未发现冲突"))

    out = []
    out.append("共解析引文 %d 条。" % total)
    n_hard = sum(1 for c in contradictions if c[3])
    out.append("硬矛盾 %d 条 / 含疑似 %d 条 / 未收录或未发现冲突 %d 条 / 无法解析 %d 条\n"
               % (n_hard, len(contradictions), len(unresolved), len(unparsed)))

    if contradictions:
        out.append("=== 硬矛盾（确定引错，必须改）===")
        for name, cit, rec, hard, soft in contradictions:
            if not hard:
                continue
            out.append("\n[%s] %s" % (name, cit["raw"][:190]))
            out.append("    Crossref: %s | %s %s(%s) %s | %s"
                       % (rec["title"], rec.get("container"), rec.get("volume"),
                          rec.get("issue"), rec.get("page"), rec.get("year")))
            for i in hard:
                out.append("    ✗ " + i)

        out.append("\n=== 疑似（需人工判一次：可能是同一篇的另一版本）===")
        for name, cit, rec, hard, soft in contradictions:
            if not soft:
                continue
            out.append("\n[%s] %s" % (name, cit["raw"][:190]))
            out.append("    Crossref: %s | %s %s(%s) %s | %s"
                       % (rec["title"], rec.get("container"), rec.get("volume"),
                          rec.get("issue"), rec.get("page"), rec.get("year")))
            for i in soft:
                out.append("    ? " + i)

    if unresolved:
        out.append("\n=== 未收录 / 未发现冲突（不判错）===")
        for name, raw, why in unresolved:
            out.append("  [%s] %s" % (name, raw[:150]))
    if unparsed:
        out.append("\n=== 无法解析的引文行 ===")
        for name, raw in unparsed:
            out.append("  [%s] %s" % (name, raw[:190]))

    text = "\n".join(out)
    if args.out:
        p = args.out if os.path.isabs(args.out) else os.path.join(ROOT, args.out)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(text + "\n")
        print("报告已写入 %s" % p)
    else:
        print(text)
    return 1 if n_hard else 0


if __name__ == "__main__":
    sys.exit(main())
