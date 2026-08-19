# 多样化自然语言Query测试结果

测试时间: 2026-08-16 22:25:12

## 📊 汇总统计

| 指标 | 数值 | 占比 |
|------|------|------|
| 总测试用例 | 60 | 100% |
| 成功 | 39 | 65% |
| 需要澄清 | 0 | 0% |
| 失败 | 21 | 35% |
| 总耗时 | 2837.84s | - |

## 按预测分类

| 预测分类 | 总数量 | 成功数 | 成功率 |
|-----------|--------|--------|--------|
| 预期成功 | 19 | 17 | 89% |
| 可能失败 | 24 | 20 | 83% |
| 很可能失败 | 17 | 2 | 12% |

## 📋 详细结果

| ID | 状态 | 预测 | Query | 分析类型(预期/实际) | 数据点 | 错误 |
|----|------|------|-------|-------------------|--------|------|
| 1 | ✅ success | 可能失败 | 帮我看一下名称是 digital_0 的广告主四月份消耗趋势 | time_trend/AnalysisType.TIME_TREND | 27 |  |
| 2 | ✅ success | 可能失败 | 查询 digital_0 最近七天的数据概览（截止到4月27日） | summary/AnalysisType.SUMMARY | 4 |  |
| 3 | ✅ success | 可能失败 | 给我 digital_0 三月份的曝光、点击、消耗汇总 | summary/AnalysisType.SUMMARY | 0 |  |
| 4 | ❌ error | 可能失败 | 在 digital_0 下找出叫 summer_mini 的广告计划四月份消耗 | entity_table/AnalysisType.ENTITY_TABLE | 0 | 实体表格期望至少返回一条数据，但结果为空 |
| 5 | ✅ success | 可能失败 | 广告主 digital_0 中，尊享_50 这个广告计划四月份消耗趋势 | time_trend/AnalysisType.TIME_TREND | 0 |  |
| 6 | ✅ success | 很可能失败 | digital_0 的 短视频_g73 最近七天消耗变化曲线 | time_trend/AnalysisType.TIME_TREND | 0 |  |
| 7 | ❌ error | 很可能失败 | 给我 digital_0 的 旗舰43_best 四月份总点击 | entity_table/AnalysisType.SUMMARY | 1 | 分析类型不匹配: 预期 entity_table, 实际 A |
| 8 | ❌ error | 很可能失败 | digital_0 下面名称包含 mini 的所有广告计划列出四月份消耗 | entity_table/AnalysisType.ENTITY_TABLE | 0 | 实体表格期望至少返回一条数据，但结果为空 |
| 9 | ❌ error | 很可能失败 | 找出 digital_0 名称带 digital 的广告计划，按消耗排序 | entity_table/AnalysisType.ENTITY_TABLE | 0 | 实体表格期望至少返回一条数据，但结果为空 |
| 10 | ❌ error | 很可能失败 | digital_0 下名称中包含下划线的广告计划四月份点击汇总 | entity_table/AnalysisType.ENTITY_TABLE | 0 | 实体表格期望至少返回一条数据，但结果为空 |
| 11 | ❌ error | 很可能失败 | digital_0 下 精选六一八0 这个广告组四月份消耗是多少 | entity_table/AnalysisType.SUMMARY | 0 | 分析类型不匹配: 预期 entity_table, 实际 A |
| 12 | ❌ error | 很可能失败 | 在 digital_0 中找出名称包含六一八的所有广告组，按消耗降序排列前三 | entity_table/AnalysisType.ENTITY_TABLE | 0 | 实体表格期望至少返回一条数据，但结果为空 |
| 13 | ❌ error | 很可能失败 | digital_0 的广告组 mini_045 四月份点击率是多少 | entity_table/AnalysisType.SUMMARY | 0 | 分析类型不匹配: 预期 entity_table, 实际 A |
| 14 | ❌ error | 很可能失败 | digital_0 下 冬季粉丝_3_zs14 这个创意四月份获得多少点击 | entity_table/AnalysisType.SUMMARY | 0 | 分析类型不匹配: 预期 entity_table, 实际 A |
| 15 | ❌ error | 很可能失败 | 列出 digital_0 名称含尊享的所有创意及消耗 | entity_table/AnalysisType.ENTITY_TABLE | 0 | 实体表格期望至少返回一条数据，但结果为空 |
| 16 | ❌ error | 很可能失败 | digital_0 的创意 专场美妆_513 四月份转化率是多少 | entity_table/AnalysisType.SUMMARY | 0 | 分析类型不匹配: 预期 entity_table, 实际 A |
| 17 | ✅ success | 很可能失败 | digital_0 中名称包含 summer 而且四月份消耗大于100的广告计划... | entity_table/AnalysisType.ENTITY_TABLE | 2 |  |
| 18 | ❌ error | 很可能失败 | digital_0 投放中的广告计划，名称含有 best，列出消耗和点击 | entity_table/AnalysisType.ENTITY_TABLE | 0 | 实体表格期望至少返回一条数据，但结果为空 |
| 19 | ❌ error | 很可能失败 | 找出 digital_0 下名称含 mini 的创意，点击量大于50的 | entity_table/AnalysisType.ENTITY_TABLE | 0 | 实体表格期望至少返回一条数据，但结果为空 |
| 20 | ✅ success | 可能失败 | 双十一_90 四月份消耗对比三月份 | period_comparison/AnalysisType.PERIOD_COMPARISON | 0 |  |
| 21 | ✅ success | 可能失败 | 母婴_3 四月份点击数据趋势图 | time_trend/AnalysisType.TIME_TREND | 0 |  |
| 22 | ✅ success | 可能失败 | 广告主 autumn_145_beauty 四月份各个广告计划消耗表格 | entity_table/AnalysisType.ENTITY_TABLE | 3 |  |
| 23 | ✅ success | 预期成功 | 六号广告主四月份每天花多少钱，给我看趋势 | time_trend/AnalysisType.TIME_TREND | 27 |  |
| 24 | ✅ success | 预期成功 | 帮我画一下广告主ID为6的四月消耗曲线 | time_trend/AnalysisType.TIME_TREND | 27 |  |
| 25 | ✅ success | 预期成功 | 四月份，广告主6的消耗是怎么变化的 | time_trend/AnalysisType.TIME_TREND | 27 |  |
| 26 | ✅ success | 预期成功 | 广告主ID等于6，四月份消耗趋势 | time_trend/AnalysisType.TIME_TREND | 27 |  |
| 27 | ✅ success | 预期成功 | 把广告主6下面每个广告计划四月份消耗趋势分开画出来 | time_trend/AnalysisType.TIME_TREND | 54 |  |
| 28 | ✅ success | 可能失败 | 广告主6，每个计划一条折线看四月份每日消耗 | time_trend/AnalysisType.TIME_TREND | 54 |  |
| 29 | ✅ success | 可能失败 | 分开展示广告主6各广告计划四月消耗走势 | time_trend/AnalysisType.TIME_TREND | 54 |  |
| 30 | ✅ success | 可能失败 | 广告主6各计划分开看四月份消耗变化 | time_trend/AnalysisType.TIME_TREND | 54 |  |
| 31 | ✅ success | 预期成功 | 列出广告主6没删掉的那些广告计划四月份消耗和点击 | entity_table/AnalysisType.ENTITY_TABLE | 2 |  |
| 32 | ✅ success | 可能失败 | 广告主6，筛选掉已删除的，展示四月份各计划消耗点击数据 | entity_table/AnalysisType.ENTITY_TABLE | 2 |  |
| 33 | ✅ success | 可能失败 | 找一下广告主6下面，状态是未删除的广告计划，四月份花了多少点了多少 | entity_table/AnalysisType.ENTITY_TABLE | 2 |  |
| 34 | ✅ success | 预期成功 | 广告主6四月份哪些计划总共花了超过10块钱 | entity_table/AnalysisType.ENTITY_TABLE | 2 |  |
| 35 | ✅ success | 可能失败 | 找出广告主6四月总消耗大于10的广告计划列出来 | entity_table/AnalysisType.ENTITY_TABLE | 2 | {'type': 'analysis_error', 'me |
| 36 | ✅ success | 可能失败 | 帮我筛选广告主6，四月消耗超过10的计划有哪些 | entity_table/AnalysisType.ENTITY_TABLE | 2 |  |
| 37 | ✅ success | 预期成功 | 用表格展示广告主6四月份的展示、点击、消耗、转化 | entity_table/AnalysisType.ENTITY_TABLE | 1 |  |
| 38 | ❌ error | 可能失败 | 广告主6四月份，把曝光点击花费转化这四个指标给我列出来 | entity_table/AnalysisType.SUMMARY | 4 | 分析类型不匹配: 预期 entity_table, 实际 A |
| 39 | ❌ error | 预期成功 | 给我广告主6四月各项核心指标数据，表格形式 | entity_table/AnalysisType.SUMMARY | 0 | 分析类型不匹配: 预期 entity_table, 实际 A |
| 40 | ✅ success | 预期成功 | 广告主6四月花费和三月比，涨了还是跌了 | period_comparison/AnalysisType.PERIOD_COMPARISON | 1 |  |
| 41 | ✅ success | 可能失败 | 对比广告主6三月份和四月份的总消耗，差异多大 | period_comparison/AnalysisType.PERIOD_COMPARISON | 1 |  |
| 42 | ✅ success | 可能失败 | 上个月跟这个月比，广告主6消耗哪个多 | period_comparison/AnalysisType.PERIOD_COMPARISON | 0 |  |
| 43 | ✅ success | 预期成功 | 广告主6四月份，不同性别用户消耗占比分别是多少 | audience_distribution/AnalysisType.AUDIENCE_DISTRIBUTION | 2 |  |
| 44 | ✅ success | 可能失败 | 按性别划分，广告主6四月消耗分布饼图 | audience_distribution/AnalysisType.AUDIENCE_DISTRIBUTION | 2 |  |
| 45 | ✅ success | 可能失败 | 广告主6四月份消耗在男女之间怎么分布 | audience_distribution/AnalysisType.AUDIENCE_DISTRIBUTION | 2 |  |
| 46 | ✅ success | 预期成功 | 广告主6四月份四个指标 | summary/AnalysisType.SUMMARY | 4 |  |
| 47 | ✅ success | 预期成功 | 给我广告主6四月总的展示点击消耗转化 | summary/AnalysisType.SUMMARY | 4 |  |
| 48 | ✅ success | 预期成功 | 广告主6四月数据概览 | summary/AnalysisType.SUMMARY | 4 |  |
| 49 | ❌ error | 预期成功 | 广告主6四月份消耗最高的前三名广告组 | entity_table/AnalysisType.ENTITY_TABLE | 0 | 实体表格期望至少返回一条数据，但结果为空 |
| 50 | ❌ error | 可能失败 | 列出广告主6点击率从高到低排前五的广告组 | entity_table/AnalysisType.ENTITY_TABLE | 0 | 实体表格期望至少返回一条数据，但结果为空 |
| 51 | ✅ success | 预期成功 | 广告主6四月份点击量超过100的创意有哪些 | entity_table/AnalysisType.ENTITY_TABLE | 4 |  |
| 52 | ❌ error | 可能失败 | 广告主6转化率最高的三个创意 | entity_table/AnalysisType.ENTITY_TABLE | 0 | 实体表格期望至少返回一条数据，但结果为空 |
| 53 | ✅ success | 预期成功 | 广告主6四月份消耗按年龄分组分布 | audience_distribution/AnalysisType.AUDIENCE_DISTRIBUTION | 8 |  |
| 54 | ✅ success | 预期成功 | 广告主6按不同操作系统看消耗占比 | audience_distribution/AnalysisType.AUDIENCE_DISTRIBUTION | 0 |  |
| 55 | ✅ success | 可能失败 | digital_0 四月份消耗按城市分布 | audience_distribution/AnalysisType.AUDIENCE_DISTRIBUTION | 20 |  |
| 56 | ❌ error | 很可能失败 | digital_0 | summary/AnalysisType.ENTITY_TABLE | 0 | 实体表格期望至少返回一条数据，但结果为空 |
| 57 | ❌ error | 很可能失败 | digital_0四月 | summary/unknown | 0 | 2次尝试全部失败，最后一次错误: 需要用户澄清 |
| 58 | ❌ error | 很可能失败 | 给我看看digital_0最近数据 | summary/unknown | 0 | 2次尝试全部失败，最后一次错误: 需要用户澄清 |
| 59 | ✅ success | 可能失败 | 六号广告主最近表现怎么样 | summary/AnalysisType.SUMMARY | 0 |  |
| 60 | ✅ success | 预期成功 | 帮我查一下广告主六四月份数据 | summary/AnalysisType.SUMMARY | 4 |  |

## ❌ 失败详情

### 4. 跨层级名称查询 - campaign

- **Query**: 在 digital_0 下找出叫 summer_mini 的广告计划四月份消耗
- **预测**: 可能失败
- **预期分析类型**: entity_table
- **实际分析类型**: AnalysisType.ENTITY_TABLE
- **预期目标层级**: campaign
- **实际目标层级**: EntityLevel.CAMPAIGN
- **错误信息**: 实体表格期望至少返回一条数据，但结果为空
- **尝试次数**: 1
- **响应时间**: 54.62s

### 7. 两层名称查询 - 总点击

- **Query**: 给我 digital_0 的 旗舰43_best 四月份总点击
- **预测**: 很可能失败
- **预期分析类型**: entity_table
- **实际分析类型**: AnalysisType.SUMMARY
- **预期目标层级**: campaign
- **实际目标层级**: EntityLevel.CAMPAIGN
- **错误信息**: 分析类型不匹配: 预期 entity_table, 实际 AnalysisType.SUMMARY
- **尝试次数**: 1
- **响应时间**: 56.44s

### 8. 模糊名称查询 - 包含mini

- **Query**: digital_0 下面名称包含 mini 的所有广告计划列出四月份消耗
- **预测**: 很可能失败
- **预期分析类型**: entity_table
- **实际分析类型**: AnalysisType.ENTITY_TABLE
- **预期目标层级**: campaign
- **实际目标层级**: EntityLevel.CAMPAIGN
- **错误信息**: 实体表格期望至少返回一条数据，但结果为空
- **尝试次数**: 1
- **响应时间**: 47.94s

### 9. 模糊名称查询 - 包含digital + 排序

- **Query**: 找出 digital_0 名称带 digital 的广告计划，按消耗排序
- **预测**: 很可能失败
- **预期分析类型**: entity_table
- **实际分析类型**: AnalysisType.ENTITY_TABLE
- **预期目标层级**: campaign
- **实际目标层级**: EntityLevel.CAMPAIGN
- **错误信息**: 实体表格期望至少返回一条数据，但结果为空
- **尝试次数**: 1
- **响应时间**: 38.6s

### 10. 模糊名称查询 - 包含下划线

- **Query**: digital_0 下名称中包含下划线的广告计划四月份点击汇总
- **预测**: 很可能失败
- **预期分析类型**: entity_table
- **实际分析类型**: AnalysisType.ENTITY_TABLE
- **预期目标层级**: campaign
- **实际目标层级**: EntityLevel.CAMPAIGN
- **错误信息**: 实体表格期望至少返回一条数据，但结果为空
- **尝试次数**: 1
- **响应时间**: 41.54s

### 11. 两层名称查询 - ad_group

- **Query**: digital_0 下 精选六一八0 这个广告组四月份消耗是多少
- **预测**: 很可能失败
- **预期分析类型**: entity_table
- **实际分析类型**: AnalysisType.SUMMARY
- **预期目标层级**: ad_group
- **实际目标层级**: EntityLevel.AD_GROUP
- **错误信息**: 分析类型不匹配: 预期 entity_table, 实际 AnalysisType.SUMMARY
- **尝试次数**: 1
- **响应时间**: 48.83s

### 12. 模糊查询 + 排序 + TopN - ad_group

- **Query**: 在 digital_0 中找出名称包含六一八的所有广告组，按消耗降序排列前三
- **预测**: 很可能失败
- **预期分析类型**: entity_table
- **实际分析类型**: AnalysisType.ENTITY_TABLE
- **预期目标层级**: ad_group
- **实际目标层级**: EntityLevel.AD_GROUP
- **错误信息**: 实体表格期望至少返回一条数据，但结果为空
- **尝试次数**: 1
- **响应时间**: 38.98s

### 13. 两层名称查询 - ad_group点击率

- **Query**: digital_0 的广告组 mini_045 四月份点击率是多少
- **预测**: 很可能失败
- **预期分析类型**: entity_table
- **实际分析类型**: AnalysisType.SUMMARY
- **预期目标层级**: ad_group
- **实际目标层级**: EntityLevel.AD_GROUP
- **错误信息**: 分析类型不匹配: 预期 entity_table, 实际 AnalysisType.SUMMARY
- **尝试次数**: 1
- **响应时间**: 61.24s

### 14. 三层名称查询 - creative

- **Query**: digital_0 下 冬季粉丝_3_zs14 这个创意四月份获得多少点击
- **预测**: 很可能失败
- **预期分析类型**: entity_table
- **实际分析类型**: AnalysisType.SUMMARY
- **预期目标层级**: creative
- **实际目标层级**: EntityLevel.CREATIVE
- **错误信息**: 分析类型不匹配: 预期 entity_table, 实际 AnalysisType.SUMMARY
- **尝试次数**: 1
- **响应时间**: 57.45s

### 15. 模糊名称查询 - creative

- **Query**: 列出 digital_0 名称含尊享的所有创意及消耗
- **预测**: 很可能失败
- **预期分析类型**: entity_table
- **实际分析类型**: AnalysisType.ENTITY_TABLE
- **预期目标层级**: creative
- **实际目标层级**: EntityLevel.CREATIVE
- **错误信息**: 实体表格期望至少返回一条数据，但结果为空
- **尝试次数**: 1
- **响应时间**: 38.14s

### 16. 三层名称查询 - creative转化率

- **Query**: digital_0 的创意 专场美妆_513 四月份转化率是多少
- **预测**: 很可能失败
- **预期分析类型**: entity_table
- **实际分析类型**: AnalysisType.SUMMARY
- **预期目标层级**: creative
- **实际目标层级**: EntityLevel.CREATIVE
- **错误信息**: 分析类型不匹配: 预期 entity_table, 实际 AnalysisType.SUMMARY
- **尝试次数**: 1
- **响应时间**: 43.47s

### 18. 混合筛选 - status + 名称contains

- **Query**: digital_0 投放中的广告计划，名称含有 best，列出消耗和点击
- **预测**: 很可能失败
- **预期分析类型**: entity_table
- **实际分析类型**: AnalysisType.ENTITY_TABLE
- **预期目标层级**: campaign
- **实际目标层级**: EntityLevel.CAMPAIGN
- **错误信息**: 实体表格期望至少返回一条数据，但结果为空
- **尝试次数**: 1
- **响应时间**: 57.15s

### 19. 混合筛选 - 名称 + having点击

- **Query**: 找出 digital_0 下名称含 mini 的创意，点击量大于50的
- **预测**: 很可能失败
- **预期分析类型**: entity_table
- **实际分析类型**: AnalysisType.ENTITY_TABLE
- **预期目标层级**: creative
- **实际目标层级**: EntityLevel.CREATIVE
- **错误信息**: 实体表格期望至少返回一条数据，但结果为空
- **尝试次数**: 1
- **响应时间**: 48.74s

### 38. ID多指标表格多样化 - 同义词替换

- **Query**: 广告主6四月份，把曝光点击花费转化这四个指标给我列出来
- **预测**: 可能失败
- **预期分析类型**: entity_table
- **实际分析类型**: AnalysisType.SUMMARY
- **预期目标层级**: advertiser
- **实际目标层级**: EntityLevel.ADVERTISER
- **错误信息**: 分析类型不匹配: 预期 entity_table, 实际 AnalysisType.SUMMARY
- **尝试次数**: 1
- **响应时间**: 53.57s

### 39. ID多指标表格多样化 - 表格形式

- **Query**: 给我广告主6四月各项核心指标数据，表格形式
- **预测**: 预期成功
- **预期分析类型**: entity_table
- **实际分析类型**: AnalysisType.SUMMARY
- **预期目标层级**: advertiser
- **实际目标层级**: EntityLevel.ADVERTISER
- **错误信息**: 分析类型不匹配: 预期 entity_table, 实际 AnalysisType.SUMMARY
- **尝试次数**: 1
- **响应时间**: 56.26s

### 49. Ad Group TopN - 消耗前三

- **Query**: 广告主6四月份消耗最高的前三名广告组
- **预测**: 预期成功
- **预期分析类型**: entity_table
- **实际分析类型**: AnalysisType.ENTITY_TABLE
- **预期目标层级**: ad_group
- **实际目标层级**: EntityLevel.AD_GROUP
- **错误信息**: 实体表格期望至少返回一条数据，但结果为空
- **尝试次数**: 1
- **响应时间**: 23.85s

### 50. Ad Group TopN - 点击率前五

- **Query**: 列出广告主6点击率从高到低排前五的广告组
- **预测**: 可能失败
- **预期分析类型**: entity_table
- **实际分析类型**: AnalysisType.ENTITY_TABLE
- **预期目标层级**: ad_group
- **实际目标层级**: EntityLevel.AD_GROUP
- **错误信息**: 实体表格期望至少返回一条数据，但结果为空
- **尝试次数**: 1
- **响应时间**: 43.78s

### 52. Creative TopN - 转化率前三

- **Query**: 广告主6转化率最高的三个创意
- **预测**: 可能失败
- **预期分析类型**: entity_table
- **实际分析类型**: AnalysisType.ENTITY_TABLE
- **预期目标层级**: creative
- **实际目标层级**: EntityLevel.CREATIVE
- **错误信息**: 实体表格期望至少返回一条数据，但结果为空
- **尝试次数**: 1
- **响应时间**: 46.59s

### 56. 极度简洁 - 只有名称

- **Query**: digital_0
- **预测**: 很可能失败
- **预期分析类型**: summary
- **实际分析类型**: AnalysisType.ENTITY_TABLE
- **预期目标层级**: advertiser
- **实际目标层级**: EntityLevel.CAMPAIGN
- **错误信息**: 实体表格期望至少返回一条数据，但结果为空
- **尝试次数**: 1
- **响应时间**: 95.55s

### 57. 简洁 - 名称+月份

- **Query**: digital_0四月
- **预测**: 很可能失败
- **预期分析类型**: summary
- **实际分析类型**: unknown
- **预期目标层级**: advertiser
- **实际目标层级**: unknown
- **错误信息**: 2次尝试全部失败，最后一次错误: 需要用户澄清
- **尝试次数**: 2
- **响应时间**: 18.95s

### 58. 全模糊 - 最近数据

- **Query**: 给我看看digital_0最近数据
- **预测**: 很可能失败
- **预期分析类型**: summary
- **实际分析类型**: unknown
- **预期目标层级**: advertiser
- **实际目标层级**: unknown
- **错误信息**: 2次尝试全部失败，最后一次错误: 需要用户澄清
- **尝试次数**: 2
- **响应时间**: 32.16s

