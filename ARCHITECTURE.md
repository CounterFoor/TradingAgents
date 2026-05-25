# TradingAgents 架构文档

## 1. 项目概览

TradingAgents 是一个基于 **LangGraph** 的多智能体（Multi-Agent）金融交易分析框架。它通过编排多个 LLM 驱动的 Agent 协作，对给定的股票（或加密货币）进行全方位分析，最终输出交易决策。

---

## 2. 目录结构

```
TradingAgents/
├── cli/main.py                      # CLI 入口 (typer)
├── main.py                          # 程序化入口
├── pyproject.toml                   # 项目依赖与元数据
├── requirements.txt                 # pip 依赖
├── .env                             # 环境变量配置
├── .env.example                     # 环境变量模板
│
├── tradingagents/
│   ├── default_config.py            # 默认配置字典
│   │
│   ├── dataflows/                   # ★ 数据流层 (Vendor 路由)
│   │   ├── interface.py             #   核心路由: route_to_vendor()
│   │   ├── config.py                #   配置管理
│   │   ├── utils.py                 #   工具函数
│   │   ├── stockstats_utils.py      #   stockstats + yfinance 缓存
│   │   ├── y_finance.py             #   Yahoo Finance 供应商
│   │   ├── yfinance_news.py         #   Yahoo Finance 新闻
│   │   ├── alpha_vantage_common.py  #   Alpha Vantage 公共模块
│   │   ├── alpha_vantage_stock.py   #   Alpha Vantage 股票数据
│   │   ├── alpha_vantage_indicator.py # Alpha Vantage 技术指标
│   │   ├── alpha_vantage_fundamentals.py # Alpha Vantage 基本面
│   │   ├── alpha_vantage_news.py    #   Alpha Vantage 新闻
│   │   ├── alpha_vantage.py         #   Alpha Vantage 统一导出
│   │   ├── akshare_stock.py         #   AKShare 供应商 (A股)
│   │   ├── akshare.py               #   AKShare 统一导出
│   │   ├── reddit.py                #   Reddit 社交情绪
│   │   └── stocktwits.py            #   StockTwits 社交情绪
│   │
│   ├── agents/                      # ★ 智能体层
│   │   ├── __init__.py              #   统一导出所有 agent 工厂
│   │   ├── schemas.py               #   结构化输出 Pydantic 模型
│   │   │
│   │   ├── analysts/                #   分析型 Agent (Phase 1)
│   │   │   ├── market_analyst.py    #     市场分析师 (K线+指标)
│   │   │   ├── fundamentals_analyst.py #   基本面分析师
│   │   │   ├── news_analyst.py      #     新闻分析师
│   │   │   ├── sentiment_analyst.py #     情绪分析师 (预取新闻+StockTwits+Reddit)
│   │   │   └── social_media_analyst.py #  向后兼容 shim
│   │   │
│   │   ├── researchers/             #   辩论型 Agent (Phase 2)
│   │   │   ├── bull_researcher.py   #     多头研究员
│   │   │   └── bear_researcher.py   #     空头研究员
│   │   │
│   │   ├── managers/                #   管理型 Agent
│   │   │   ├── research_manager.py  #     研究经理 (Phase 2 裁决)
│   │   │   └── portfolio_manager.py #     投资组合经理 (Phase 4 裁决)
│   │   │
│   │   ├── trader/                  #   交易员 Agent (Phase 3)
│   │   │   └── trader.py
│   │   │
│   │   ├── risk_mgmt/              #   风险辩论 Agent (Phase 4)
│   │   │   ├── aggressive_debator.py
│   │   │   ├── conservative_debator.py
│   │   │   └── neutral_debator.py
│   │   │
│   │   └── utils/
│   │       ├── agent_states.py      #   AgentState TypedDict
│   │       ├── agent_utils.py       #   工具导入 + 辅助函数
│   │       ├── core_stock_tools.py  #   @tool get_stock_data
│   │       ├── technical_indicators_tools.py # @tool get_indicators
│   │       ├── fundamental_data_tools.py # @tool get_fundamentals 等
│   │       ├── news_data_tools.py   #   @tool get_news 等
│   │       ├── structured.py        #   结构化输出绑定
│   │       ├── memory.py            #   交易记忆日志系统
│   │       └── rating.py            #   评级工具
│   │
│   ├── graph/                       # ★ 图编排层
│   │   ├── trading_graph.py         #   TradingAgentsGraph 主类
│   │   ├── setup.py                 #   GraphSetup 图构建
│   │   ├── propagation.py           #   Propagator 初始状态+参数
│   │   ├── conditional_logic.py     #   条件边逻辑
│   │   ├── analyst_execution.py     #   分析师执行计划
│   │   ├── signal_processing.py     #   信号提取
│   │   ├── reflection.py            #   反思生成器
│   │   └── checkpointer.py          #   断点续跑
│   │
│   └── llm_clients/                 # ★ LLM 客户端层
│       ├── __init__.py              #   create_llm_client() 工厂
│       └── ...                      #   各供应商客户端
│
├── tests/
├── scripts/
└── assets/ / build/
```

