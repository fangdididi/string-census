# string-census 文案普查

[English](README.md) · **简体中文**

一个智能体技能：把产品里每一条界面文案、每一种语言一次性审完，告诉你这些文字能不能发版。

占位符对不上、复数缺少 `other` 分支、代码里拼接的句子、“是 / 否”对话框、“点击这里”链接、不给出路的报错、术语走样、没翻译和放不下的文字——文案普查在所有语言包里一次找出来，汇成一本带结论的台账。

## 为什么需要它

界面文案是一页一页评审、一个键一个键翻译的。没有人把语言包当成整体来读，所以只有跨文件才看得出的问题（某个语言里改了名的占位符、流程走到一半换了说法的术语、英文刚好、德文长出三倍的按钮）总是先被用户撞上。文案普查就是把它们当成一个整体来读。

## 功能

- **三级问题，一个结论。** `BREAKS`（会崩溃或显示错误数据）、`MISLEADS`（会把人带错路）、`DRIFTS`（不一致和翻译欠账）。结论为 `HOLD`、`SHIP WITH DEBT`、`CLEAN WITH DRIFT` 或 `CLEAN`，并提供对应的退出码，方便接入 CI。
- **普查卡。** 运行前冻结的一个小 JSON：源语言、术语表、按元素类型的大小写规则、槽位宽度、角色覆盖、允许与源文相同的字符串。
- **占位符检查**：ICU `{name}`、ICU plural/select、mustache `{{name}}`、printf `%s` `%1$s` `%@`、Ruby `%{name}`，以及可选的 Laravel `:name`。
- **ICU 结构检查**：括号不配对、plural 或 select 缺少 `other`。
- **跨语言检查**：缺失键、孤儿键、空翻译、未翻译、同一源文被译成两种说法、超出槽位或增长系数的文字（中日韩字符按双倍宽度计）。
- **源文措辞检查**：含糊链接、“Are you sure”、是/否/OK 按钮、“Oops”式报错、没有下一步的报错、否定式开关、“successfully”、控件里的“Please”、指令式占位文字、`(s)` 假复数、术语表、大小写规则。
- **代码扫描**：围着变量拼接的句子、`=== 1 ? "" : "s"` 复数小把戏、不带语言区域的日期格式化、描述图标而非动作的 `aria-label`。
- **支持格式**：JSON（嵌套、i18next、next-intl、vue-i18n）、Flutter ARB、Apple `.strings`。只依赖 Python 3 标准库。

## 安装

整个文件夹就是技能，复制或克隆到你的智能体读取技能的位置即可。

**Claude Code**

```bash
git clone https://github.com/fangdididi/string-census ~/.claude/skills/string-census
```

**Codex**

```bash
git clone https://github.com/fangdididi/string-census ~/.codex/skills/string-census
```

**Cursor**：克隆到项目的 `.cursor/skills/string-census`（或全局技能目录），在对话里提到“文案普查 / string census”即可。

**其他智能体**：让它读取 `SKILL.zh-CN.md`（或 `SKILL.md`），并把 `scripts/census.py` 放在旁边。

## 使用

对智能体说：

> 德语版上线前，对 `web/locales` 做一次文案普查，源语言是英文。

或者自己运行检查脚本：

```bash
python3 scripts/census.py locales/*.json --source en --card census-card.json --code src > census-ledger.md
echo $?   # 2 HOLD · 1 SHIP WITH DEBT · 0 CLEAN
```

选项：`--format json` 输出 JSON；`--colon` 把 `:name` 当作占位符；可多次使用 `--code` 扫描多个目录。

## 示例

```bash
cd examples/demo-app
python3 ../../scripts/census.py locales/en.json locales/de.json locales/zh-CN.json --source en --card census-card.json --code src
```

```text
# String census: HOLD

| Tier | Count |
| --- | --- |
| BREAKS | 7 |
| MISLEADS | 7 |
| DRIFTS | 11 |
```

部分发现：

| 级别 | 规则 | 语言 | 位置 | 文本 |
| --- | --- | --- | --- | --- |
| BREAKS | placeholder-mismatch | de | `project.owner_label` | `Gehört {owner}`（源文是 `{name}`） |
| BREAKS | icu-syntax | de | `project.count` | 复数缺少 `other` |
| BREAKS | empty-translation | zh-CN | `settings.email_placeholder` | 空字符串 |
| BREAKS | plural-hack | 代码 | `ProjectHeader.tsx:3` | `files.length === 1 ? "" : "s"` |
| MISLEADS | are-you-sure | en | `project.delete_confirm` | `Are you sure?` |
| MISLEADS | glyph-name | 代码 | `ProjectHeader.tsx:8` | `aria-label="Trash icon"` |
| DRIFTS | over-slot | de | `project.delete_button` | 44 列文字塞进 24 列的按钮 |

完整台账见 [examples/demo-app/expected-ledger.md](examples/demo-app/expected-ledger.md)。

## 文件结构

```text
string-census/
├── SKILL.md                  # 技能说明（英文）
├── SKILL.zh-CN.md            # 技能说明（中文）
├── README.md
├── README.zh-CN.md
├── LICENSE
├── scripts/
│   └── census.py             # 检查脚本（仅标准库）
├── tests/
│   └── test_census.py        # 76 个测试：python3 -m unittest discover -s tests
└── examples/
    └── demo-app/
        ├── census-card.json
        ├── locales/          # en、de、zh-CN，预埋了问题
        ├── src/ProjectHeader.tsx
        └── expected-ledger.md
```

## 局限

- 措辞规则只对源语言运行（英文规则）。其他语言做的是结构和跨语言检查，措辞仍需要懂这门语言的人来读。
- `no-way-forward` 和角色识别都是启发式的。技能会要求智能体先结合上下文读每一条，再动手修改。
- 来自服务端、CMS 或远程配置的文案，除非导出，否则会被标为未覆盖。

## 许可证

MIT © fangdididi
