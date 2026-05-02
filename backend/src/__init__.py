import os
# 必须在导入任何使用 tokenizers 的模块之前设置
# 避免 forking 导致 LLM API 调用异常
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
