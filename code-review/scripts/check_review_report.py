#!/usr/bin/env python3
"""コードレビューの報告書の書式を検査する．

報告書（Markdown）を FILE から，FILE を省略するか "-" を指定した場合は標準入力
から読み込み，references/report-format.md の書式に従っているかを検査する．問題は
「エラー」（書式の要件に違反しており，必ず直すもの）と「警告」（直すことを推奨
するが，妥当な理由があれば許容できるもの）に分けて表示する．

主な検査項目:
  - 見出し「コードレビュー結果」，必須の節（概要，指摘一覧，指摘詳細，
    レビューの範囲と限界）とその順序，概要の 5 項目，件数の表の書式
  - 指摘の見出しの形式（R001【高】概要），ID の形式・重複・欠番・順序
  - 深刻度の値と並び順（高 → 中 → 低）
  - 深刻度ごとの必須項目と，確度・由来・観点の値
  - 指摘一覧と指摘詳細の一致（ID，深刻度，概要，場所），件数と判定の整合
  - 日本語で書かれているか，句読点が「，」「．」に統一されているか（コードブロック
    とコードスパンの外にある「、」「。」を警告する）
  - --kind を指定した場合: 「由来」の要否（diff では必須，files では禁止）
  - --root を指定した場合: 場所欄のパスの存在と行番号の範囲
  - --rereview を指定した場合: 前回指摘の対応状況との整合と番号の継続

終了ステータス: 0 = エラーなし，1 = エラーあり，2 = 使い方の誤り
"""

import argparse
import os
import re
import sys

SEVERITIES = ("高", "中", "低")
RANK = dict((name, index) for index, name in enumerate(SEVERITIES))
PERSPECTIVES = (
    "要件・仕様", "正確性", "エラー処理", "リソース管理", "並行性", "セキュリティ",
    "データ整合性", "互換性", "性能", "テスト", "可読性・保守性", "ドキュメント",
    "ビルド・依存関係", "運用性", "移植性", "国際化・アクセシビリティ",
    "理論的整合性", "疑似コードとの整合性", "公開コードとの整合性",
)
FIELDS = (
    "場所", "由来", "観点", "確度", "問題", "根拠", "影響", "深刻度の判断理由",
    "リスク許容時の対応", "修正案",
)
BASIC_FIELDS = ("場所", "観点", "確度", "問題", "修正案")
REQUIRED_FIELDS = {
    "高": BASIC_FIELDS + ("根拠", "影響", "深刻度の判断理由"),
    "中": BASIC_FIELDS + ("根拠", "影響", "深刻度の判断理由", "リスク許容時の対応"),
    "低": BASIC_FIELDS,
}
SECTIONS = (
    "概要", "前回指摘の対応状況", "指摘一覧", "指摘詳細", "確認事項",
    "レビューの範囲と限界",
)
REQUIRED_SECTIONS = ("概要", "指摘一覧", "指摘詳細", "レビューの範囲と限界")
ROOT_HEADING = "コードレビュー結果"
OVERVIEW_FIELDS = ("対象", "変更の目的", "前提", "実施した検証", "判定")
STATUSES = ("解決済み", "一部解決", "未解決", "取り下げ")
CARRIED_STATUSES = ("一部解決", "未解決")
NO_FINDINGS = "指摘事項はありません"
INDEX_HEADER = ["ID", "深刻度", "概要", "場所"]
COUNT_HEADER = ["深刻度", "件数", "意味"]
MEANINGS = {
    "高": "解決するまでマージすべきでない（ブロッカー）",
    "中": "未解決のままマージするには明示的なリスク許容の判断が必要",
    "低": "上記のいずれにも該当しない",
}
PROSE_FIELDS = ("問題", "根拠", "影響", "深刻度の判断理由", "リスク許容時の対応",
                "修正案")
TITLE_LIMIT = 80

FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
FINDING_MARK_RE = re.compile(r"^R\d|【\s*(高|中|低)\s*】")
FINDING_RE = re.compile(r"^(R\d+)\s*【\s*([^】]*?)\s*】\s*(.*)$")
FIELD_RE = re.compile(
    r"^[-*+][ \t]+(?:"
    r"\*\*(?P<a>[^*]+?)\*\*[ \t]*[:：]"
    r"|\*\*(?P<b>[^*]+?)[ \t]*[:：][ \t]*\*\*"
    r"|(?P<c>[^\s*:：`][^:：`]*?)[ \t]*[:：]"
    r")[ \t]*(?P<value>.*)$")
