# TradingAgents 技术要点指南

本文档面向希望理解本项目代码的初学者，逐一解释项目中使用的关键技术概念、框架和设计模式。

---

## 1. 总览：项目在做什么

TradingAgents 是一个**多智能体（Multi-Agent）股票分析系统**。它让多个 AI 角色（分析师、研究员、交易员、风控经理）协作完成一只股票的研究，最终输出买卖决策。

```
用户输入：股票代码 + 日期
         │
         ▼
  ┌──────────────────┐
  │  多个 AI 角色分工协作  │
  │  市场分析师         │
  │  新闻分析师         │
  │  基本面分析师       │
  │  情绪分析师         │  ← 并行分析
  ├──────────────────┤
  │  多头研究员 vs 空头研究员│  ← 辩论
  ├──────────────────┤
  │  研究经理           │  ← 裁决投资计划
  ├──────────────────┤
  │  交易员             │  ← 制定交易方案
  ├──────────────────┤
  │  激进/保守/中立风控   │  ← 辩论
  ├──────────────────┤
  │  投资组合经理        │  ← 最终决策
  └──────────────────┘
         │
         ▼
  输出：买入/持有/卖出 + 分析报告
```

---

## 2. 核心技术框架：LangGraph

### 2.1 什么是 LangGraph？

LangGraph 是 LangChain 生态中的一个框架，用于构建**有向图（Directed Graph）** 形式的工作流。你可以把图想象成一张流程图：

```
[节点 A] ──→ [节点 B] ──→ [节点 C]
   │                        │
   └──(条件)──→ [节点 D]────┘
```

- **节点（Node）**：一个处理步骤，比如一个 AI 调用
- **边（Edge）**：节点之间的连接，表示执行顺序
- **条件边（Conditional Edge）**：根据当前状态决定走哪条路

### 2.2 本项目中的图

项目定义了一个 `StateGraph`（状态图），所有节点共享一个**全局状态** `AgentState`：

```python
workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("Market Analyst", market_analyst_function)
workflow.add_node("Bull Researcher", bull_researcher_function)

# 添加边
workflow.add_edge("Research Manager", "Trader")           # 固定边
workflow.add_conditional_edges("Market Analyst", router)    # 条件边
```

每个节点都是一个 Python 函数，接收当前状态，返回更新。LangGraph 自动将返回值合并到状态中。

### 2.3 关键概念：State（状态）

```python
class AgentState(MessagesState):
    company_of_interest: str   # 股票代码 —— 全局共享
    trade_date: str            # 交易日期 —— 全局共享
    market_report: str         # 市场分析师报告
    fundamentals_report: str   # 基本面分析师报告
    ...
```

这就像一块白板，每个 Agent 在上面写自己的报告，后面的 Agent 读取。

---

## 3. 智能体（Agent）模式

### 3.1 工厂函数模式

每个 Agent 都是一个**工厂函数**：接收 LLM，返回一个节点函数。

```python
def create_market_analyst(llm):
    def market_analyst_node(state: AgentState) -> dict:
        # 1. 从 state 读取输入
        ticker = state["company_of_interest"]
        date = state["trade_date"]
        
        # 2. 构造提示词
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message + tool_descriptions),
            MessagesPlaceholder(variable_name="messages"),
        ])
        
        # 3. 绑定工具并调用 LLM
        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])
        
        # 4. 返回状态更新
        return {"messages": [result], "market_report": report}
    
    return market_analyst_node  # 返回节点函数
```

**为什么用工厂函数？** 因为 LLM 客户端在 `TradingAgentsGraph` 初始化时创建，然后传给各个 Agent 工厂。

### 3.2 Agent 的分类

| 类别 | Agent | 特点 |
|------|-------|------|
| **分析型** | Market / Fundamentals / News / Sentiment | 绑定工具，LLM 自主决定调用哪些工具 |
| **辩论型** | Bull / Bear / Aggressive / Conservative / Neutral | 纯文本对话，不调用工具 |
| **决策型** | Research Manager / Trader / Portfolio Manager | 结构化输出（Pydantic 模型） |

---

## 4. 工具（Tool）系统

### 4.1 什么是 @tool

`@tool` 是 LangChain 的装饰器，将一个普通函数变为 LLM 可以调用的"工具"：