---

## 3. 核心架构分层

```
   ┌──────────────────────────────────────────┐
   │              CLI / Entry Point           │  cli/main.py, main.py
   │     (typer CLI, dotenv 加载, 用户交互)      │
   └──────────────┬───────────────────────────┘
                  │
   ┌──────────────▼───────────────────────────┐
   │        TradingAgentsGraph (主编排器)       │  graph/trading_graph.py
   │   ┌──────────────────────────────────┐   │
   │   │        LangGraph StateGraph       │   │  graph/setup.py
   │   │    (节点 + 边 + 条件逻辑 + 状态)    │   │
   │   └──────────────────────────────────┘   │
   └──────────────┬───────────────────────────┘
                  │
   ┌──────────────▼───────────────────────────┐
   │            Agent 层 (LLM + Tools)         │  agents/
   │                                          │
   │  Phase 1: 并行分析                        │
   │  ┌────────┬────────┬────────┬────────┐   │
   │  │ Market │ News   │ Fund.  │ Sent.  │   │
   │  │Analyst │Analyst │Analyst │Analyst │   │
   │  └───┬────┴───┬────┴───┬────┴───┬────┘   │
   │      │        │        │        │         │
   │  Phase 2: Bull ↔ Bear 辩论 → Research Mgr │
   │  Phase 3: Trader                          │
   │  Phase 4: 风险辩论 → Portfolio Manager     │
   └──────────────┬───────────────────────────┘
                  │ 调用 @tool 装饰的函数
   ┌──────────────▼───────────────────────────┐
   │        数据路由层 (Vendor Routing)         │  dataflows/interface.py
   │                                          │
   │    route_to_vendor(method, *args)         │
   │         │                                 │
   │    ┌────┴────┬─────┬──────┐               │
   │    ▼         ▼     ▼      ▼               │
   │ yfinance  alpha_vantage  akshare  ...     │
   │                                              │
   │    fallback: 限流/不支持 → 自动回退下一家   │
   └──────────────────────────────────────────┘
```

---

## 4. 数据流层 (Dataflows)

### 4.1 路由机制

核心函数 `route_to_vendor(method, *args)` 实现多供应商自动路由与回退：

```python
route_to_vendor("get_stock_data", "000001", "2024-01-01", "2024-12-31")
  │
  ├─ 1. get_category_for_method("get_stock_data") → "core_stock_apis"
  │
  ├─ 2. get_vendor("core_stock_apis", "get_stock_data")
  │      ├─ tool_vendors["get_stock_data"]?      # 工具级覆盖
  │      └─ data_vendors["core_stock_apis"]      # 类别级默认
  │         → "akshare, yfinance"
  │
  ├─ 3. fallback_chain = ["akshare", "yfinance", "alpha_vantage"]
  │
  └─ 4. for vendor in fallback_chain:
            try:  return VENDOR_METHODS[method][vendor](*args)
            except AKShareUnsupportedError:    continue
            except YFRateLimitError:           continue
            except AlphaVantageRateLimitError: continue
         raise RuntimeError("No available vendor")
```