TABLE_ROW_RE = re.compile(r"^\s*\|(.*)\|\s*$")
TABLE_SEPARATOR_RE = re.compile(r"^\s*:?-{3,}:?\s*$")
ID_RE = re.compile(r"^R(\d+)$")
BOUNDARY = r"(?=$|[\s—–\-－:：（(，．、。,.])"
VERDICT_VALUE_RE = re.compile(r"^(マージ不可|条件付きマージ可|マージ可)" + BOUNDARY)
CONFIDENCE_RE = re.compile(r"^(確定|ほぼ確実|要確認)" + BOUNDARY)
ORIGIN_RE = re.compile(r"^(変更起因|既存)" + BOUNDARY)
CODE_SPAN_RE = re.compile(r"`([^`]+)`")
PATH_LINE_RE = re.compile(
    r"^(?P<path>.+?):(?P<start>\d+)(?:[-–〜~](?P<end>\d+))?$")
KANA_RE = re.compile("[\u3040-\u30ff]")
JAPANESE_RE = re.compile("[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]")
PERSPECTIVE_SPLIT_RE = re.compile("[，、,／/]")
DISALLOWED_PUNCTUATION_RE = re.compile("[、。]")
PUNCTUATION_LINE_LIMIT = 10


class Report(object):
    def __init__(self):
        self.items = []

    def error(self, line, message):
        self.items.append((line or 0, 0, "エラー", message))

    def warning(self, line, message):
        self.items.append((line or 0, 1, "警告", message))

    def count(self, severity):
        return sum(1 for item in self.items if item[2] == severity)

    def render(self):
        lines = []
        for line, _, severity, message in sorted(self.items):
            where = "%d 行目: " % line if line else ""
            lines.append("%s: %s%s" % (severity, where, message))
        return lines


class Line(object):
    def __init__(self, number, text, code):
        self.number = number
        self.text = text
        self.code = code


class Heading(object):
    def __init__(self, index, level, text):
        self.index = index
        self.level = level
        self.text = text


class Field(object):
    def __init__(self, label, line, value):
        self.label = label
        self.line = line
        self.value = value
        self.extra = []

    @property
    def content(self):
        return "\n".join([self.value] + self.extra)

    def is_empty(self):
        return not self.content.strip()


class Finding(object):
    def __init__(self, heading, fid, severity, title):
        self.heading = heading
        self.id = fid
        self.severity = severity
        self.title = title
        self.fields = {}
        self.order = []

    @property
    def line(self):
        return self.heading.index + 1


def parse_lines(text):
    lines = []
    fence = None
    for number, raw in enumerate(text.split("\n"), 1):
        match = FENCE_RE.match(raw)
        if fence is None:
            if match:
                fence = (match.group(1)[0], len(match.group(1)))
                lines.append(Line(number, raw, True))
            else:
                lines.append(Line(number, raw, False))
        else:
            lines.append(Line(number, raw, True))
            if (match and match.group(1)[0] == fence[0]
                    and len(match.group(1)) >= fence[1]
                    and not match.group(2).strip()):
                fence = None
    return lines


def parse_headings(lines):
    headings = []
    for index, line in enumerate(lines):
        if line.code:
            continue
        match = HEADING_RE.match(line.text)
        if match:
            headings.append(Heading(index, len(match.group(1)),
                                    match.group(2).strip()))
    return headings


def block_end(headings, heading, limit):
    """見出しの次の，同じかより浅いレベルの見出しの位置（なければ limit）．"""
    for other in headings:
        if other.index > heading.index and other.level <= heading.level:
            return min(other.index, limit)
    return limit


def split_cells(text):
    match = TABLE_ROW_RE.match(text)
    if not match:
        return None
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", match.group(1))]


def plain(text):
    return text.replace("**", "").replace("`", "").strip()


def table_rows(lines, start, end):
    """範囲内の表の行を，本文の行と見出し行に分けて返す．

    各行は (行番号, セルのリスト, None) の形．区切り行（|---|）の直前の行を
    見出し行とみなす．
    """
    rows, headers = [], []
    for line in lines[start:end]:
        cells = None if line.code else split_cells(line.text)
        if cells is None:
            continue
        if all(TABLE_SEPARATOR_RE.match(cell) for cell in cells):
            if rows and rows[-1][0] == line.number - 1:
                headers.append(rows.pop())
            continue
        rows.append((line.number, cells, None))
    return rows, headers


