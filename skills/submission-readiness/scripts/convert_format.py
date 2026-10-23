#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""convert_format.py — 格式转换（pandoc 包装器）。

用法::

    python convert_format.py --check
    python convert_format.py --input paper/main.md --output paper/main.docx --format docx
    python convert_format.py --input paper/main.md --output paper/main.tex --format latex --template tpl.tex
    python convert_format.py --input paper/main.md --output paper/main.pdf --format pdf
    python convert_format.py --selftest

退出码::

    0 = 成功
    1 = 转换失败（pandoc 返回非 0，或产物未生成）
    2 = 用法错误或运行故障（含 pandoc 未安装、输入/输出路径不合法）

设计约束::

    * 仅使用标准库（shutil / subprocess / argparse），不依赖 pypandoc 等第三方包
    * Python 3.9 兼容（f-string 表达式内不出现反斜杠）
"""

import argparse
import io
import os
import shutil
import subprocess
import sys

FORMAT_MAP = {
    "docx": "docx",
    "latex": "latex",
    "tex": "latex",
    "pdf": "pdf",
    "md": "markdown",
    "markdown": "markdown",
    "html": "html",
}

EXPECTED_EXT = {
    "docx": ".docx",
    "latex": ".tex",
    "pdf": ".pdf",
    "md": ".md",
    "html": ".html",
}

PANDOC_MISSING_MSG = """未检测到 pandoc（文档格式转换工具）。

本脚本只是 pandoc 的包装器，缺少 pandoc 时无法完成转换。可选方案：
  1) 安装 pandoc 后重试：
     - Windows：winget install --id JohnMacFarlane.Pandoc
     - macOS：brew install pandoc
     - Debian/Ubuntu：apt install pandoc
  2) 改用 Word 手工粘贴：用 Word 打开源文件 → 另存为 → 选择目标格式
     （Word 可直接导出 .docx 与 .pdf，中文排版最稳）。
  3) 改用 LaTeX 路线：先用本工具导出 .tex，再本地用 XeLaTeX 编译中文 PDF。
  4) 先运行 `--check` 确认环境，再执行转换。

