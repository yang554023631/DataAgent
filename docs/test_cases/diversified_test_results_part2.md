# 多样化自然语言Query测试结果 - Part 2 (ID 31-60)

测试时间: 2026-08-17 17:51:45

## 📊 汇总统计

| 指标 | 数值 | 占比 |
|------|------|------|
| 总测试用例 | 30 | 100% |
| 成功 | 17 | 57% |
| 需要澄清 | 0 | 0% |
| 失败 | 13 | 43% |
| 总耗时 | 1587.58s | - |

## 按预测分类

| 预测分类 | 总数量 | 成功数 | 成功率 |
|-----------|--------|--------|--------|
| 预期成功 | 13 | 8 | 62% |
| 可能失败 | 8 | 5 | 62% |
| 很可能失败 | 9 | 4 | 44% |

## 📋 详细结果

| ID | 状态 | 预测 | Query | 分析类型(预期/实际) | 数据点 | 错误 |
|----|------|------|-------|-------------------|--------|------|
| 31 | ✅ success | 预期成功 | 广告主6下面找出消耗最高的前五名广告计划 | entity_table/AnalysisType.ENTITY_TABLE | 5 |  |
| 32 | ✅ success | 预期成功 | 广告主6，把所有广告计划按点击从高到低排，只看前3 | entity_table/AnalysisType.ENTITY_TABLE | 3 |  |
| 33 | ✅ success | 可能失败 | 帮我找出广告主6，消耗最少的五个广告计划 | entity_table/AnalysisType.ENTITY_TABLE | 5 |  |
| 34 | ✅ success | 预期成功 | 给我看广告主6转化率前五的广告组 | entity_table/AnalysisType.ENTITY_TABLE | 5 |  |
| 35 | ✅ success | 可能失败 | 广告主6，投放中的广告计划中，消耗前五是哪些 | entity_table/AnalysisType.ENTITY_TABLE | 5 |  |
| 36 | ✅ success | 可能失败 | 广告主6，点击量大于50的创意，转化率最高的三个 | entity_table/AnalysisType.ENTITY_TABLE | 3 |  |
| 37 | ✅ success | 很可能失败 | 广告主6，投放中，消耗超过100，转化率前三的广告组 | entity_table/AnalysisType.ENTITY_TABLE | 3 |  |
| 38 | ❌ error | 预期成功 | 广告主6四月份一周七天每天平均消耗分布 | aggregation/AnalysisType.ENTITY_TABLE | 0 | 实体表格期望至少返回一条数据，但结果为空 |
| 39 | ❌ error | 预期成功 | 广告主6按星期几统计四月份平均每天消耗 | aggregation/AnalysisType.ENTITY_TABLE | 0 | 实体表格期望至少返回一条数据，但结果为空 |
| 40 | ❌ error | 可能失败 | 帮我分析广告主6每天哪个时段花钱最多，按小时统计四月份平均消耗 | aggregation/AnalysisType.ENTITY_TABLE | 0 | 实体表格期望至少返回一条数据，但结果为空 |
| 41 | ❌ error | 很可能失败 | 广告主6，工作日和周末消耗对比 | aggregation/unknown | 0 | 2次尝试全部失败，最后一次错误: 执行异常: argumen |
| 42 | ✅ success | 预期成功 | 广告主6三月份比四月份消耗多了还是少了 | period_comparison/AnalysisType.PERIOD_COMPARISON | 1 |  |
| 43 | ✅ success | 预期成功 | 广告主6四月份消耗相比上一个月变化了多少 | period_comparison/AnalysisType.PERIOD_COMPARISON | 1 |  |
| 44 | ✅ success | 预期成功 | 广告主6最近一周消耗和上一周相比增长了多少 | period_comparison/AnalysisType.PERIOD_COMPARISON | 0 |  |
| 45 | ✅ success | 很可能失败 | 对比广告主6下top3消耗计划，这个月和上个月的消耗变化 | period_comparison/AnalysisType.PERIOD_COMPARISON | 0 |  |
| 46 | ❌ error | 预期成功 | 广告主6四月份，分性别看消耗和转化率 | aggregation/unknown | 0 | 2次尝试全部失败，最后一次错误: 执行异常: argumen |
| 47 | ❌ error | 预期成功 | 广告主6各个年龄段分别花了多少钱 | aggregation/AnalysisType.AUDIENCE_DISTRIBUTION | 8 | 分析类型不匹配: 预期 aggregation, 实际 An |
| 48 | ❌ error | 预期成功 | 在广告主6中，苹果和安卓的点击率分别是多少 | aggregation/unknown | 0 | 2次尝试全部失败，最后一次错误: 执行异常: argumen |
| 49 | ❌ error | 可能失败 | 广告主6分性别分年龄看四月份消耗 | aggregation/unknown | 0 | 2次尝试全部失败，最后一次错误: 执行异常: argumen |
| 50 | ❌ error | 可能失败 | 广告主6按性别和系统版本分别统计转化率 | aggregation/unknown | 0 | 2次尝试全部失败，最后一次错误: 执行异常: argumen |
| 51 | ✅ success | 预期成功 | 广告主6转化率最高的三个广告计划 | entity_table/AnalysisType.ENTITY_TABLE | 3 |  |
| 52 | ✅ success | 预期成功 | 广告主6转化率最高的三个创意 | entity_table/AnalysisType.ENTITY_TABLE | 3 |  |
| 53 | ✅ success | 可能失败 | 广告主6点击率最低的两个广告组是什么 | entity_table/AnalysisType.ENTITY_TABLE | 2 |  |
| 54 | ✅ success | 可能失败 | 广告主6点击大于100的计划中点击率前五名 | entity_table/AnalysisType.ENTITY_TABLE | 5 |  |
| 55 | ❌ error | 很可能失败 | 广告主 digital_0 四月份按星期统计消耗 | aggregation/unknown | 0 | 2次尝试全部失败，最后一次错误: 执行异常: argumen |
| 56 | ✅ success | 很可能失败 | 广告主 digital_0 四月份数据概览 | summary/AnalysisType.SUMMARY | 4 |  |
| 57 | ❌ error | 很可能失败 | 广告主 digital_0四月消耗曲线 | time_trend/unknown | 0 | 2次尝试全部失败，最后一次错误: 需要用户澄清 |
| 58 | ❌ error | 很可能失败 | 给我看看广告主 digital_0最近数据 | summary/unknown | 0 | 2次尝试全部失败，最后一次错误: 需要用户澄清 |
| 59 | ✅ success | 很可能失败 | 广告主6找出消耗大于100且转化率大于0.02的创意 | entity_table/AnalysisType.ENTITY_TABLE | 33 |  |
| 60 | ❌ error | 很可能失败 | 广告主 digital_0下，找出四月份转化大于10并且转化率大于0.05的创意... | entity_table/unknown | 0 | 2次尝试全部失败，最后一次错误: 需要用户澄清 |