def find_sections(lines, headings, report, rereview):
    sections = {}
    for heading in headings:
        if heading.text not in SECTIONS:
            continue
        if heading.text in sections:
            report.error(heading.index + 1,
                         "節「%s」が重複しています" % heading.text)
            continue
        sections[heading.text] = (heading, heading.index + 1,
                                  block_end(headings, heading, len(lines)))
    for name in REQUIRED_SECTIONS:
        if name not in sections:
            report.error(None, "必須の節「%s」がありません（見出しの文言を"
                         "変えないでください）" % name)
    previous = sections.get("前回指摘の対応状況")
    if rereview and previous is None:
        report.error(None, "再レビューでは「前回指摘の対応状況」の節が必要です")
    if not rereview and previous is not None:
        report.warning(previous[0].index + 1, "「前回指摘の対応状況」があります．"
                       "再レビューであれば --rereview を指定してください")
    present = [name for name in SECTIONS if name in sections]
    positions = [sections[name][0].index for name in present]
    if positions != sorted(positions):
        report.error(None, "節の順序が書式と異なります（%s の順に並べて"
                     "ください）" % "，".join(present))
    roots = [h for h in headings if h.text == ROOT_HEADING]
    if not roots:
        report.error(None, "報告書の最初の見出しを「%s」にしてください"
                     % ROOT_HEADING)
    elif sections and roots[0].index > min(
            heading.index for heading, _, _ in sections.values()):
        report.error(roots[0].index + 1, "見出し「%s」は各節より前に置いて"
                     "ください" % ROOT_HEADING)
    return sections


def prose_text(text):
    """コードブロックとコードスパンを除いた文章を返す．"""
    kept = []
    fence = None
    for line in text.split("\n"):
        match = FENCE_RE.match(line)
        if fence is not None:
            if (match and match.group(1)[0] == fence[0]
                    and len(match.group(1)) >= fence[1]
                    and not match.group(2).strip()):
                fence = None
            continue
        if match:
            fence = (match.group(1)[0], len(match.group(1)))
            continue
        kept.append(CODE_SPAN_RE.sub("", line))
    return "\n".join(kept)


def has_japanese(text):
    return bool(JAPANESE_RE.search(prose_text(text)))


def parse_fields(finding, lines, start, end, report):
    current = None
    for line in lines[start:end]:
        match = None
        if not line.code and line.text[:1] not in (" ", "\t"):
            match = FIELD_RE.match(line.text)
        if match:
            label = (match.group("a") or match.group("b")
                     or match.group("c")).strip()
            if label in FIELDS:
                if label in finding.fields:
                    report.error(line.number, "%s: 項目「%s」が重複しています"
                                 % (finding.id, label))
                    current = None
                    continue
                current = Field(label, line.number, match.group("value"))
                finding.fields[label] = current
                finding.order.append(label)
                continue
            if match.group("a") or match.group("b"):
                report.warning(line.number, "%s: 未知の項目「%s」です（項目名は"
                               "書式の表記どおりにしてください）"
                               % (finding.id, label))
        if current is not None:
            current.extra.append(line.text)


def parse_findings(lines, headings, sections, report):
    """指摘の見出しと項目を解析する．

    「指摘詳細」の一段下の見出しはすべて指摘の見出しでなければならない．
    それ以外の場所やレベルにある，指摘の見出しに見えるものはエラーにする．
    """
    findings = []
    detail = sections.get("指摘詳細")
    candidates = []
    for heading in headings:
        inside = (detail is not None and detail[1] <= heading.index < detail[2]
                  and heading.level > detail[0].level)
        if inside and heading.level == detail[0].level + 1:
            candidates.append(heading)
        elif FINDING_MARK_RE.search(heading.text):
            report.error(heading.index + 1, "指摘の見出しは「指摘詳細」の節の"
                         "中に，それより一段だけ深い見出しとして置いて"
                         "ください: %s" % heading.text)
    starts = [heading.index for heading in candidates]
    for heading in candidates:
        number = heading.index + 1
        match = FINDING_RE.match(heading.text)
        if not match or not ID_RE.match(match.group(1)):
            report.error(number, "「指摘詳細」の直下の見出しは `R001【高】概要` "
                         "の形の指摘の見出しにしてください: %s" % heading.text)
            continue
        fid, severity, title = match.group(1), match.group(2), match.group(3)
        title = title.strip()
        if severity not in SEVERITIES:
            report.error(number, "%s: 深刻度は「高」「中」「低」のいずれかにして"
                         "ください（「%s」になっています）" % (fid, severity))
            severity = None
        if not title:
            report.error(number, "%s: 見出しに概要がありません" % fid)
        elif not has_japanese(title):
            report.error(number, "%s: 見出しの概要を日本語で書いてください" % fid)
        elif len(title) > TITLE_LIMIT:
            report.warning(number, "%s: 見出しの概要が長すぎます（%d 文字）．"
                           "詳細は「問題」に書いてください" % (fid, len(title)))
        finding = Finding(heading, fid, severity, title)
        end = min([block_end(headings, heading, len(lines)), detail[2]]
                  + [index for index in starts if index > heading.index])
        parse_fields(finding, lines, heading.index + 1, end, report)
        findings.append(finding)
    return findings


