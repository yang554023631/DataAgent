# 多样化自然语言Query测试结果 - Part 1 (ID 1-30)

测试时间: 2026-08-17 17:13:41

## 📊 汇总统计

| 指标 | 数值 | 占比 |
|------|------|------|
| 总测试用例 | 30 | 100% |
| 成功 | 23 | 77% |
| 需要澄清 | 0 | 0% |
| 失败 | 7 | 23% |
| 总耗时 | 1272.92s | - |

## 按预测分类

| 预测分类 | 总数量 | 成功数 | 成功率 |
|-----------|--------|--------|--------|
| 预期成功 | 5 | 5 | 100% |
| 可能失败 | 11 | 9 | 82% |
| 很可能失败 | 14 | 9 | 64% |

## 📋 详细结果

| ID | 状态 | 预测 | Query | 分析类型(预期/实际) | 数据点 | 错误 |
|----|------|------|-------|-------------------|--------|------|
| 1 | ✅ success | 可能失败 | 帮我看一下名称是 digital_0 的广告主四月份消耗趋势 | time_trend/AnalysisType.TIME_TREND | 27 |  |
| 2 | ✅ success | 可能失败 | 查询广告主 digital_0 最近七天的数据概览（截止到4月27日） | summary/AnalysisType.SUMMARY | 4 |  |
| 3 | ✅ success | 可能失败 | 给我广告主 digital_0 三月份的曝光、点击、消耗汇总 | summary/AnalysisType.SUMMARY | 3 |  |
| 4 | ✅ success | 可能失败 | 在广告主 digital_0 下找出叫 summer_mini 的广告计划四月份... | entity_table/AnalysisType.ENTITY_TABLE | 2 |  |
| 5 | ✅ success | 可能失败 | 广告主 digital_0 中，尊享_50 这个广告计划四月份消耗趋势 | time_trend/AnalysisType.TIME_TREND | 27 |  |
| 6 | ✅ success | 很可能失败 | 广告主 digital_0 的 短视频_g73 最近七天消耗变化曲线 | time_trend/AnalysisType.TIME_TREND | 0 |  |
| 7 | ❌ error | 很可能失败 | 给我广告主 digital_0 的 旗舰43_best 四月份总点击 | entity_table/AnalysisType.SUMMARY | 0 | 分析类型不匹配: 预期 entity_table, 实际 A |
| 8 | ✅ success | 很可能失败 | 广告主 digital_0 下面名称包含 mini 的所有广告计划列出四月份消耗 | entity_table/AnalysisType.ENTITY_TABLE | 2 |  |
| 9 | ✅ success | 很可能失败 | 找出广告主 digital_0 名称带 digital 的广告计划，按消耗排序 | entity_table/AnalysisType.ENTITY_TABLE | 7 |  |
| 10 | ✅ success | 很可能失败 | 广告主 digital_0 下名称中包含下划线的广告计划四月份点击汇总 | entity_table/AnalysisType.ENTITY_TABLE | 2 |  |
| 11 | ❌ error | 很可能失败 | 广告主 digital_0 下 精选六一八0 这个广告组四月份消耗是多少 | entity_table/AnalysisType.SUMMARY | 1 | 分析类型不匹配: 预期 entity_table, 实际 A |
| 12 | ✅ success | 很可能失败 | 在广告主 digital_0 中找出名称包含六一八的所有广告组，按消耗降序排列前... | entity_table/AnalysisType.ENTITY_TABLE | 3 |  |
| 13 | ❌ error | 很可能失败 | 广告主 digital_0 的广告组 mini_045 四月份点击率是多少 | entity_table/unknown | 0 | 2次尝试全部失败，最后一次错误: 执行异常: argumen |
| 14 | ❌ error | 很可能失败 | 广告主 digital_0 下 冬季粉丝_3_zs14 这个创意四月份获得多少点... | entity_table/AnalysisType.SUMMARY | 1 | 分析类型不匹配: 预期 entity_table, 实际 A |
| 15 | ✅ success | 很可能失败 | 列出广告主 digital_0 名称含尊享的所有创意及消耗 | entity_table/AnalysisType.ENTITY_TABLE | 33 |  |
| 16 | ❌ error | 很可能失败 | 广告主 digital_0 的创意 专场美妆_513 四月份转化率是多少 | entity_table/unknown | 0 | 2次尝试全部失败，最后一次错误: 执行异常: argumen |
| 17 | ✅ success | 很可能失败 | 广告主 digital_0 中名称包含 summer 而且四月份消耗大于100的... | entity_table/AnalysisType.ENTITY_TABLE | 2 |  |
| 18 | ✅ success | 很可能失败 | 广告主 digital_0 投放中的广告计划，名称含有 best，列出消耗和点击 | entity_table/AnalysisType.ENTITY_TABLE | 7 |  |
| 19 | ✅ success | 很可能失败 | 找出广告主 digital_0 下名称含 mini 的创意，点击量大于50 | entity_table/AnalysisType.ENTITY_TABLE | 1 |  |
| 20 | ❌ error | 可能失败 | 广告主双十一_90 四月份消耗对比三月份 | period_comparison/unknown | 0 | 2次尝试全部失败，最后一次错误: 需要用户澄清 |
| 21 | ❌ error | 可能失败 | 广告主母婴_3 四月份点击数据趋势图 | time_trend/unknown | 0 | 2次尝试全部失败，最后一次错误: 需要用户澄清 |
| 22 | ✅ success | 可能失败 | 广告主 autumn_145_beauty 四月份各个广告计划消耗表格 | entity_table/AnalysisType.ENTITY_TABLE | 3 |  |
| 23 | ✅ success | 预期成功 | 六号广告主四月份每天花多少钱，给我看趋势 | time_trend/AnalysisType.TIME_TREND | 27 |  |
| 24 | ✅ success | 预期成功 | 帮我画一下广告主ID为6的四月消耗曲线 | time_trend/AnalysisType.TIME_TREND | 27 |  |
| 25 | ✅ success | 预期成功 | 四月份，广告主6的消耗是怎么变化的 | time_trend/AnalysisType.TIME_TREND | 27 |  |
| 26 | ✅ success | 预期成功 | 广告主ID等于6，四月份消耗趋势 | time_trend/AnalysisType.TIME_TREND | 27 |  |
| 27 | ✅ success | 预期成功 | 把广告主6下面每个广告计划四月份消耗趋势分开画出来 | time_trend/AnalysisType.TIME_TREND | 54 |  |
| 28 | ✅ success | 可能失败 | 广告主6，每个计划一条折线看四月份每日消耗 | time_trend/AnalysisType.TIME_TREND | 54 |  |
| 29 | ✅ success | 可能失败 | 分开展示广告主6各广告计划四月消耗走势 | time_trend/AnalysisType.TIME_TREND | 54 |  |
| 30 | ✅ success | 可能失败 | 广告主6各计划分开看四月份消耗变化 | time_trend/AnalysisType.TIME_TREND | 54 |  |