## ❌ 失败详情

### 38. 周期性趋势 措辞变化1

- **Query**: 广告主6四月份一周七天每天平均消耗分布
- **预测**: 预期成功
- **预期分析类型**: aggregation
- **实际分析类型**: AnalysisType.ENTITY_TABLE
- **预期目标层级**: advertiser
- **实际目标层级**: EntityLevel.ADVERTISER
- **错误信息**: 实体表格期望至少返回一条数据，但结果为空
- **尝试次数**: 1
- **响应时间**: 49.49s

### 39. 周期性趋势 措辞变化2

- **Query**: 广告主6按星期几统计四月份平均每天消耗
- **预测**: 预期成功
- **预期分析类型**: aggregation
- **实际分析类型**: AnalysisType.ENTITY_TABLE
- **预期目标层级**: advertiser
- **实际目标层级**: EntityLevel.ADVERTISER
- **错误信息**: 实体表格期望至少返回一条数据，但结果为空
- **尝试次数**: 1
- **响应时间**: 87.2s

### 40. 周期性趋势 措辞变化3

- **Query**: 帮我分析广告主6每天哪个时段花钱最多，按小时统计四月份平均消耗
- **预测**: 可能失败
- **预期分析类型**: aggregation
- **实际分析类型**: AnalysisType.ENTITY_TABLE
- **预期目标层级**: advertiser
- **实际目标层级**: EntityLevel.ADVERTISER
- **错误信息**: 实体表格期望至少返回一条数据，但结果为空
- **尝试次数**: 1
- **响应时间**: 41.32s

### 41. 周期性趋势 对比

- **Query**: 广告主6，工作日和周末消耗对比
- **预测**: 很可能失败
- **预期分析类型**: aggregation
- **实际分析类型**: unknown
- **预期目标层级**: advertiser
- **实际目标层级**: unknown
- **错误信息**: 2次尝试全部失败，最后一次错误: 执行异常: argument of type 'NoneType' is not iterable
- **尝试次数**: 2
- **响应时间**: 107.7s

