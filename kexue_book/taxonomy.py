"""主题分类体系：把科学空间的文章按主题重新归类。

参考站点的第二套主题分类（共 18 个主题），默认只启用其中的 9 个技术/数学主题：

    深度学习基础、词向量与Embedding、大模型与Transformer、生成模型、
    优化与训练、数学工具、概率统计与信息论、几何与方程、NLP与信息抽取

分类规则是“标题关键词 + 原生分类门控”：
  1. 按优先级顺序匹配标题正则，命中即归入该主题（只允许归入该原生分类
     允许的主题集合）；
  2. 全部未命中时，落回该原生分类的兜底主题；
  3. 原生分类若没有出现在门控表里（如天文、物理等），直接落回它自身
     对应的主题（默认不启用）。

规则是启发式的，拿真实标题校准过篇数分布后仍可继续微调；所有规则都
集中在本文件，改起来只动这里。
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# 主题定义
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Topic:
    topic_id: str            # 英文 slug，用于命令行与目录名
    name: str                # 中文名，用于书签/索引展示
    title_rules: tuple[str, ...] = ()   # 按优先级排列的标题正则（忽略大小写）
    enabled_by_default: bool = False


# 默认启用的 9 个主题（对应需求截图中勾选的第二套分类子集）
DEFAULT_TOPIC_IDS: tuple[str, ...] = (
    "dl-basics",
    "embedding",
    "llm",
    "generative",
    "optimization",
    "math",
    "probability",
    "geometry",
    "nlp",
)

# 全部 18 个主题（第二套分类全集）；后 9 个默认不启用
TOPICS: tuple[Topic, ...] = (
    Topic(
        topic_id="embedding",
        name="词向量与Embedding",
        enabled_by_default=True,
        title_rules=(
            r"词向量", r"词嵌入", r"word2vec", r"word embedding", r"\bembedding\b",
            r"\bglove\b", r"句向量", r"句嵌入", r"skip-?gram", r"\bcmwe\b",
            r"\bsimcse\b", r"\bcosent\b", r"simbert", r"whitening", r"文本向量",
            r"句子相似度", r"对比学习",
        ),
    ),
    Topic(
        topic_id="llm",
        name="大模型与Transformer",
        enabled_by_default=True,
        title_rules=(
            r"transformer", r"attention", r"注意力", r"\bbert\b", r"\bgpt-?\d*\b",
            r"\bllm\b", r"大模型", r"语言模型", r"预训练", r"pre-?train",
            r"微调", r"fine[ -]?tun", r"\blora\b", r"\bmoe\b", r"专家混合",
            r"\brope\b", r"旋转位置", r"位置编码", r"位置嵌入", r"kv ?cache",
            r"scaling ?law", r"标度定律", r"\bmamba\b", r"线性attention",
            r"in-?context", r"上下文学习", r"prompt", r"提示词", r"\bcot\b",
            r"chain-?of-?thought", r"思维链", r"多模态", r"tokenizer",
            r"分词器", r"\bk3\b", r"deepseek", r"开源模型", r"对话模型",
            r"聊天模型", r"无损压缩", r"\blm\b ?loss", r"词表", r"词元",
            r"\balbert\b", r"\belectra\b", r"\bt5\b", r"bert4keras", r"wobert",
            r"roformer", r"\bnbce\b", r"词颗粒度",
        ),
    ),
    Topic(
        topic_id="generative",
        name="生成模型",
        enabled_by_default=True,
        title_rules=(
            r"生成模型", r"生成对抗", r"\bgan\b", r"\bwgan\b", r"\bvae\b",
            r"变分自编码", r"扩散模型", r"扩散", r"diffusion", r"\bddpm\b",
            r"\bddim\b", r"score-?based", r"流模型", r"flow模型", r"\bflow\b",
            r"\bglow\b", r"\bnice\b", r"对抗模型",
            r"normalizing flow", r"\bcnf\b", r"连续标准化流", r"能量模型",
            r"energy.?based", r"\bebm\b", r"图像生成", r"概率流",
            r"\bvq\b", r"wasserstein", r"最优传输", r"optimal transport",
            r"sde", r"随机微分方程", r"去噪", r"denois", r"\bvdm\b",
            r"生成式", r"自回归生成",
        ),
    ),
    Topic(
        topic_id="nlp",
        name="NLP与信息抽取",
        enabled_by_default=True,
        title_rules=(
            r"\bnlp\b", r"自然语言", r"分词", r"新词发现", r"词性标注",
            r"命名实体", r"\bner\b", r"句法", r"语法", r"语义", r"篇章",
            r"文本分类", r"情感分析", r"情感分类", r"舆情", r"机器翻译",
            r"翻译", r"摘要", r"问答", r"信息抽取", r"知识图谱", r"关系抽取",
            r"关键词", r"主题模型", r"\bcrf\b",
            r"条件随机场", r"\bhmm\b", r"隐马尔可夫", r"序列标注",
            r"阅读理解", r"文本匹配", r"文本生成", r"对联", r"写诗",
            r"作词", r"\blda\b", r"实体识别", r"实体链接", r"实体关系",
            r"联合抽取", r"事件抽取", r"标题生成", r"字标注", r"词法",
            r"依存", r"检索增强", r"\brag\b", r"文本摘要", r"语言理解",
            r"语言识别", r"聊天机器人", r"\bocr\b", r"完形填空", r"语料",
            r"维基百科", r"词汇", r"用词造句", r"搜出来的文本", r"globalpointer",
        ),
    ),
    Topic(
        topic_id="optimization",
        name="优化与训练",
        enabled_by_default=True,
        title_rules=(
            r"优化器", r"优化", r"\bsgd\b", r"\badam\b", r"adamw",
            r"梯度下降", r"梯度", r"学习率", r"动量", r"momentum",
            r"warm-?up", r"权重衰减", r"weight.?decay", r"训练技巧",
            r"训练(?!集)", r"损失函数", r"损失", r"\bloss\b", r"泛化",
            r"generalization", r"收敛", r"共轭梯度", r"牛顿法", r"l-?bfgs",
            r"\blars\b", r"\blamb\b", r"lookahead", r"对抗训练",
            r"知识蒸馏", r"蒸馏", r"混合精度", r"分布式训练", r"并行训练",
            r"参数初始化", r"初始化", r"方差缩减", r"variance reduction",
            r"过拟合", r"欠拟合", r"早停", r"\blsn\b", r"\bmuon\b", r"\bmup\b",
            r"最速下降", r"正则", r"teacher ?forcing", r"\bteaforn\b",
            r"\bqk-?clip\b", r"scaleup",
        ),
    ),
    Topic(
        topic_id="dl-basics",
        name="深度学习基础",
        enabled_by_default=True,
        title_rules=(
            r"神经网络", r"深度学习", r"\bkeras\b", r"\bcnn\b", r"卷积",
            r"\brnn\b", r"\blstm\b", r"\bgru\b", r"循环神经网络", r"残差",
            r"\bresnet\b", r"激活函数", r"\brelu\b", r"\bswish\b", r"\bmish\b",
            r"池化", r"pooling", r"dropout", r"dropconnect", r"batch ?norm",
            r"层归一化", r"归一化", r"自编码器", r"autoencoder", r"感知机",
            r"反向传播", r"\bbp\b", r"seq2seq", r"编码器", r"解码器",
            r"深度网络", r"网络结构", r"机器学习", r"tensorflow",
            r"多标签分类", r"分类器", r"胶囊网络", r"pool层", r"k-?nn",
            r"k近邻", r"聚类", r"支持向量", r"\bsvm\b", r"决策树",
            r"随机森林", r"\bxgboost\b", r"树模型", r"\bcapsule\b",
            r"\bk-?means\b", r"数据挖掘", r"apriori", r"\bmnist\b",
            r"\bmobilenet\b", r"\bxception\b", r"图像分类", r"\bconv1d\b",
            r"\bconv2d\b", r"\bmixup\b", r"数据增强", r"验证集", r"测试集",
            r"多任务", r"\bbn\b", r"pre[ -]?norm", r"post[ -]?norm", r"验证码",
        ),
    ),
    Topic(
        topic_id="probability",
        name="概率统计与信息论",
        enabled_by_default=True,
        title_rules=(
            r"概率", r"统计", r"贝叶斯", r"bayes", r"先验分布", r"后验分布",
            r"先验", r"后验", r"分布", r"信息熵", r"\b熵\b", r"entropy",
            r"信息论", r"信息量", r"自信息", r"\bkl\b", r"kl散度",
            r"互信息", r"mutual information", r"似然", r"最大熵", r"期望",
            r"方差", r"采样", r"\bmcmc\b", r"蒙特卡罗", r"蒙特卡洛",
            r"随机过程", r"高斯", r"gaussian", r"正态分布", r"中心极限",
            r"大数定律", r"假设检验", r"显著性", r"卡方", r"泊松",
            r"\bpoisson\b", r"指数族", r"\bcopula\b", r"divergence",
            r"交叉熵", r"cross.?entropy", r"\bgumbel\b", r"狄利克雷",
            r"dirichlet", r"二项分布", r"多项分布", r"无偏估计", r"估计量",
            r"\bem\b ?算法", r"最大似然", r"logistic回归", r"逻辑回归",
            r"狄拉克", r"测度论", r"sigma代数",
        ),
    ),
    Topic(
        topic_id="geometry",
        name="几何与方程",
        enabled_by_default=True,
        title_rules=(
            r"几何", r"曲线", r"曲面", r"曲率", r"流形", r"manifold",
            r"微分方程", r"方程", r"\bode\b", r"\bpde\b", r"常微分",
            r"偏微分", r"不动点", r"混沌", r"动力系统", r"哈密顿",
            r"hamilton", r"拉格朗日", r"lagrang", r"对称性", r"symmetry",
            r"拓扑", r"topolog", r"群论", r"李群", r"锥面", r"椭圆",
            r"双曲", r"抛物线", r"抛物面", r"三角形", r"相空间",
            r"最速降线", r"旋轮线", r"摆线", r"悬链线", r"测地线",
            r"等周", r"圆内", r"外摆线", r"渐开线", r"斐波那契",
            r"黄金分割", r"圆锥曲",
        ),
    ),
    Topic(
        topic_id="math",
        name="数学工具",
        enabled_by_default=True,
        title_rules=(
            r"数学", r"微积分", r"积分", r"微分", r"线性代数", r"矩阵",
            r"行列式", r"特征值", r"特征向量", r"泰勒", r"taylor",
            r"傅里叶", r"fourier", r"拉普拉斯", r"laplace", r"复变函数",
            r"复数", r"解析函数", r"解析延拓", r"数列", r"级数", r"极限",
            r"不等式", r"柯西", r"cauchy", r"伽马函数", r"\bgamma\b ?函数",
            r"贝塞尔", r"bessel", r"变分法", r"泛函", r"格林函数",
            r"数值方法", r"数值计算", r"插值", r"数论", r"素数", r"欧拉",
            r"euler", r"恒等式", r"迭代法", r"阶乘", r"组合数学", r"排列",
            r"递推", r"差分", r"向量空间", r"张量", r"正交", r"投影",
            r"集合论", r"逻辑", r"证明", r"定理", r"公式", r"数学分析",
            r"代数", r"抽象代数", r"环论", r"域论", r"测度", r"空间分解",
            r"基底", r"正交基", r"奇异值", r"\bsvd\b", r"最小二乘",
            r"多项式", r"圆周率", r"\bpi\b", r"自然常数", r"对数",
            r"指数函数", r"三角函数", r"双曲函数", r"特殊函数",
            r"超几何", r"椭圆积分", r"求和", r"求解", r"计算技巧",
            r"cur分解", r"johnson", r"lindenstrauss", r"维度灾难", r"子集",
            r"幂迭代",
        ),
    ),
    # ---- 以下 9 个主题默认不启用（属于第二套分类全集，可用 --all-topics 打开） ----
    Topic(
        topic_id="engineering",
        name="工程工具",
        title_rules=(
            r"python", r"工具", r"软件", r"输入法", r"linux", r"\bgit\b",
            r"服务器", r"网站", r"浏览器", r"\bapi\b", r"数据库", r"编程",
            r"代码", r"脚本", r"环境", r"部署", r"终端", r"windows",
            r"matlab", r"爬虫", r"效率", r"办公", r"预处理", r"可视化",
            r"画图", r"作图",
        ),
    ),
    Topic(topic_id="astronomy", name="天文科普"),
    Topic(topic_id="phychem", name="物理化学"),
    Topic(topic_id="biology", name="生物自然"),
    Topic(topic_id="photography", name="图片摄影"),
    Topic(topic_id="qa", name="科普问答与百科"),
    Topic(topic_id="site", name="资源与站务"),
    Topic(topic_id="essay", name="阅读写作与随笔"),
    Topic(topic_id="misc", name="其他"),
)

TOPIC_BY_ID: dict[str, Topic] = {t.topic_id: t for t in TOPICS}


# ---------------------------------------------------------------------------
# 站点原生分类 → 主题 的映射与门控
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NativeCategory:
    slug: str
    name: str
    # 允许归入的主题（按全局优先级过滤后再匹配）
    allowed_topics: tuple[str, ...] = ()
    # 标题规则全部未命中时的兜底主题
    fallback_topic: str = "misc"


NATIVE_CATEGORIES: dict[str, NativeCategory] = {
    "Big-Data": NativeCategory(
        slug="Big-Data",
        name="信息时代",
        allowed_topics=(
            "embedding", "llm", "generative", "nlp", "optimization",
            "dl-basics", "probability", "geometry", "math", "engineering",
        ),
        fallback_topic="engineering",
    ),
    "Mathematics": NativeCategory(
        slug="Mathematics",
        name="数学研究",
        allowed_topics=(
            "math", "probability", "geometry", "optimization",
            "dl-basics", "generative", "embedding", "llm", "nlp",
        ),
        fallback_topic="math",
    ),
    "Everything": NativeCategory(
        slug="Everything",
        name="千奇百怪",
        allowed_topics=tuple(TOPIC_BY_ID),
        fallback_topic="misc",
    ),
    "Astronomy": NativeCategory(slug="Astronomy", name="天文探索", fallback_topic="astronomy"),
    "Phy-chem": NativeCategory(slug="Phy-chem", name="物理化学", fallback_topic="phychem"),
    "Biology": NativeCategory(slug="Biology", name="生物自然", fallback_topic="biology"),
    "Photograph": NativeCategory(slug="Photograph", name="图片摄影", fallback_topic="photography"),
    "Questions": NativeCategory(slug="Questions", name="问题百科", fallback_topic="qa"),
    "Life-Feeling": NativeCategory(slug="Life-Feeling", name="生活/情感", fallback_topic="essay"),
    "Resources": NativeCategory(slug="Resources", name="资源共享", fallback_topic="site"),
}

# 默认抓取的原生分类：9 个目标主题的文章几乎全部来自这两类 + 千奇百怪
DEFAULT_SOURCE_CATEGORIES: tuple[str, ...] = ("Big-Data", "Mathematics", "Everything")

# 抓取优先级（多分类去重时，排在前面的原生分类作为文章的主分类）
CRAWL_PRIORITY: tuple[str, ...] = ("Big-Data", "Mathematics", "Everything")


# ---------------------------------------------------------------------------
# 分类器
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CompiledRule:
    topic_id: str
    pattern: "re.Pattern[str]"


_RULES: list[CompiledRule] = []


def _ascii_boundary(pattern: str) -> str:
    r"""把首尾的 \b 换成只针对 ASCII 字母数字的边界。

    中文标题里汉字也算 \w，导致 "MoE环" 不满足 \bMoE\b；
    用 ASCII-only 边界后既能匹配 "MoE环"，也不会误匹配 "demo"。
    """
    if pattern.startswith(r"\b"):
        pattern = r"(?<![a-zA-Z0-9])" + pattern[2:]
    if pattern.endswith(r"\b"):
        pattern = pattern[:-2] + r"(?![a-zA-Z0-9])"
    return pattern


for _topic in TOPICS:
    for _rule in _topic.title_rules:
        _RULES.append(
            CompiledRule(
                _topic.topic_id,
                re.compile(_ascii_boundary(_rule), re.IGNORECASE),
            )
        )


def classify_title(title: str, native_slug: str) -> str:
    """把一篇文章按标题 + 原生分类归入一个主题，返回 topic_id。"""
    native = NATIVE_CATEGORIES.get(native_slug)
    if native is None:
        return "misc"

    # 该原生分类只映射到自身主题（天文/物理等），无标题规则可走
    if not native.allowed_topics:
        return native.fallback_topic

    allowed = set(native.allowed_topics)
    for rule in _RULES:
        if rule.topic_id in allowed and rule.pattern.search(title):
            return rule.topic_id

    return native.fallback_topic


def topic_name(topic_id: str) -> str:
    topic = TOPIC_BY_ID.get(topic_id)
    return topic.name if topic else topic_id


def resolve_topic_ids(
    requested: list[str] | None, all_topics: bool = False
) -> tuple[str, ...]:
    """解析命令行传入的主题参数，返回按 TOPICS 定义顺序排列的 topic_id 元组。"""
    if all_topics:
        return tuple(t.topic_id for t in TOPICS)
    if not requested:
        return DEFAULT_TOPIC_IDS

    unknown = [r for r in requested if r not in TOPIC_BY_ID]
    if unknown:
        raise SystemExit(
            f"[error] 未知主题: {', '.join(unknown)}。可用主题: "
            + ", ".join(f"{t.topic_id}({t.name})" for t in TOPICS)
        )
    order = {t.topic_id: i for i, t in enumerate(TOPICS)}
    return tuple(sorted(dict.fromkeys(requested), key=lambda r: order[r]))
