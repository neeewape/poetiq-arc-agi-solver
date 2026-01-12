# LLM 策略迭代系统规格文档

本文档定义基于 LLM 的策略生成—仿真—反馈—修正—终止的闭环系统规格，覆盖模块边界、交互协议、反馈模板、终止规则、状态机，以及数据接口与可追溯性设计。

---

## 1. 系统模块边界

### 1.1 LLM 生成模块（策略/参数/规则）
**职责**
- 读取输入协议中的假设、约束、历史反馈、风险上限等字段。
- 输出新策略（参数、规则、执行逻辑）及改动理由。

**输入**
- `assumptions`、`constraints`、`history_feedback`、`risk_limits`、`strategy_params`。

**输出**
- `strategy`、`change_rationale`、`risk_expectation`、`stop_recommendation`。

**边界**
- 不执行策略仿真。
- 不直接修改历史数据与仿真结果。

### 1.2 仿真环境模块（执行策略并输出指标）
**职责**
- 接收策略定义，执行历史回测或多情景仿真。
- 产出收益、风险、稳健性指标与日志。

**输入**
- `strategy`（由生成模块输出）。
- `simulation_config`（市场数据、场景集、频率、交易成本等）。

**输出**
- `metrics`、`scenario_metrics`、`run_log`、`data_gaps`。

**边界**
- 不直接生成策略。
- 不修改 LLM 的输出。

### 1.3 反馈分析模块（指标 → 可优化信号）
**职责**
- 将仿真指标结构化为可优化信号。
- 识别风险超限、稳健性不足与关键缺口。

**输入**
- `metrics`、`scenario_metrics`、`run_log`、`data_gaps`。

**输出**
- `analysis_summary`、`optimization_signals`、`risk_alerts`、`info_requests`。

**边界**
- 不直接生成策略。
- 只对指标解释与诊断。

### 1.4 LLM 修正模块（基于反馈生成改进方案）
**职责**
- 吸收分析反馈与历史上下文，生成改进策略。

**输入**
- `analysis_summary`、`optimization_signals`、`risk_alerts`、`info_requests`。

**输出**
- `strategy`、`change_rationale`、`risk_expectation`、`stop_recommendation`。

**边界**
- 不执行仿真或数据补全。

### 1.5 自我终止模块（是否足够好/是否停止）
**职责**
- 基于终止规则判断是否停止迭代。
- 支持“信息不足”触发补充数据流程。

**输入**
- `metrics`、`analysis_summary`、`iteration_state`、`history_improvements`、`info_requests`。

**输出**
- `stop_decision`、`stop_reason`、`required_info`。

**边界**
- 不生成策略。
- 不修改终止规则配置。

---

## 2. LLM 交互协议（输入/输出字段）

### 2.1 输入字段（示例）
```json
{
  "iteration_id": "iter-0007",
  "assumptions": ["市场冲击可忽略", "交易成本为线性模型"],
  "constraints": {
    "max_leverage": 2.0,
    "max_positions": 20,
    "allowed_assets": ["AAPL", "MSFT", "SPY"]
  },
  "history_feedback": [
    {
      "iteration_id": "iter-0006",
      "summary": "收益提升有限，最大回撤超限",
      "key_metrics": {
        "annualized_return": 0.12,
        "max_drawdown": 0.22
      }
    }
  ],
  "strategy_params": {
    "signal_window": 20,
    "rebalance_freq": "weekly"
  },
  "risk_limits": {
    "max_drawdown": 0.15,
    "tail_risk": 0.05
  },
  "risk_budget": {
    "daily_var_limit": 0.02
  },
  "simulation_config": {
    "time_horizon": "2018-2024",
    "scenarios": ["baseline", "stress_downturn", "high_volatility"]
  }
}
```

### 2.2 输出字段（示例）
```json
{
  "strategy": {
    "name": "Momentum-Volatility-Adjusted-v2",
    "parameters": {
      "signal_window": 30,
      "volatility_cap": 0.12,
      "rebalance_freq": "weekly"
    },
    "rules": [
      "若波动率>阈值则降低仓位",
      "若信号强度低于阈值则保持现金"
    ]
  },
  "change_rationale": [
    "扩大信号窗口降低噪声",
    "引入波动率上限控制回撤"
  ],
  "risk_expectation": {
    "expected_max_drawdown": 0.14,
    "expected_sharpe": 1.1
  },
  "stop_recommendation": {
    "should_stop": false,
    "reason": "需验证回撤是否降至上限以下"
  }
}
```