def leading_value(field):
    return plain(field.value) or plain(field.content)


def check_fields(finding, report):
    fid = finding.id
    required = REQUIRED_FIELDS.get(finding.severity, BASIC_FIELDS)
    for label in required:
        field = finding.fields.get(label)
        if field is None:
            report.error(finding.line, "%s: 必須の項目「%s」がありません"
                         % (fid, label))
        elif field.is_empty():
            report.error(field.line, "%s: 項目「%s」が空です" % (fid, label))
    for label, field in finding.fields.items():
        if label not in required and field.is_empty():
            report.warning(field.line, "%s: 項目「%s」が空です（書く内容が"
                           "なければ項目ごと削除してください）" % (fid, label))
    risk = finding.fields.get("リスク許容時の対応")
    if risk is not None and finding.severity == "高":
        report.error(risk.line, "%s: 深刻度「高」はブロッカーであり，リスク許容"
                     "の対象になりません．「リスク許容時の対応」を削除するか，"
                     "深刻度を見直してください" % fid)
    elif risk is not None and finding.severity == "低":
        report.warning(risk.line, "%s: 「リスク許容時の対応」は深刻度「中」の"
                       "指摘にだけ書きます" % fid)
    indices = [FIELDS.index(label) for label in finding.order]
    if indices != sorted(indices):
        report.warning(finding.line, "%s: 項目の順序が書式と異なります（%s の順）"
                       % (fid, "，".join(FIELDS)))

    confidence = finding.fields.get("確度")
    if confidence is not None and not confidence.is_empty():
        value = leading_value(confidence)
        match = CONFIDENCE_RE.match(value)
        if not match:
            report.error(confidence.line, "%s: 確度は「確定」「ほぼ確実」"
                         "「要確認」のいずれかで書き始めてください" % fid)
        elif match.group(1) == "要確認" and not has_japanese(
                confidence.content.split("要確認", 1)[1]):
            report.error(confidence.line, "%s: 確度が「要確認」の場合は，問題と"
                         "なるための前提と，その確認方法を続けて書いてください"
                         % fid)
    origin = finding.fields.get("由来")
    if origin is not None and not origin.is_empty():
        if not ORIGIN_RE.match(leading_value(origin)):
            report.error(origin.line, "%s: 由来は「変更起因」または「既存」の"
                         "いずれかにしてください" % fid)
    perspective = finding.fields.get("観点")
    if perspective is not None and not perspective.is_empty():
        for name in PERSPECTIVE_SPLIT_RE.split(plain(perspective.content)):
            name = name.strip()
            if name and name not in PERSPECTIVES:
                report.warning(perspective.line, "%s: 観点「%s」は観点名の一覧"
                               "（references/checklist.md）にありません"
                               % (fid, name))
    location = finding.fields.get("場所")
    if location is not None and not location.is_empty():
        if not CODE_SPAN_RE.search(location.content):
            report.warning(location.line, "%s: 場所はバッククォートで囲んだパス"
                           "と行番号（`path:行`）で示してください" % fid)
    for label in PROSE_FIELDS:
        field = finding.fields.get(label)
        if field is not None and not field.is_empty():
            if not has_japanese(field.content):
                report.error(field.line, "%s: 「%s」を日本語で書いてください"
                             "（コード片だけにしないでください）" % (fid, label))


def check_origins(findings, report, kind=None):
    with_origin = [f for f in findings if "由来" in f.fields]
    for finding in findings:
        has_origin = "由来" in finding.fields
        if kind == "diff" and not has_origin:
            report.error(finding.line, "%s: 差分のレビューでは「由来」が必要です"
                         % finding.id)
        elif kind == "files" and has_origin:
            report.error(finding.line, "%s: ファイル全体のレビューでは「由来」を"
                         "書きません" % finding.id)
        elif (kind is None and with_origin and not has_origin):
            report.error(finding.line, "%s: 「由来」がありません（差分の"
                         "レビューでは，すべての指摘に書いてください）"
                         % finding.id)