### 4.2 支持的供应商

| 供应商 | 类型 | 认证 | 主要覆盖 |
|--------|------|------|---------|
| **yfinance** | 默认首选 | 无需 key | 美股、全球市场 |
| **Alpha Vantage** | 回退/可选 | `ALPHA_VANTAGE_API_KEY` | 美股、技术指标 API |
| **AKShare** | 可选 | 无需 key | **A 股** (6位代码)、港股 |

### 4.3 数据类别与方法映射

| 类别 | 方法 | yfinance | alpha_vantage | akshare |
|------|------|----------|---------------|---------|
| `core_stock_apis` | `get_stock_data` | ✓ | ✓ | ✓ (A股/港股) |
| `technical_indicators` | `get_indicators` | ✓ (stockstats) | ✓ (API) | ✓ (A股+stockstats) |
| `fundamental_data` | `get_fundamentals` | ✓ | ✓ | ✓ (A股) |
| | `get_balance_sheet` | ✓ | ✓ | ✓ (A股) |
| | `get_cashflow` | ✓ | ✓ | ✓ (A股) |
| | `get_income_statement` | ✓ | ✓ | ✓ (A股) |
| `news_data` | `get_news` | ✓ | ✓ | ✓ (A股) |
| | `get_global_news` | ✓ | ✓ | ✗ |
| | `get_insider_transactions` | ✓ | ✓ | ✗ |

---

## 5. Agent 层

### 5.1 Agent 工厂模式

所有 Agent 遵循统一的工厂模式：

```python
def create_<agent_name>(llm):
    def <agent_name>_node(state: AgentState) -> dict:
        # 1. 提取 state 字段
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        # 2. 定义工具列表
        tools = [get_stock_data, get_indicators]

        # 3. 构建 Prompt（系统消息 + 工具描述 + 日期上下文）
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt + tool_descriptions + date_context),
            MessagesPlaceholder(variable_name="messages"),
        ])

        # 4. 绑定工具并调用
        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])

        # 5. 返回状态更新（report 仅在最终回复时填充）
        return {"messages": [result], "market_report": report}
    return <agent_name>_node
```

### 5.2 Agent 列表

| Agent | 文件 | 绑定工具 | 输出字段 |
|-------|------|----------|---------|
| **Market Analyst** | `analysts/market_analyst.py` | `get_stock_data`, `get_indicators` | `market_report` |
| **Fundamentals Analyst** | `analysts/fundamentals_analyst.py` | `get_fundamentals`, `get_balance_sheet`, `get_cashflow`, `get_income_statement` | `fundamentals_report` |
| **News Analyst** | `analysts/news_analyst.py` | `get_news`, `get_global_news` | `news_report` |
| **Sentiment Analyst** | `analysts/sentiment_analyst.py` | 无（预取数据注入 prompt） | `sentiment_report` |
| **Bull Researcher** | `researchers/bull_researcher.py` | 无 | `investment_debate_state` |
| **Bear Researcher** | `researchers/bear_researcher.py` | 无 | `investment_debate_state` |
| **Research Manager** | `managers/research_manager.py` | 无（结构化输出） | `investment_plan` |
| **Trader** | `trader/trader.py` | 无（结构化输出） | `trader_investment_plan` |
| **Aggressive Debator** | `risk_mgmt/aggressive_debator.py` | 无 | `risk_debate_state` |
| **Conservative Debator** | `risk_mgmt/conservative_debator.py` | 无 | `risk_debate_state` |
| **Neutral Debator** | `risk_mgmt/neutral_debator.py` | 无 | `risk_debate_state` |
| **Portfolio Manager** | `managers/portfolio_manager.py` | 无（结构化输出） | `final_trade_decision` |

