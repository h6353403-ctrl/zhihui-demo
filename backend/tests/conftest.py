import sys
from pathlib import Path

# 让测试能直接 import backend 下的 app 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