注意：各期刊对文件格式（DOCX/LaTeX/模板）的具体要求需自行查目标期刊官网。"""


class PandocMissing(Exception):
    """pandoc 不在 PATH 中。"""

    def __init__(self, message):
        Exception.__init__(self, message)
        self.message = message


def resolve_pandoc():
    """返回 pandoc 可执行文件路径；找不到则抛 PandocMissing。"""
    path = shutil.which("pandoc")
    if not path:
        raise PandocMissing(PANDOC_MISSING_MSG)
    return path


def build_command(pandoc_path, input_path, output_path, fmt, template=None):
    """组装 pandoc 命令行（不执行）。"""
    target = FORMAT_MAP[fmt]
    cmd = [pandoc_path, input_path, "-t", target, "-o", output_path]
    if template:
        if target == "docx" and template.lower().endswith(".docx"):
            cmd += ["--reference-doc", template]
        else:
            cmd += ["--template", template]
    return cmd


def run_conversion(cmd):
    """执行 pandoc。返回 (退出码, 输出文本)。"""
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        return 2, "无法启动 pandoc：{0}".format(exc)
    out = proc.stdout.decode("utf-8", "replace").strip()
    err = proc.stderr.decode("utf-8", "replace").strip()
    if proc.returncode != 0:
        return 1, ("pandoc 转换失败（退出码 {0}）。\n--- pandoc stderr ---\n{1}".format(
            proc.returncode, err if err else "（pandoc 未输出错误信息）"))
    return 0, out


def check_environment():
    """探测 pandoc 是否可用。返回 (退出码, 文本)。"""
    try:
        path = resolve_pandoc()
    except PandocMissing as exc:
        return 2, exc.message
    try:
        proc = subprocess.run([path, "--version"], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
        version = proc.stdout.decode("utf-8", "replace").splitlines()
        first = version[0] if version else "（未取得版本信息）"
    except OSError as exc:
        return 2, "检测到 pandoc：{0}，但无法执行：{1}".format(path, exc)
    return 0, "pandoc 可用：{0}\n版本：{1}".format(path, first)


def build_parser():
    p = argparse.ArgumentParser(
        prog="convert_format.py",
        description="格式转换（pandoc 包装器）：docx / latex / pdf。"
                    "各期刊对格式的具体要求请自行查目标期刊官网。")
    p.add_argument("--input", help="输入文件（如 main.md / main.docx）")
    p.add_argument("--output", help="输出文件（如 main.docx / main.tex / main.pdf）")
    p.add_argument("--format", choices=sorted(FORMAT_MAP.keys()),
                   help="目标格式：docx / latex / pdf（另有 md / html 别名）")
    p.add_argument("--template", help="模板文件（latex/pdf 用 --template；"
                                      "docx 的 .docx 参考模板用 --reference-doc）")
    p.add_argument("--check", action="store_true",
                   help="只探测 pandoc 是否可用，不做转换")
    p.add_argument("--selftest", action="store_true", help="运行离线自检（不调用 pandoc）")
    return p


def selftest():
    checks = []

    def ck(name, cond, detail=""):
        checks.append((name, bool(cond), detail))

    parser = build_parser()

    # 1) 参数解析
    args = parser.parse_args(["--input", "a.md", "--output", "a.docx",
                               "--format", "docx"])
    ck("参数解析正常",
       args.input == "a.md" and args.output == "a.docx" and args.format == "docx")

    # 2) 命令组装
    cmd = build_command("pandoc", "a.md", "a.docx", "docx")
    ck("命令含输入输出与目标格式",
       "a.md" in cmd and "a.docx" in cmd and "docx" in cmd, str(cmd))
    cmd_tpl = build_command("pandoc", "a.md", "a.tex", "latex", "tpl.tex")
    ck("latex 模板走 --template", "--template" in cmd_tpl, str(cmd_tpl))
    cmd_ref = build_command("pandoc", "a.md", "a.docx", "docx", "ref.docx")
    ck("docx 参考模板走 --reference-doc", "--reference-doc" in cmd_ref, str(cmd_ref))
    ck("格式别名映射正确",
       FORMAT_MAP["tex"] == "latex" and FORMAT_MAP["markdown"] == "markdown")

    # 3) pandoc 缺失分支（离线模拟）
    real_which = shutil.which
    try:
        shutil.which = lambda name: None
        try:
            resolve_pandoc()
            ck("缺失时抛出 PandocMissing", False, "未抛异常")
        except PandocMissing as exc:
            ck("缺失时抛出 PandocMissing", True)
            ck("缺失提示含替代方案",
               "Word" in exc.message and "pandoc" in exc.message)
        code, text = check_environment()
        ck("check 在缺失时返回 2", code == 2, str(code))
    finally:
        shutil.which = real_which

    # 4) 转换成功 / 失败分支（离线模拟 subprocess）
    real_run = subprocess.run

    class FakeProc(object):
        def __init__(self, code, out=b"", err=b""):
            self.returncode = code
            self.stdout = out
            self.stderr = err

    try:
        subprocess.run = lambda *a, **k: FakeProc(0, out=b"ok\n")
        code, text = run_conversion(["pandoc", "a.md"])
        ck("成功时返回 0", code == 0, str(code))

        subprocess.run = lambda *a, **k: FakeProc(1, err="boom".encode("utf-8"))
        code, text = run_conversion(["pandoc", "a.md"])
        ck("失败时返回 1", code == 1, str(code))
        ck("失败时保留 stderr", "boom" in text, text)

        subprocess.run = lambda *a, **k: FakeProc(0)
        code, text = check_environment()
        ck("check 在可用时返回 0", code == 0, str(code))
    finally:
        subprocess.run = real_run

    # CLI 端到端（捕捉只在命令行路径出现的错误）
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        code = main(["--check"])
    finally:
        sys.stdout = old
    ck("CLI --check 可运行", code in (0, 2), str(code))
    ck("CLI --check 有输出", len(buf.getvalue().strip()) > 0)

    failed = [c for c in checks if not c[1]]
    print("convert_format selftest: {0}/{1} 通过".format(
        len(checks) - len(failed), len(checks)))
    for name, ok, detail in checks:
        print("  [{0}] {1}{2}".format("PASS" if ok else "FAIL", name,
                                     "" if ok else "  <- " + detail))
    if failed:
        print("selftest 失败：{0} 项未通过".format(len(failed)))
        return 2
    print("selftest 通过")
    return 0


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.check:
        code, text = check_environment()
        print(text)
        return code
    if not args.input or not args.output or not args.format:
        parser.print_usage(sys.stderr)
        print("错误：需要 --input、--output、--format；"
              "或使用 --check / --selftest。", file=sys.stderr)
        return 2
    if not os.path.isfile(args.input):
        print("错误：输入文件不存在：{0}".format(args.input), file=sys.stderr)
        return 2
    out_dir = os.path.dirname(os.path.abspath(args.output))
    if not os.path.isdir(out_dir):
        print("错误：输出目录不存在：{0}".format(out_dir), file=sys.stderr)
        return 2
    if args.template and not os.path.isfile(args.template):
        print("错误：模板文件不存在：{0}".format(args.template), file=sys.stderr)
        return 2

    expected = EXPECTED_EXT.get(FORMAT_MAP[args.format])
    actual = os.path.splitext(args.output)[1].lower()
    if expected and actual != expected:
        print("提示：目标格式为 {0}（通常使用 {1} 扩展名），"
              "当前输出为 {2}。".format(args.format, expected, actual))

    try:
        pandoc_path = resolve_pandoc()
    except PandocMissing as exc:
        print(exc.message, file=sys.stderr)
        return 2

    cmd = build_command(pandoc_path, args.input, args.output, args.format,
                        args.template)
    print("执行：{0}".format(" ".join(cmd)))
    code, text = run_conversion(cmd)
    if text:
        print(text, file=sys.stderr if code != 0 else sys.stdout)
    if code != 0:
        return code
    if not os.path.exists(args.output):
        print("错误：pandoc 返回成功，但产物不存在：{0}".format(args.output),
              file=sys.stderr)
        return 1
    print("完成：{0}".format(args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