### 5.3 可用工具函数

| 工具 | 文件 | 路由方法 | 说明 |
|------|------|----------|------|
| `get_stock_data` | `core_stock_tools.py` | `get_stock_data` | OHLCV 历史数据 |
| `get_indicators` | `technical_indicators_tools.py` | `get_indicators` | 技术指标 (支持逗号分隔多指标) |
| `get_fundamentals` | `fundamental_data_tools.py` | `get_fundamentals` | 公司基本面 |
| `get_balance_sheet` | `fundamental_data_tools.py` | `get_balance_sheet` | 资产负债表 |
| `get_cashflow` | `fundamental_data_tools.py` | `get_cashflow` | 现金流量表 |
| `get_income_statement` | `fundamental_data_tools.py` | `get_income_statement` | 利润表 |
| `get_news` | `news_data_tools.py` | `get_news` | 个股新闻 |
| `get_global_news` | `news_data_tools.py` | `get_global_news` | 宏观经济新闻 |
| `get_insider_transactions` | `news_data_tools.py` | `get_insider_transactions` | 内幕交易 |

---

## 6. 图编排层 (LangGraph)

### 6.1 完整工作流

```
START
  │
  ├── Phase 1: 并行分析 ──────────────────────────────
  │   ├── Market Analyst  ──→  market_report
  │   ├── Sentiment Analyst ──→ sentiment_report
  │   ├── News Analyst     ──→  news_report
  │   └── Fundamentals Analyst ──→ fundamentals_report
  │
  ├── Phase 2: 投资辩论 ──────────────────────────────
  │   (循环 max_debate_rounds 轮)
  │   Bull Researcher → Bear Researcher → Research Manager
  │                                          └─→ investment_plan
  │
  ├── Phase 3: 交易执行 ─────────────────────────────
  │   Trader ──→ trader_investment_plan
  │
  ├── Phase 4: 风险辩论 ─────────────────────────────
  │   (循环 max_risk_discuss_rounds 轮)
  │   Aggressive → Conservative → Neutral → Portfolio Manager
  │                                            └─→ final_trade_decision
  │
  └── Phase 5: 记忆存储 ─────────────────────────────
      MemoryLog.store_decision()
```

### 6.2 条件边逻辑

- **Analyst 循环**：每个分析师的 agent node → tool node → agent node，直到 LLM 输出非工具调用的最终报告
- **辩论循环**：Bull/Bear Researcher 交替发言，由 `conditional_logic.should_continue_debate` 根据轮次计数裁决
- **风险循环**：Aggressive → Conservative → Neutral 轮流发言，由 `should_continue_risk_analysis` 裁决

---

## 7. 全局状态 (AgentState)

```python
class AgentState(MessagesState):
    company_of_interest: str       # 股票代码
    asset_type: str                # "stock" 或 "crypto"
    trade_date: str                # 交易日期 YYYY-mm-dd
    sender: str                    # 最后发言的 Agent

    # Phase 1 输出
    market_report: str
    sentiment_report: str
    news_report: str
    fundamentals_report: str

    # Phase 2
    investment_debate_state: InvestDebateState
    investment_plan: str

    # Phase 3
    trader_investment_plan: str

    # Phase 4
    risk_debate_state: RiskDebateState
    final_trade_decision: str

    # Phase 5 (记忆)
    past_context: str
```

### InvestDebateState

```python
class InvestDebateState(TypedDict):
    bull_history: str          # 多头对话历史
    bear_history: str          # 空头对话历史
    history: str               # 完整辩论历史
    current_response: str      # 最新回应
    judge_decision: str        # 研究经理最终裁决
    count: int                 # 辩论轮次
```

### RiskDebateState

