# Scientific Spaces Big-Data PDF builder（主题分类版）

将科学空间（[spaces.ac.cn](https://spaces.ac.cn)）的文章抓取、按**主题分类**整理，并合成带书签和页码的 PDF，方便在 iPad 等设备上离线阅读。

本 fork 在原版（BaochaiXue/sujianlin_pdf，仅抓"信息时代"单一分类）基础上增强：

* **主题分类体系**：新增 `kexue_book/taxonomy.py`，把文章按标题关键词 + 原生分类门控归入 18 个主题（第二套主题分类），默认启用其中 9 个技术/数学主题；
* **多分类抓取**：默认抓取 信息时代（Big-Data）+ 数学研究（Mathematics）+ 千奇百怪（Everything）三个原生分类并自动去重；
* **反 Cookie 质询**：站点近期对无 Cookie 请求返回 403，爬虫已内置自动质询重试；
* **主题索引**：`--metadata-only` 一键输出 `index.md` / `posts.json`（按主题分组、含日期与链接），先看清单再决定要不要渲染 PDF；
* **两级书签**：合并成单本 PDF 时书签为 主题 → 文章 两级结构；
* **分册输出**：`--per-category` 可为每个主题单独生成一本 PDF。

> ⚠️ **版权说明**：科学空间的文章采用 CC BY-NC-SA 协议（署名-非商业性使用-相同方式共享）。本项目只抓取公开网页并本地生成 PDF，仅供个人学习与收藏使用，请勿用于任何商业用途，转发时请注明原作者与原站链接。

---

## 主题分类（默认启用 9 个）

| topic_id | 名称 | 参考篇数 |
|---|---|---|
| `dl-basics` | 深度学习基础 | ~123 |
| `embedding` | 词向量与Embedding | ~24 |
| `llm` | 大模型与Transformer | ~155 |
| `generative` | 生成模型 | ~124 |
| `optimization` | 优化与训练 | ~110 |
| `math` | 数学工具 | ~381 |
| `probability` | 概率统计与信息论 | ~85 |
| `geometry` | 几何与方程 | ~106 |
| `nlp` | NLP与信息抽取 | ~93 |

另有 9 个默认关闭的主题（`engineering` 工程工具、`astronomy` 天文科普、`phychem` 物理化学、`biology` 生物自然、`photography` 图片摄影、`qa` 科普问答与百科、`site` 资源与站务、`essay` 阅读写作与随笔、`misc` 其他），用 `--all-topics` 或 `--topic astronomy,...` 打开。

分类规则是启发式的（标题关键词优先级匹配 + 原生分类门控），全部集中在 `kexue_book/taxonomy.py`，可按需增删关键词微调。

---

## 目录结构

```text
kexue_book/
  __init__.py   # 包入口，导出 Post 类型
  types.py      # Post 元数据结构（标题 / URL / 日期 / 原生分类 / 主题）
  taxonomy.py   # 主题分类体系：18 个主题 + 关键词规则 + 门控表
  crawl.py      # 爬取原生分类页（含 Cookie 质询重试），收集元信息并归类
  index.py      # 按主题输出 index.md / posts.json 索引与统计
  render.py     # Playwright 渲染单篇 HTML -> 单篇 PDF
  merge.py      # 合并章节 PDF，添加封面、两级书签、页码
  cli.py        # 命令行入口（python -m kexue_book.cli）
output/          # 运行后生成的输出目录
  index.md       # 主题索引（--metadata-only 或正常构建时生成）
  posts.json     # 全部文章元数据（按主题分组）
  chapters/      # 渲染出的单篇 PDF
  manifest.json  # 每篇文章的渲染状态、PDF 路径、页数和失败原因
  *.pdf          # 最终合并后的“选集”PDF
requirements.txt
README.md
```

---

## 环境准备

建议使用 Python 3.11（其他 3.10+ 一般也可以）。

```bash
conda create -n kexue-book python=3.11 -y
conda activate kexue-book

pip install -r requirements.txt
python -m playwright install chromium
```

如果后续 `requirements.txt` 有更新，只需在已有环境中重新执行一次：

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

> Playwright 会自动下载 Chromium，可视为一次性的“浏览器安装”。

---

## 快速开始

### 第一步：先看主题索引（不渲染 PDF）

```bash
python -m kexue_book.cli \
  --start 2009-01-01 \
  --end   2026-12-31 \
  --metadata-only \
  --out-dir output
```

输出 `output/index.md`（按 9 个主题分组的文章清单：日期、标题、链接、原生分类）和 `output/posts.json`，并打印各主题篇数统计。

### 第二步：合成一本带两级书签的 PDF

```bash
python -m kexue_book.cli \
  --start 2009-01-01 \
  --end   2026-12-31 \
  --out-dir output \
  --name "Kexue-Topics" \
  --cover \
  --workers 6
```

书签结构为 主题（一级）→ 文章（二级），主题顺序即上表顺序，主题内按日期从旧到新。

### 或者：每个主题一本分册

```bash
python -m kexue_book.cli \
  --start 2009-01-01 \
  --end   2026-12-31 \
  --out-dir output \
  --per-category \
  --cover \
  --workers 6
```

输出到 `output/<topic-id>/<topic-id>-<start>-<end>.pdf`，每本封面写明主题名。

### 只想要其中几个主题

```bash
# 只要 大模型与Transformer + 生成模型 + 数学工具
python -m kexue_book.cli --start 2009-01-01 --end 2026-12-31 \
  --topic llm,generative,math --out-dir output-top3

# 也可以用全部 18 个主题
python -m kexue_book.cli --start 2009-01-01 --end 2026-12-31 \
  --all-topics --out-dir output-all
```

查看主题清单：`python -m kexue_book.cli --list-topics`

### 调规则 / 重建整书（不重新渲染）

分类规则集中在 `kexue_book/taxonomy.py`，改完后：

```bash
# 只重新归类并刷新索引（不重爬、不渲染）
python scripts/reclassify.py output/posts_all.json --out output

# 用已渲染的章节 PDF 重建整书（改了排序/书签/分类时）
python scripts/remerge.py output --name Kexue-Topics --cover
```

正常构建也支持 `--from-json output/posts_all.json` 跳过重新爬取。

---

## 默认行为与功能

* 默认抓取原生分类 `Big-Data`（信息时代）、`Mathematics`（数学研究）、`Everything`（千奇百怪），可用 `--source-category` 指定；一篇属于多个分类的文章自动去重合并。
* 默认只保留 9 个技术/数学主题的文章，其余（工程工具、天文……）被过滤掉。
* 文章先按主题顺序、再按日期从旧到新排列（`--order desc` 反转组内日期顺序）。
* 每篇文章会生成 **可点击的 PDF 书签目录**：单本模式为两级（主题 → 文章），分册模式为一级。
* 页脚会印出 **真实页码**，从整本书的第一页（封面）开始连续编号；可用 `--no-page-numbers` 关闭。
* 可选封面 `--cover`，标题为 **“苏剑林选集”**（分册模式为 “苏剑林选集 · 主题名”）。
* 会自动隐藏站点的侧边栏、评论区等元素，正文和公式（MathJax 渲染）都会保留。
* 支持按标题关键词选择或排除文章（`--title-keyword` / `--exclude-title-keyword`）。
* 每次渲染会生成 `manifest.json`，记录每篇文章的标题、URL、日期、序号、PDF 路径、状态、失败原因和页数。
* 支持断点续跑：`--resume` 会跳过已有且可读取、页数大于 0 的单篇 PDF；`--retry-failed` 只重试上一次 `manifest.json` 中失败的文章。

---

## 命令行参数

核心参数：

* `--start YYYY-MM-DD`：起始日期（含）。
* `--end YYYY-MM-DD`：结束日期（含）。
* `--out-dir PATH`：输出目录（默认：`output`）。
* `--name NAME`：生成的 PDF 文件名前缀（默认：`BigData`）。

主题相关（本 fork 新增）：

* `--source-category SLUG`：只抓这些原生分类，可重复或逗号分隔（默认 `Big-Data,Mathematics,Everything`）。
* `--topic ID`：只保留这些主题，可重复或逗号分隔（默认 9 个技术/数学主题）。
* `--all-topics`：不过滤主题，保留全部 18 个。
* `--list-topics`：打印主题清单后退出。
* `--metadata-only`：只抓元数据并输出 `index.md` / `posts.json`，不渲染 PDF。
* `--per-category`：每个主题单独合成一本 PDF。

排版 / 排序相关：

* `--order asc|desc`：组内按日期排序方式（默认 `asc`）。
* `--cover`：在最前面加一页封面。
* `--no-page-numbers`：关闭每页底部的页码。

标题过滤：

* `--title-keyword TEXT`：只保留标题包含指定关键词的文章；可重复或逗号分隔。
* `--title-match any|all`：多个关键词的匹配方式（默认 `any`）。
* `--exclude-title-keyword TEXT`：排除标题包含指定关键词的文章。
* `--title-case-sensitive`：标题关键词匹配改为大小写敏感。

渲染控制：

* `--delay-ms N`：每篇文章打印 PDF 前额外等待毫秒数（默认 4000，等 MathJax）。
* `--workers N`：并行渲染进程数（默认 1；4~6 视机器性能）。
* `--resume`：复用已存在的有效单篇 PDF。
* `--retry-failed`：只重试上次 manifest 中失败的文章。

调试：

* `--limit N`：只处理前 N 篇（先按主题过滤再应用）。

---

## 整体流程

运行 `python -m kexue_book.cli ...` 时会执行：

1. **抓取元信息（crawl）**  
   依次抓取各原生分类的分页列表（`https://spaces.ac.cn/category/<slug>`），内置 Cookie 质询自动重试；收集标题、URL、日期，按 URL 去重合并多分类信息；按 `--start`/`--end` 过滤时间区间。

2. **主题归类（taxonomy）**  
   按“标题关键词优先级匹配 + 原生分类门控”把每篇文章归入 18 个主题之一；默认只保留 9 个技术/数学主题，其余主题被过滤。`--metadata-only` 到此为止，输出索引。

3. **单篇渲染（render）**  
   使用 Playwright + Chromium 打开文章页面，等待 MathJax 渲染完成，注入打印 CSS 后导出 A4 单篇 PDF 到 `chapters/`；支持并行与断点续跑。

4. **合并与排版（merge）**  
   合并前输出完整性检查；按主题顺序合并所有单篇 PDF，生成两级书签（主题 → 文章）；可选封面与连续页码。`--per-category` 时改为按主题分别合并成多本。

---

## 注意事项与小贴士

* 第一次运行时 Playwright 会下载 Chromium，时间可能略长。
* 站点对无 Cookie 请求返回 403，爬虫已自动处理；若仍被拦（如 IP 级限流），等几分钟再试。
* 如果科学空间将来更换主题或改版 HTML 结构，`crawl.py` 里的 CSS 选择器（例如 `div.Post`, `span.submitted`）可能需要微调。
* 分类规则是启发式的，个别边界文章可能与原站主题分类有出入；调整 `taxonomy.py` 里的关键词即可，改完对 `posts.json` 重新归类不需要重新爬取正文列表。
* 封面默认使用 ReportLab 内置 `STSong-Light`；想换自定义中文字体，在 `merge.py` 的 `_make_cover_pdf` 中注册对应 TTF 并替换 `setFont("STSong-Light", 32)`。
* 生成的 PDF 仅用于 **个人学习和收藏**，请尊重原站点的 CC BY-NC-SA 协议，转载或分发时务必注明原作者“苏剑林”和科学空间链接。

---

生成好 PDF 之后，把最终的 `*.pdf` 丢进 iCloud / AirDrop 给 iPad，用任意 PDF 阅读器打开，就可以当一本“官方未发行的《苏剑林·主题选集》”慢慢啃了。