def check_ids(findings, report, rereview):
    seen = {}
    numbered = []
    for finding in findings:
        number = int(ID_RE.match(finding.id).group(1))
        if number < 1 or finding.id != "R%03d" % number:
            report.error(finding.line, "%s: ID は R と 3 桁以上の数字（R001，"
                         "R002，…，R999，R1000）で書いてください" % finding.id)
            continue
        if finding.id in seen:
            report.error(finding.line, "%s: ID が重複しています（%d 行目と同じ）"
                         % (finding.id, seen[finding.id]))
            continue
        seen[finding.id] = finding.line
        numbered.append((number, finding))
    previous = None
    for finding in findings:
        if finding.severity is None:
            continue
        if (previous is not None
                and RANK[finding.severity] < RANK[previous.severity]):
            report.error(finding.line, "%s: 指摘は深刻度「高」「中」「低」の順に"
                         "並べてください（%s【%s】の後に【%s】があります）"
                         % (finding.id, previous.id, previous.severity,
                            finding.severity))
        previous = finding
    if rereview:
        for (number, finding), (next_number, next_finding) in zip(
                numbered, numbered[1:]):
            if (finding.severity == next_finding.severity
                    and next_number < number):
                report.error(next_finding.line, "%s: 再レビューでは，同じ深刻度の"
                             "中で ID の昇順に並べてください" % next_finding.id)
    else:
        for position, finding in enumerate(findings, 1):
            expected = "R%03d" % position
            if finding.id != expected:
                report.error(finding.line, "%s: この位置の ID は %s のはずです"
                             "（並べた順に R001 から欠番なく番号を付けて"
                             "ください）" % (finding.id, expected))
                break


def section_text(lines, section):
    _, start, end = section
    return "\n".join(line.text for line in lines[start:end] if not line.code)


def check_index(lines, sections, findings, report):
    """指摘一覧を検査し，(行番号, ID, 場所のセル) の並びを返す．"""
    section = sections.get("指摘一覧")
    if section is None:
        return []
    heading, start, end = section
    rows, headers = table_rows(lines, start, end)
    if not findings:
        if NO_FINDINGS not in section_text(lines, section):
            report.error(heading.index + 1, "指摘がない場合は，指摘一覧に"
                         "「指摘事項はありません．」と書いてください")
    for number, cells, _ in headers:
        if [plain(cell) for cell in cells] != INDEX_HEADER:
            report.warning(number, "指摘一覧の表の見出し行は"
                           "「| ID | 深刻度 | 概要 | 場所 |」にしてください")
    entries = []
    for number, cells, _ in rows:
        fid = plain(cells[0])
        if not ID_RE.match(fid):
            report.warning(number, "指摘一覧の行から ID を読み取れません")
            continue
        if len(cells) != 4:
            report.warning(number, "指摘一覧の行は ID，深刻度，概要，場所の"
                           "4 列にしてください")
        cells = cells + [""] * (4 - len(cells))
        entries.append((number, fid, plain(cells[1]), plain(cells[2]),
                        cells[3]))
    if findings and not entries:
        report.error(heading.index + 1, "指摘一覧に，すべての指摘を載せた表が"
                     "ありません")
        return []
    details = dict((finding.id, finding) for finding in findings)
    listed = []
    for number, fid, severity, summary, location in entries:
        if fid in listed:
            report.error(number, "指摘一覧で %s が重複しています" % fid)
            continue
        listed.append(fid)
        finding = details.get(fid)
        if finding is None:
            report.error(number, "指摘一覧の %s に対応する指摘詳細がありません"
                         % fid)
            continue
        if finding.severity and severity != finding.severity:
            report.error(number, "%s: 指摘一覧の深刻度（%s）が指摘詳細（%s）と"
                         "異なります" % (fid, severity, finding.severity))
        if summary != plain(finding.title):
            report.error(number, "%s: 指摘一覧の概要を指摘詳細の見出しと同じ"
                         "文言にしてください" % fid)
        detail_location = finding.fields.get("場所")
        listed_spans = CODE_SPAN_RE.findall(location)
        if detail_location is not None and listed_spans:
            detail_spans = set(span.strip() for span in
                               CODE_SPAN_RE.findall(detail_location.content))
            for span in listed_spans:
                if span.strip() not in detail_spans:
                    report.error(number, "%s: 指摘一覧の場所 `%s` が指摘詳細の"
                                 "「場所」にありません" % (fid, span.strip()))
        elif not listed_spans:
            report.warning(number, "%s: 指摘一覧の場所をバッククォートで囲んだ"
                           "パスと行番号で示してください" % fid)
    for finding in findings:
        if finding.id not in listed:
            report.error(finding.line, "%s が指摘一覧にありません" % finding.id)
    in_index = [fid for fid in listed if fid in details]
    in_details = []
    for finding in findings:
        if finding.id in listed and finding.id not in in_details:
            in_details.append(finding.id)
    if in_index != in_details:
        report.error(heading.index + 1, "指摘一覧の順序が指摘詳細と異なります")
    return [(number, fid, location)
            for number, fid, _, _, location in entries]


def check_empty_statement(lines, sections, findings, report):
    for name in ("指摘一覧", "指摘詳細"):
        section = sections.get(name)
        if section is None:
            continue
        has_statement = NO_FINDINGS in section_text(lines, section)
        if findings and has_statement:
            report.error(section[0].index + 1, "指摘があるのに，「%s」に"
                         "「指摘事項はありません」と書かれています" % name)
        if not findings and not has_statement and name == "指摘詳細":
            report.warning(section[0].index + 1, "指摘がない場合は，指摘詳細にも"
                           "「指摘事項はありません．」と書いてください")