```python
class RiskDebateState(TypedDict):
    aggressive_history: str     # 激进分析师对话
    conservative_history: str   # 保守分析师对话
    neutral_history: str        # 中立分析师对话
    history: str                # 完整风险辩论历史
    latest_speaker: str         # 最后发言者
    current_aggressive_response: str
    current_conservative_response: str
    current_neutral_response: str
    judge_decision: str         # PM 最终裁决
    count: int
```

---

## 8. 配置系统

### 8.1 优先级（从高到低）

```
1. CLI 参数 (如 --checkpoint)
2. 环境变量 TRADINGAGENTS_* (通过 .env 或系统变量)
3. tool_vendors (工具级供应商覆盖)
4. data_vendors (类别级供应商默认)
5. default_config.py (硬编码默认值)
```

### 8.2 关键配置项

| Key | 默认值 | 说明 |
|-----|--------|------|
| `llm_provider` | `"openai"` | LLM 供应商 |
| `deep_think_llm` | `"gpt-5.4"` | 复杂推理模型 |
| `quick_think_llm` | `"gpt-5.4-mini"` | 快速任务模型 |
| `backend_url` | `None` | 自定义 API 端点 |
| `max_debate_rounds` | `1` | 投资辩论最大轮次 |
| `max_risk_discuss_rounds` | `1` | 风险辩论最大轮次 |
| `checkpoint_enabled` | `False` | 启用断点续跑 |
| `output_language` | `"English"` | 报告输出语言 |
| `data_vendors.*` | `"yfinance"` | 数据供应商（支持逗号分隔回退链） |
| `news_article_limit` | `20` | 每只股票最大新闻数 |
| `global_news_lookback_days` | `7` | 宏观新闻回溯天数 |
| `benchmark_ticker` | `None` | Alpha 计算基准 (自动检测) |
| `analyst_concurrency_limit` | `1` | 分析师并行度 |

### 8.3 供应商配置示例

```python
# 类别级配置 (影响该类别下所有工具)
"data_vendors": {
    "core_stock_apis": "akshare, yfinance",       # A股用AKShare，美股回退yfinance
    "technical_indicators": "akshare, yfinance",
    "fundamental_data": "akshare, yfinance",
    "news_data": "yfinance",
}

# 工具级配置 (覆盖类别级，针对单个工具)
"tool_vendors": {
    "get_stock_data": "akshare",   # 仅股票数据强制走AKShare
}
```

---

## 9. 记忆系统

- **存储位置**: `~/.tradingagents/memory/trading_memory.md`
- **存储格式**: Markdown 文件，每条记录包含交易日期、代码、评级、收益率、Alpha、反思
- **生命周期**:
  1. **Phase 4 完成时** → 写入 Pending 条目（含评级、决策摘要）
  2. **下次同代码运行时** → `_resolve_pending_entries()` 获取实际收益率
  3. **生成反思** → `Reflector.reflect_on_final_decision()` 分析决策对错原因
  4. **更新为 Resolved** → 标记完成，追加反思内容
- **上下文注入**: `get_past_context(ticker)` 返回同代码最近 5 条 + 跨代码最近 3 条历史决策

---

## 10. LLM 供应商适配

`tradingagents/llm_clients/` 通过 `create_llm_client(provider, model, base_url)` 统一创建 LLM 客户端：

| 供应商 | provider 值 | 特有能力 |
|--------|-------------|---------|
| OpenAI | `openai` | `reasoning_effort` |
| Anthropic | `anthropic` | `effort` (思考预算) |
| Google Gemini | `google` | `thinking_level` |
| DeepSeek | `deepseek` | 标准兼容 |
| xAI | `xai` | 标准兼容 |
| DashScope | `dashscope` | 标准兼容 |
| Zhipu (智谱) | `zhipu` | 标准兼容 |
| MiniMax | `minimax` | 标准兼容 |
| Ollama | `ollama` | 本地部署 |
| OpenRouter | `openrouter` | 多模型路由 |

---

## 11. 技术指标清单