## ❌ 失败详情

### 7. 两层名称查询 - 总点击

- **Query**: 给我广告主 digital_0 的 旗舰43_best 四月份总点击
- **预测**: 很可能失败
- **预期分析类型**: entity_table
- **实际分析类型**: AnalysisType.SUMMARY
- **预期目标层级**: campaign
- **实际目标层级**: EntityLevel.CAMPAIGN
- **错误信息**: 分析类型不匹配: 预期 entity_table, 实际 AnalysisType.SUMMARY
- **尝试次数**: 1
- **响应时间**: 69.92s

### 11. 两层名称查询 - ad_group

- **Query**: 广告主 digital_0 下 精选六一八0 这个广告组四月份消耗是多少
- **预测**: 很可能失败
- **预期分析类型**: entity_table
- **实际分析类型**: AnalysisType.SUMMARY
- **预期目标层级**: ad_group
- **实际目标层级**: EntityLevel.AD_GROUP
- **错误信息**: 分析类型不匹配: 预期 entity_table, 实际 AnalysisType.SUMMARY
- **尝试次数**: 1
- **响应时间**: 32.09s

### 13. 两层名称查询 - ad_group点击率

- **Query**: 广告主 digital_0 的广告组 mini_045 四月份点击率是多少
- **预测**: 很可能失败
- **预期分析类型**: entity_table
- **实际分析类型**: unknown
- **预期目标层级**: ad_group
- **实际目标层级**: unknown
- **错误信息**: 2次尝试全部失败，最后一次错误: 执行异常: argument of type 'NoneType' is not iterable
- **尝试次数**: 2
- **响应时间**: 78.65s

### 14. 三层名称查询 - creative

- **Query**: 广告主 digital_0 下 冬季粉丝_3_zs14 这个创意四月份获得多少点击
- **预测**: 很可能失败
- **预期分析类型**: entity_table
- **实际分析类型**: AnalysisType.SUMMARY
- **预期目标层级**: creative
- **实际目标层级**: EntityLevel.CREATIVE
- **错误信息**: 分析类型不匹配: 预期 entity_table, 实际 AnalysisType.SUMMARY
- **尝试次数**: 1
- **响应时间**: 48.37s

### 16. 三层名称查询 - creative转化率

- **Query**: 广告主 digital_0 的创意 专场美妆_513 四月份转化率是多少
- **预测**: 很可能失败
- **预期分析类型**: entity_table
- **实际分析类型**: unknown
- **预期目标层级**: creative
- **实际目标层级**: unknown
- **错误信息**: 2次尝试全部失败，最后一次错误: 执行异常: argument of type 'NoneType' is not iterable
- **尝试次数**: 2
- **响应时间**: 102.84s

### 20. 其他广告主名称对比

- **Query**: 广告主双十一_90 四月份消耗对比三月份
- **预测**: 可能失败
- **预期分析类型**: period_comparison
- **实际分析类型**: unknown
- **预期目标层级**: advertiser
- **实际目标层级**: unknown
- **错误信息**: 2次尝试全部失败，最后一次错误: 需要用户澄清
- **尝试次数**: 2
- **响应时间**: 29.31s

### 21. 其他广告主名称趋势

- **Query**: 广告主母婴_3 四月份点击数据趋势图
- **预测**: 可能失败
- **预期分析类型**: time_trend
- **实际分析类型**: unknown
- **预期目标层级**: advertiser
- **实际目标层级**: unknown
- **错误信息**: 2次尝试全部失败，最后一次错误: 需要用户澄清
- **尝试次数**: 2
- **响应时间**: 31.94s