def count_by_severity(findings):
    return dict((name, sum(1 for f in findings if f.severity == name))
                for name in SEVERITIES)


def expected_verdict(counts):
    if counts["高"]:
        return "マージ不可"
    if counts["中"]:
        return "条件付きマージ可"
    return "マージ可"


def overview_fields(lines, start, end, report):
    """概要の箇条書きの項目を {名前: (行番号, 内容)} にする．"""
    fields = {}
    current = None
    for line in lines[start:end]:
        match = None
        if not line.code and line.text[:1] not in (" ", "\t"):
            match = FIELD_RE.match(line.text)
        if match:
            label = (match.group("a") or match.group("b")
                     or match.group("c")).strip()
            if label in OVERVIEW_FIELDS:
                if label in fields:
                    report.error(line.number, "概要の項目「%s」が重複しています"
                                 % label)
                    current = None
                else:
                    fields[label] = [line.number, match.group("value")]
                    current = label
                continue
            current = None
        elif line.text.startswith("|") or line.text.startswith("#"):
            current = None
        elif current is not None and line.text.strip():
            fields[current][1] += "\n" + line.text
    return fields


def check_summary(lines, sections, findings, report):
    section = sections.get("概要")
    if section is None:
        return
    heading, start, end = section
    fields = overview_fields(lines, start, end, report)
    for label in OVERVIEW_FIELDS:
        if label not in fields:
            report.error(heading.index + 1, "概要に「%s」の項目がありません"
                         % label)
        elif not fields[label][1].strip():
            report.error(fields[label][0], "概要の「%s」が空です" % label)
        elif label != "判定" and not has_japanese(fields[label][1]):
            report.error(fields[label][0], "概要の「%s」を日本語で書いて"
                         "ください" % label)

    counts = count_by_severity(findings)
    table = {}
    rows, headers = table_rows(lines, start, end)
    for number, cells, _ in headers:
        if [plain(cell) for cell in cells] != COUNT_HEADER:
            report.error(number, "件数の表の見出し行は「| 深刻度 | 件数 | 意味 |」"
                         "にしてください")
    for number, cells, _ in rows:
        name = plain(cells[0])
        if name not in SEVERITIES:
            continue
        if len(cells) != 3:
            report.error(number, "件数の表の行は深刻度，件数，意味の 3 列に"
                         "してください")
            continue
        match = re.match(r"^(\d+)\s*件?$", plain(cells[1]))
        if not match:
            report.error(number, "件数の表の「%s」の件数を数字で書いてください"
                         % name)
        elif name in table:
            report.error(number, "件数の表で「%s」の行が重複しています" % name)
        else:
            table[name] = (number, int(match.group(1)))
        if plain(cells[2]) != MEANINGS[name]:
            report.error(number, "件数の表の「%s」の意味は「%s」と書いて"
                         "ください" % (name, MEANINGS[name]))
    if not table:
        report.error(heading.index + 1, "概要に深刻度別の件数の表"
                     "（| 深刻度 | 件数 | 意味 |）がありません")
    else:
        for name in SEVERITIES:
            if name not in table:
                report.error(heading.index + 1, "件数の表に「%s」の行がありません"
                             "（0 件でも書いてください）" % name)
            elif table[name][1] != counts[name]:
                report.error(table[name][0], "件数の表では「%s」が %d 件ですが，"
                             "指摘詳細には %d 件あります"
                             % (name, table[name][1], counts[name]))

    expected = expected_verdict(counts)
    if "判定" not in fields:
        return
    number, value = fields["判定"]
    match = VERDICT_VALUE_RE.match(plain(value))
    if not match:
        report.error(number, "判定は「マージ不可」「条件付きマージ可」"
                     "「マージ可」のいずれかで書き始めてください（例: "
                     "「%s — ……」）" % expected)
    elif match.group(1) != expected:
        report.error(number, "判定が「%s」になっていますが，指摘の深刻度"
                     "（高 %d 件，中 %d 件，低 %d 件）からは「%s」です"
                     % (match.group(1), counts["高"], counts["中"], counts["低"],
                        expected))