| 分类 | 指标名 | 说明 |
|------|--------|------|
| **移动平均** | `close_50_sma` | 50 日简单移动平均 |
| | `close_200_sma` | 200 日简单移动平均 |
| | `close_10_ema` | 10 日指数移动平均 |
| **MACD** | `macd` | MACD 线 |
| | `macds` | MACD 信号线 |
| | `macdh` | MACD 柱状图 |
| **动量** | `rsi` | 相对强弱指标 |
| | `mfi` | 资金流量指标 |
| **KDJ** | `kdjk` | KDJ K 值 (快线) |
| | `kdjd` | KDJ D 值 (慢线) |
| | `kdjj` | KDJ J 值 (背离线) |
| **布林带** | `boll` | 布林带中轨 (20 SMA) |
| | `boll_ub` | 布林带上轨 |
| | `boll_lb` | 布林带下轨 |
| **波动率** | `atr` | 平均真实波幅 |
| **趋势强度** | `adx` | 平均趋向指数 |
| | `dx` | 趋向指数 |
| | `adxr` | ADX 评级 |
| **成交量** | `vwma` | 成交量加权移动平均 |

---

## 12. 扩展指南

### 12.1 添加新数据供应商

```python
# 1. 创建模块 tradingagents/dataflows/new_vendor.py
def get_stock(symbol, start_date, end_date):
    ...

def get_fundamentals(ticker, curr_date=None):
    ...

# 2. 在 interface.py 中注册
from .new_vendor import get_stock as get_new_stock

VENDOR_LIST.append("new_vendor")
VENDOR_METHODS["get_stock_data"]["new_vendor"] = get_new_stock

# 3. 配置中启用
"data_vendors": { "core_stock_apis": "new_vendor, yfinance" }
```

### 12.2 添加新 Agent

```python
# 1. 创建 agents/analysts/my_analyst.py
def create_my_analyst(llm):
    def node(state: AgentState) -> dict:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一个..."),
            MessagesPlaceholder(variable_name="messages"),
        ])
        result = (prompt | llm).invoke(state["messages"])
        return {"my_report": result.content}
    return node

# 2. 在 agents/__init__.py 导出
from .analysts.my_analyst import create_my_analyst

# 3. 在 graph/setup.py 注册节点和边
workflow.add_node("My Analyst", create_my_analyst(llm))
workflow.add_edge("News Analyst", "My Analyst")
workflow.add_edge("My Analyst", "Bull Researcher")
```

---

## 13. 数据流示例：A 股分析全链路

以分析平安银行 (`000001`) 为例，配置 `data_vendors.core_stock_apis = "akshare, yfinance"`：

```
Market Analyst 调用 get_stock_data("000001", "2025-05-20", "2025-05-26")
  │
  route_to_vendor("get_stock_data", "000001", ...)
  │
  ├─ vendor = "akshare"
  │    _is_ashare("000001") → True (6位数字)
  │    ak.stock_zh_a_hist("000001", ...)  →  OHLCV CSV
  │    ← 成功返回数据
  │
  └─ (yfinance 未触发)

Market Analyst 调用 get_indicators("000001", "rsi", "2025-05-26", 30)
  │
  route_to_vendor("get_indicators", "000001", "rsi", ...)
  │
  ├─ vendor = "akshare"
  │    _is_ashare("000001") → True
  │    ak.stock_zh_a_hist(...) → OHLCV → stockstats.wrap() → df["rsi"]
  │    ← 返回 RSI 值序列 + 描述
```

若分析的是美股 `AAPL`：

```
route_to_vendor("get_stock_data", "AAPL", ...)
  │
  ├─ vendor = "akshare"
  │    _is_ashare("AAPL") → False
  │    raise AKShareUnsupportedError("AKShare only supports A-share...")
  │    route_to_vendor 捕获 → continue
  │
  ├─ vendor = "yfinance"
  │    yf.Ticker("AAPL").history(...) → OHLCV CSV
  │    ← 成功返回数据
```