### 46. 人群细分 表达1

- **Query**: 广告主6四月份，分性别看消耗和转化率
- **预测**: 预期成功
- **预期分析类型**: aggregation
- **实际分析类型**: unknown
- **预期目标层级**: advertiser
- **实际目标层级**: unknown
- **错误信息**: 2次尝试全部失败，最后一次错误: 执行异常: argument of type 'NoneType' is not iterable
- **尝试次数**: 2
- **响应时间**: 105.03s

### 47. 人群细分 表达2

- **Query**: 广告主6各个年龄段分别花了多少钱
- **预测**: 预期成功
- **预期分析类型**: aggregation
- **实际分析类型**: AnalysisType.AUDIENCE_DISTRIBUTION
- **预期目标层级**: advertiser
- **实际目标层级**: EntityLevel.ADVERTISER
- **错误信息**: 分析类型不匹配: 预期 aggregation, 实际 AnalysisType.AUDIENCE_DISTRIBUTION
- **尝试次数**: 1
- **响应时间**: 28.02s

### 48. 人群细分 表达3

- **Query**: 在广告主6中，苹果和安卓的点击率分别是多少
- **预测**: 预期成功
- **预期分析类型**: aggregation
- **实际分析类型**: unknown
- **预期目标层级**: advertiser
- **实际目标层级**: unknown
- **错误信息**: 2次尝试全部失败，最后一次错误: 执行异常: argument of type 'NoneType' is not iterable
- **尝试次数**: 2
- **响应时间**: 80.97s

### 49. 人群细分 多维度组合

- **Query**: 广告主6分性别分年龄看四月份消耗
- **预测**: 可能失败
- **预期分析类型**: aggregation
- **实际分析类型**: unknown
- **预期目标层级**: advertiser
- **实际目标层级**: unknown
- **错误信息**: 2次尝试全部失败，最后一次错误: 执行异常: argument of type 'NoneType' is not iterable
- **尝试次数**: 2
- **响应时间**: 111.5s

### 50. 人群细分 多维度组合2

- **Query**: 广告主6按性别和系统版本分别统计转化率
- **预测**: 可能失败
- **预期分析类型**: aggregation
- **实际分析类型**: unknown
- **预期目标层级**: advertiser
- **实际目标层级**: unknown
- **错误信息**: 2次尝试全部失败，最后一次错误: 执行异常: argument of type 'NoneType' is not iterable
- **尝试次数**: 2
- **响应时间**: 95.03s

### 55. 广告主名称 + 完整流程

- **Query**: 广告主 digital_0 四月份按星期统计消耗
- **预测**: 很可能失败
- **预期分析类型**: aggregation
- **实际分析类型**: unknown
- **预期目标层级**: advertiser
- **实际目标层级**: unknown
- **错误信息**: 2次尝试全部失败，最后一次错误: 执行异常: argument of type 'NoneType' is not iterable
- **尝试次数**: 2
- **响应时间**: 71.97s

### 57. 广告主名称 + 趋势简写

- **Query**: 广告主 digital_0四月消耗曲线
- **预测**: 很可能失败
- **预期分析类型**: time_trend
- **实际分析类型**: unknown
- **预期目标层级**: advertiser
- **实际目标层级**: unknown
- **错误信息**: 2次尝试全部失败，最后一次错误: 需要用户澄清
- **尝试次数**: 2
- **响应时间**: 27.84s

### 58. 广告主名称 + 近七天概览

- **Query**: 给我看看广告主 digital_0最近数据
- **预测**: 很可能失败
- **预期分析类型**: summary
- **实际分析类型**: unknown
- **预期目标层级**: advertiser
- **实际目标层级**: unknown
- **错误信息**: 2次尝试全部失败，最后一次错误: 需要用户澄清
- **尝试次数**: 2
- **响应时间**: 31.44s

### 60. 完整复杂流程 - 名称+层级+筛选+TopN

- **Query**: 广告主 digital_0下，找出四月份转化大于10并且转化率大于0.05的创意，按转化率排序，只看前5个
- **预测**: 很可能失败
- **预期分析类型**: entity_table
- **实际分析类型**: unknown
- **预期目标层级**: creative
- **实际目标层级**: unknown
- **错误信息**: 2次尝试全部失败，最后一次错误: 需要用户澄清
- **尝试次数**: 2
- **响应时间**: 41.11s