---

## 3. 反馈结构化模板

### 3.1 指标字段（统一命名）
```json
{
  "returns_metrics": {
    "annualized_return": 0.15,
    "monthly_return_avg": 0.012,
    "sharpe_ratio": 1.2
  },
  "risk_metrics": {
    "max_drawdown": 0.13,
    "tail_risk_95": 0.06,
    "loss_distribution": {
      "p10": -0.03,
      "p50": -0.01,
      "p90": 0.02
    }
  },
  "robustness_metrics": {
    "scenario_consistency": 0.8,
    "scenario_results": {
      "baseline": {"sharpe_ratio": 1.2},
      "stress_downturn": {"sharpe_ratio": 0.6},
      "high_volatility": {"sharpe_ratio": 0.9}
    }
  }
}
```

### 3.2 反馈摘要模板
```json
{
  "analysis_summary": "收益改善但在压力情景下表现不稳",
  "optimization_signals": [
    "提升压力场景稳健性",
    "减少尾部风险"
  ],
  "risk_alerts": [
    "最大回撤接近上限"
  ],
  "info_requests": [
    "缺少交易成本敏感性测试结果"
  ]
}
```

---

## 4. 自我终止规则

### 4.1 指标阈值（硬性门槛）
- `annualized_return >= target_return`
- `max_drawdown <= max_drawdown_limit`
- `tail_risk_95 <= tail_risk_limit`

### 4.2 边际改进不足（连续 N 轮提升 < 阈值）
- 定义 `delta_metric = 当前指标 - 上一轮指标`。
- 若连续 `N` 轮满足 `delta_metric < improvement_threshold`，触发停止。
- 建议配置：
  - `N = 3`
  - `improvement_threshold = 0.01`（年化收益提升阈值）

### 4.3 信息不足检测
- 关键数据缺失（如交易成本敏感性、压力情景缺失）触发补充需求。
- 若 `info_requests` 非空，进入“补充信息”分支，暂停策略更新。

---

## 5. 迭代循环状态机

### 5.1 状态定义
- **Generate**：生成策略
- **Simulate**：执行仿真
- **Analyze**：反馈分析
- **Revise**：策略修正
- **StopCheck**：终止判定
- **Resample**：回退/重采样分支
- **Stop**：终止

### 5.2 状态转移
```
Generate → Simulate → Analyze → Revise → StopCheck
StopCheck → Stop (若满足终止条件)
StopCheck → Generate (若继续迭代)
Analyze → Resample (若信息不足或异常)
Resample → Simulate (重跑仿真)
```

### 5.3 允许回退/重采样分支
- 当 `data_gaps` 或 `info_requests` 触发时，进入 Resample。
- Resample 可替换数据源、扩展情景集、重新校准参数。

---

## 6. 系统规格文档

### 6.1 数据接口

**输入接口**
- `strategy_request`: 生成模块输入协议（参见 2.1）。
- `simulation_config`: 仿真配置（数据源、频率、成本模型、场景集）。

**输出接口**
- `simulation_result`: 仿真指标与日志（参见 3.1）。
- `analysis_report`: 反馈摘要（参见 3.2）。
- `termination_decision`: 终止判定输出。

### 6.2 指标定义
- **年化收益**：年化复合收益率。
- **月度收益**：月度平均收益。
- **夏普比率**：年化超额收益 / 年化波动率。
- **最大回撤**：峰值到谷值最大跌幅。
- **尾部风险**：95% 分位数损失或 CVaR。
- **稳健性一致性**：跨场景指标一致性评分（0-1）。

### 6.3 终止准则
1. 指标达标：收益与风险均满足阈值。
2. 边际提升不足：连续 N 轮改进不足。
3. 信息不足：关键数据缺失需补充。

### 6.4 容错与异常处理策略
- 仿真失败：记录 `run_log` 与错误码，进入 Resample。
- 指标异常（NaN/Inf）：触发数据校验与重跑。
- 输出格式错误：返回协议校验错误并请求修正。

### 6.5 版本化与可追溯性设计
- `iteration_id`：每轮唯一标识。
- `strategy_version`：策略版本号（语义化，如 `v1.2.0`）。
- `data_version`：数据源版本与哈希。
- `decision_log`：记录策略、指标、终止判定的完整流水。
