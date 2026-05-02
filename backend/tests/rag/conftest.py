import pytest
import os

# 在所有测试运行前设置环境变量
os.environ['OPENAI_API_KEY'] = 'test-key'