def check_rereview(lines, sections, findings, report):
    section = sections.get("前回指摘の対応状況")
    if section is None:
        return
    heading, start, end = section
    rows, _ = table_rows(lines, start, end)
    previous = {}
    for number, cells, _ in rows:
        fid = plain(cells[0])
        match = ID_RE.match(fid)
        if not match:
            report.warning(number, "前回指摘の対応状況の行から ID を読み取れません")
            continue
        if fid in previous:
            report.error(number, "前回指摘の対応状況で %s が重複しています" % fid)
            continue
        severity = plain(cells[1]) if len(cells) > 1 else ""
        status = plain(cells[2]) if len(cells) > 2 else ""
        if severity not in SEVERITIES:
            report.warning(number, "%s: 前回の深刻度は「高」「中」「低」の"
                           "いずれかで書いてください" % fid)
        if status not in STATUSES:
            report.error(number, "%s: 状況は「解決済み」「一部解決」「未解決」"
                         "「取り下げ」のいずれかにしてください" % fid)
        value = int(match.group(1))
        if value < 1 or fid != "R%03d" % value:
            report.error(number, "%s: ID は R と 3 桁以上の数字（R001 など）で"
                         "書いてください" % fid)
        previous[fid] = (number, status, value)
    if not previous:
        report.error(heading.index + 1, "前回指摘の対応状況に，前回までの指摘"
                     "ごとの表がありません")
        return
    current = set(finding.id for finding in findings)
    for fid, (number, status, _) in sorted(previous.items()):
        if status in CARRIED_STATUSES and fid not in current:
            report.error(number, "%s は「%s」なので，同じ ID で指摘詳細に載せて"
                         "ください" % (fid, status))
        if status in ("解決済み", "取り下げ") and fid in current:
            report.error(number, "%s は「%s」なので，指摘詳細に載せないで"
                         "ください" % (fid, status))
    largest = max(value for _, _, value in previous.values())
    used = set(value for _, _, value in previous.values())
    missing = [n for n in range(1, largest + 1) if n not in used]
    if missing:
        report.error(heading.index + 1, "前回指摘の対応状況には，これまでに付けた"
                     "すべての ID（R001 から R%03d まで）を載せてください（%s が"
                     "ありません）" % (largest, "，".join("R%03d" % n
                                                     for n in missing[:5])))
    new_numbers = []
    for finding in findings:
        number = int(ID_RE.match(finding.id).group(1))
        if finding.id in previous:
            continue
        if number <= largest:
            report.error(finding.line, "%s: 新しい指摘には，前回までの最大の"
                         "番号（R%03d）より大きい番号を付けてください（番号は"
                         "再利用しません）" % (finding.id, largest))
        else:
            new_numbers.append(number)
    expected = list(range(largest + 1, largest + 1 + len(new_numbers)))
    if sorted(new_numbers) != expected:
        report.error(heading.index + 1, "新しい指摘の ID は R%03d から欠番なく"
                     "連番にしてください（現在: %s）" % (
                         largest + 1, "，".join("R%03d" % n
                                               for n in sorted(new_numbers))))