```python
@tool
def get_stock_data(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Retrieve stock price data..."""
    return route_to_vendor("get_stock_data", symbol, start_date, end_date)
```

关键点：
- 函数签名 + 文档字符串 → LLM 理解如何调用
- `Annotated` 类型提示 → 参数描述，LLM 知道每个参数的含义
- 返回 `str` → 工具调用的结果以文本形式返回给 LLM

### 4.2 工具如何绑定到 Agent

```python
# 定义工具列表
tools = [get_stock_data, get_indicators]

# 绑定到 LLM：告诉 LLM 它可以使用这些工具
chain = prompt | llm.bind_tools(tools)

# 调用时，如果 LLM 决定使用工具，result.tool_calls 会包含调用信息
result = chain.invoke(state["messages"])
if result.tool_calls:
    # LLM 想调用工具，LangGraph 会路由到 ToolNode 执行
    pass
else:
    # LLM 直接返回了文本回答
    pass
```

### 4.3 ToolNode 的作用

LangGraph 的 `ToolNode` 是专门用来执行工具调用的节点：

```python
ToolNode([get_stock_data, get_indicators])
```

它的工作：
1. 接收 LLM 决定要调用的工具列表
2. 并发执行所有工具
3. 将结果包装成 `ToolMessage` 返回给 LLM

架构图：

```
LLM 决定调用 get_stock_data("AAPL", ...)
         │
         ▼
    ToolNode 接收请求
         │
         ▼
    get_stock_data("AAPL", ...)   ← 实际的 Python 函数执行
         │
         ▼
    route_to_vendor("get_stock_data", ...)  ← 路由到数据供应商
         │
         ▼
    yfinance / akshare / alpha_vantage  ← 实际拉取数据
         │
         ▼
    结果（字符串） → ToolMessage → 返回给 LLM
```

---

## 5. 数据供应商（Vendor）路由系统

### 5.1 为什么需要路由？

项目支持多个数据源：yfinance（美股）、AKShare（A股）、Alpha Vantage（备选）。不同数据源有不同的可用性和限制。路由系统自动选择可用的数据源。

### 5.2 核心函数：route_to_vendor

```python
def route_to_vendor(method: str, *args, **kwargs):
    # 1. 获取该方法可用的供应商列表
    available = VENDOR_METHODS[method]  # e.g., {"yfinance": fn1, "akshare": fn2}
    
    # 2. 从配置读取用户偏好的供应商顺序
    configured = get_vendor(category, method)  # e.g., "akshare, yfinance"
    
    # 3. 构建回退链：用户偏好 + 其余可用供应商
    fallback_chain = ["akshare", "yfinance", "alpha_vantage"]
    
    # 4. 依次尝试每个供应商
    for vendor in fallback_chain:
        try:
            return available[vendor](*args)  # 调用供应商的实现
        except YFRateLimitError:        # yfinance 限流 → 试下一个
            continue
        except AKShareUnsupportedError: # AKShare 不支持 → 试下一个
            continue
        except ConnectionError:          # 网络错误 → 试下一个
            continue
    
    raise RuntimeError("所有供应商都不可用")
```

### 5.3 VENDOR_METHODS 注册表

```python
VENDOR_METHODS = {
    "get_stock_data": {
        "yfinance": get_YFin_data_online,
        "akshare": get_akshare_stock,
        "alpha_vantage": get_alpha_vantage_stock,
    },
    "get_fundamentals": {
        "yfinance": get_yfinance_fundamentals,
        "akshare": get_akshare_fundamentals,
        "alpha_vantage": get_alpha_vantage_fundamentals,
    },
    # ... 每个方法都注册了所有供应商的实现
}
```

### 5.4 回退链示例

```
get_stock_data("600036", "2025-05-20", "2025-05-26")
  │
  ├→ akshare: 成功 → 返回数据 ✓
  │  (美股则: akshare → AKShareUnsupportedError → 回退到 yfinance)
  │
  yfinance: 限流 → YFRateLimitError → 自动回退
  alpha_vantage: 网络错误 → ConnectionError → 自动回退
```

---

## 6. 条件边（Conditional Edge）和路由逻辑

### 6.1 分析师的工具循环

每个分析师在产出最终报告前可能需要多次调用工具：

```
[Market Analyst] ──(有 tool_calls?)──→ [tools_market (执行工具)]
       │                                       │
       └──(无 tool_calls)──→ [Msg Clear]       │
              │                    ↑            │
              ▼                    └────────────┘
          进入下一阶段           (返回给 Analyst 继续)
```

代码实现：

```python
def should_continue_market(self, state):
    last_message = state["messages"][-1]
    if last_message.tool_calls:          # LLM 还想调用工具
        return "tools_market"            # 路由到工具节点
    return "Msg Clear Market"            # 清除消息，进入下一阶段
```

### 6.2 辩论循环

Bull ↔ Bear 交替辩论，由计数器控制轮次：

```python
def should_continue_debate(self, state):
    count = state["investment_debate_state"]["count"]
    if count >= 2 * max_debate_rounds:      # 达到最大轮次
        return "Research Manager"           # 结束辩论
    if state["current_response"].startswith("Bull"):
        return "Bear Researcher"            # 轮到 Bear 发言
    return "Bull Researcher"                # 轮到 Bull 发言
```

```
Bull Researcher → Bear Researcher → (计数+1)
      ↑                  │
      └──────────────────┘
      (直到达到最大轮次)
            │
            ▼
    Research Manager（裁决）
```

### 6.3 风险辩论循环

三个角色轮流发言：

```
Aggressive → Conservative → Neutral → (计数+1)
     ↑                            │
     └────────────────────────────┘
     (直到达到最大轮次)
            │
            ▼
    Portfolio Manager（最终决策）
```

---

## 7. 提示词（Prompt）工程

### 7.1 提示词结构

每个分析型 Agent 的提示词由三部分组成：

```
[共享前文]          You are a helpful AI assistant...
                    You have access to: {tool_names}
                    当前日期：{current_date}
                    分析对象：{instrument_context}

[自定义指令]        Market Analyst 的专属指示...
                    可用指标列表：RSI, MACD, KDJ...

[语言指令]          Write your entire response in Chinese.
```

### 7.2 Agents 如何看到彼此的报告

通过 `state` 传递：

```python
# Bull Researcher 的提示词中注入所有报告
prompt = f"""
Market Report: {state['market_report']}
News Report: {state['news_report']}
Fundamentals Report: {state['fundamentals_report']}
Sentiment Report: {state['sentiment_report']}
Previous Debate: {state['investment_debate_state']['history']}
"""
```

---

## 8. 结构化输出（Structured Output）

### 8.1 什么是结构化输出？

让 LLM 返回一个固定的 JSON 格式，而非自由文本：

```python
class ResearchPlan(BaseModel):
    recommendation: PortfolioRating  # 枚举：BUY/HOLD/SELL...
    rationale: str                   # 理由
    strategic_actions: str           # 战略行动

# 绑定：告诉 LLM 必须返回符合这个 Schema 的 JSON
structured_llm = llm.with_structured_output(ResearchPlan)
result = structured_llm.invoke(prompt)
# result 是一个 ResearchPlan 实例，不是字符串
```

### 8.2 降级机制

并非所有 LLM 供应商都支持 `with_structured_output`。项目实现了降级：

```python
def invoke_structured_or_freetext(structured_llm, plain_llm, prompt, render, name):
    try:
        result = structured_llm.invoke(prompt)  # 尝试结构化
        return render(result)                     # 渲染为 Markdown
    except Exception:
        response = plain_llm.invoke(prompt)       # 降级为纯文本
        return response.content
```

---

## 9. 并发执行机制

### 9.1 分析师并行

四个分析师在 Phase 1 中**顺序执行**（当前设计），但每个分析师的**工具调用是并发的**：

```python
# ToolNode 使用线程池执行工具
with get_executor_for_config(config) as executor:
    outputs = list(executor.map(self._run_one, tool_calls, ...))
```

多个工具调用（如同时请求 RSI 和 MACD）会并行执行，加速数据获取。

### 9.2 辩论串行

辩论型 Agent 必须是串行的——每一步都依赖上一步的输出。

---

## 10. 记忆系统（Memory Log）

### 10.1 作用

记录每次分析的历史决策，下次运行时供 Portfolio Manager 参考。

### 10.2 存储格式

Markdown 文件 `~/.tradingagents/memory/trading_memory.md`：

```markdown
## [2025-05-20 | AAPL | Buy | pending]
- Rating: Buy
- Price Target: $250
---

## [2025-05-13 | AAPL | Sell | +3.2%]
- Rating: Sell
- Actual Return: +3.2%
- Alpha: +1.5%
- Reflection: 正确判断了超买信号...
---
```