def count_file_lines(path, cache):
    if path not in cache:
        count, last = 0, b"\n"
        try:
            with open(path, "rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    count += chunk.count(b"\n")
                    last = chunk[-1:]
            cache[path] = count + (0 if last == b"\n" else 1)
        except (IOError, OSError):
            cache[path] = None
    return cache[path]


def inside_root(root, path):
    real_root = os.path.realpath(root)
    real_path = os.path.realpath(os.path.join(root, path))
    try:
        return os.path.commonpath([real_root, real_path]) == real_root
    except ValueError:
        return False


def check_location_text(fid, text, number, root, report, cache):
    for match in CODE_SPAN_RE.finditer(text):
        token = match.group(1).strip()
        before_change = "変更前" in text[match.end():match.end() + 8]
        path_line = None if "://" in token else PATH_LINE_RE.match(token)
        if path_line:
            path = path_line.group("path")
        elif "/" in token and not re.search(r"[\s()<>*?]|://", token):
            path = token.rstrip("/")
        else:
            continue
        if os.path.isabs(path) or re.match(r"^[A-Za-z]:[\\/]", path):
            report.error(number, "%s: 場所 `%s` はリポジトリのルートからの相対"
                         "パスで書いてください" % (fid, token))
            continue
        if not inside_root(root, path):
            report.error(number, "%s: 場所 `%s` が --root の外を指しています"
                         % (fid, token))
            continue
        full = os.path.join(root, path)
        if not os.path.exists(full):
            if not before_change:
                report.warning(number, "%s: 場所のパス `%s` が --root の下に"
                               "見つかりません" % (fid, path))
            continue
        if path_line is None or before_change:
            continue
        if not os.path.isfile(full):
            report.warning(number, "%s: `%s` はファイルではありません"
                           % (fid, path))
            continue
        start = int(path_line.group("start"))
        end = int(path_line.group("end") or start)
        total = count_file_lines(full, cache)
        if start < 1 or end < start:
            report.error(number, "%s: 行番号の範囲 `%s` が不正です" % (fid, token))
        elif total is not None and end > total:
            report.error(number, "%s: `%s` の行番号が，ファイルの行数（%d 行）を"
                         "超えています" % (fid, token, total))


def check_locations(findings, entries, root, report):
    cache = {}
    for finding in findings:
        field = finding.fields.get("場所")
        if field is not None:
            check_location_text(finding.id, field.content, field.line, root,
                                report, cache)
    for number, fid, location in entries:
        check_location_text(fid, location, number, root, report, cache)


def check_japanese(lines, report):
    prose = [line.text for line in lines
             if not line.code and not HEADING_RE.match(line.text)]
    if not any(KANA_RE.search(text) for text in prose):
        report.error(None, "報告書を日本語で書いてください")


def check_punctuation(lines, report):
    """コードブロックとコードスパンの外にある「、」「。」を警告する．"""
    found = [line.number for line in lines
             if not line.code and DISALLOWED_PUNCTUATION_RE.search(
                 CODE_SPAN_RE.sub("", line.text))]
    if not found:
        return
    shown = "，".join("%d" % number
                      for number in found[:PUNCTUATION_LINE_LIMIT]) + " 行目"
    if len(found) > PUNCTUATION_LINE_LIMIT:
        shown += "ほか %d 行" % (len(found) - PUNCTUATION_LINE_LIMIT)
    report.warning(found[0], "「、」「。」が使われています（%d 行: %s）．"
                   "句読点は「，」「．」に統一してください（原文を引用する場合は，"
                   "句読点を変えずにコードスパンかコードブロックで示してください）"
                   % (len(found), shown))


def check(text, root=None, rereview=False, kind=None):
    """報告書を検査し，(Report, 解析結果の要約) を返す．"""
    report = Report()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        report.error(None, "報告書が空です")
        return report, "解析できません"
    lines = parse_lines(text)
    headings = parse_headings(lines)
    sections = find_sections(lines, headings, report, rereview)
    findings = parse_findings(lines, headings, sections, report)
    for finding in findings:
        check_fields(finding, report)
    check_origins(findings, report, kind)
    check_ids(findings, report, rereview)
    entries = check_index(lines, sections, findings, report)
    check_empty_statement(lines, sections, findings, report)
    check_summary(lines, sections, findings, report)
    if rereview:
        check_rereview(lines, sections, findings, report)
    if root:
        check_locations(findings, entries, root, report)
    check_japanese(lines, report)
    check_punctuation(lines, report)
    counts = count_by_severity(findings)
    summary = "指摘 %d 件（高 %d / 中 %d / 低 %d），期待される判定: %s" % (
        len(findings), counts["高"], counts["中"], counts["低"],
        expected_verdict(counts))
    return report, summary


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="コードレビューの報告書の書式を検査する．",
        epilog="終了ステータス: 0 = エラーなし，1 = エラーあり，2 = 使い方の誤り")
    parser.add_argument("file", nargs="?", default="-",
                        help="報告書のファイル（省略するか - で標準入力）")
    parser.add_argument(
        "--root", metavar="DIR",
        help="場所欄のパスの基準となるディレクトリ（リポジトリのルート）．"
             "指定すると，パスの存在と行番号の範囲を検査する")
    parser.add_argument(
        "--kind", choices=("diff", "files"),
        help="レビューの種類．diff（差分のレビュー）では全指摘に「由来」を必須"
             "とし，files（ファイル全体のレビュー）では「由来」を禁止する")
    parser.add_argument(
        "--rereview", action="store_true",
        help="再レビューの報告書として検査する（前回指摘の対応状況との整合，"
             "番号の継続）")
    args = parser.parse_args(argv)
    if args.file == "-" and sys.stdin.isatty():
        parser.error("入力がありません．ファイルを指定するか，標準入力に報告書を"
                     "渡してください")
    if args.root and not os.path.isdir(args.root):
        parser.error("--root のディレクトリが存在しません: %s" % args.root)
    return args


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = parse_args(argv)
    if args.file == "-":
        data = sys.stdin.buffer.read()
    else:
        try:
            with open(args.file, "rb") as stream:
                data = stream.read()
        except (IOError, OSError) as exc:
            sys.stderr.write("エラー: %s を読み込めません: %s\n"
                             % (args.file, exc))
            return 2
    report, summary = check(data.decode("utf-8-sig", "replace"),
                            root=args.root, rereview=args.rereview,
                            kind=args.kind)
    for line in report.render():
        print(line)
    print("解析結果: " + summary)
    errors, warnings = report.count("エラー"), report.count("警告")
    if errors or warnings:
        print("結果: エラー %d 件，警告 %d 件" % (errors, warnings))
    else:
        print("結果: OK")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