### 10.3 生命周期

1. **分析完成时**：写入 Pending 条目（含评级，不含收益率）
2. **下次同股票运行时**：获取实际收益率，更新为 Resolved
3. **生成反思**：LLM 分析决策对错原因

---

## 11. 配置系统（Config）

### 11.1 配置优先级

```
CLI 参数 > 环境变量 > 配置文件 > 默认值
```

### 11.2 关键配置项

```python
DEFAULT_CONFIG = {
    # LLM 设置
    "llm_provider": "openai",         # LLM 供应商
    "deep_think_llm": "gpt-5.4",      # 复杂任务模型
    "quick_think_llm": "gpt-5.4-mini",# 简单任务模型
    
    # 数据供应商
    "data_vendors": {
        "core_stock_apis": "akshare, yfinance",      # 股票数据
        "technical_indicators": "akshare, yfinance", # 技术指标
        "fundamental_data": "akshare, yfinance",     # 基本面
        "news_data": "yfinance",                     # 新闻
    },
    
    # 辩论轮次
    "max_debate_rounds": 1,           # Bull/Bear 辩论轮次
    "max_risk_discuss_rounds": 1,     # 风险辩论轮次
    
    # 输出
    "output_language": "English",     # 输出语言
}
```

### 11.3 通过 .env 覆盖

```bash
# .env 文件
TRADINGAGENTS_LLM_PROVIDER=deepseek
TRADINGAGENTS_OUTPUT_LANGUAGE=Chinese
ALPHA_VANTAGE_API_KEY=your_key_here
```

加载机制：`cli/main.py` 开头的 `load_dotenv()` 读取 `.env`，`default_config.py` 中的 `_apply_env_overrides()` 将 `TRADINGAGENTS_*` 环境变量映射到配置键。

---

## 12. 完整数据流示例

以分析 **招商银行（600036）** 为例：

```
用户输入: tradingagents analyze → 选择 600036, 2025-05-26
  │
  ▼
Phase 1 ──────────────────────────────────────────────
  Market Analyst 节点
    │  LLM 决定调用工具
    │  get_stock_data("600036", "2025-05-20", "2025-05-26")
    │    → route_to_vendor("get_stock_data", ...)
    │    → akshare → Sina Finance → OHLCV CSV
    │  get_indicators("600036", "rsi", "2025-05-26", 60)
    │    → route_to_vendor → akshare + stockstats → RSI值
    │  LLM 撰写市场报告 → market_report
  Fundamentals Analyst 节点
    │  get_fundamentals("600036") → AKShare → 财务摘要
    │  get_balance_sheet("600036") → AKShare + 同花顺 → 资产负债表
    │  LLM 撰写基本面报告 → fundamentals_report
  News Analyst / Sentiment Analyst 同理

Phase 2 ──────────────────────────────────────────────
  Bull Researcher 撰写看多论点
  Bear Researcher 撰写看空论点
  Research Manager 裁决 → investment_plan

Phase 3 ──────────────────────────────────────────────
  Trader 制定交易方案 → trader_investment_plan

Phase 4 ──────────────────────────────────────────────
  Aggressive / Conservative / Neutral 辩论风险
  Portfolio Manager 最终裁决 → final_trade_decision

Phase 5 ──────────────────────────────────────────────
  MemoryLog.store_decision("600036", "2025-05-26", ...)
```

---

## 附录：技术栈一览

| 技术 | 用途 |
|------|------|
| **Python 3.10+** | 开发语言 |
| **LangGraph** | 多 Agent 工作流编排（状态图） |
| **LangChain** | LLM 调用、工具系统、提示词模板 |
| **LangChain @tool** | 定义 LLM 可调用的工具函数 |
| **yfinance** | Yahoo Finance 美股数据 |
| **AKShare** | 中国 A 股数据（新浪财经 + 同花顺） |
| **Alpha Vantage** | 备选美股数据源 |
| **stockstats** | 技术指标计算（RSI, MACD, KDJ, ADX, BOLL...） |
| **Pydantic** | 结构化输出模型定义 |
| **Typer** | CLI 命令行界面 |
| **Rich** | 终端富文本显示 |
| **python-dotenv** | 环境变量加载 |
