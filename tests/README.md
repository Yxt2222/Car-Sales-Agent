# 测试指南

## 快速开始

### 1. 运行单个测试文件

```bash
cd "d:\PythonProgramming\Aitherpath MLE\car_sales_project"
python tests/test_retriever.py
```

### 2. 使用 pytest 运行（推荐）

```bash
# 安装 pytest
pip install pytest

# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_retriever.py::test_retrieve_volvo -v
```

### 3. 直接 Python 命令运行测试

```bash
python -c "import sys; sys.path.insert(0, '.'); from tests.test_retriever import test_retrieve_volvo; test_retrieve_volvo()"
```

## 测试结构

### tests/test_retriever.py

| 测试分类 | 测试函数 | 测试内容 |
|---------|---------|---------|
| 预算解析 | `test_extract_budget_range()` | 15-20万 格式解析 |
| 预算解析 | `test_extract_budget_single()` | 50w 单一预算解析 |
| 预算解析 | `test_extract_budget_zuoyou()` | 40左右 预算解析 |
| 预算解析 | `test_extract_budget_invalid()` | 无效预算处理 |
| 标签提取 | `test_extract_tags_electric()` | 电动车标签提取 |
| 标签提取 | `test_extract_tags_suv()` | SUV 标签提取 |
| 检索 | `test_retrieve_by_brand()` | 按品牌检索 |
| 检索 | `test_retrieve_by_price()` | 按价格检索 |
| 检索 | `test_retrieve_combined()` | 品牌+价格组合检索 |
| 检索 | `test_retrieve_volvo()` | 沃尔沃品牌检索 |
| 格式化 | `test_format_for_llm()` | LLM 上下文格式化 |
| 完整流程 | `test_full_pipeline()` | 端到端检索流程 |

## 编写新测试

### 测试函数模板

```python
def test_your_test_case():
    """
    测试描述

    验证点:
    - 期望结果1
    - 期望结果2
    """
    # 1. 准备测试数据
    ctx = CallContext(
        state=CallState.RECOMMEND,
        brand="测试品牌",
        budget="测试预算"
    )

    # 2. 执行被测试功能
    result = retrieve_cars(ctx, top_k=2)

    # 3. 验证结果
    assert len(result) > 0, "结果不能为空"
    assert all("测试品牌" in c.brand for c in cars), "品牌应该匹配"

    # 4. 打印结果（可选）
    print(f"✓ 测试通过: 找到 {len(result)} 个结果")
```

### 常用断言

| 断言类型 | 示例 | 说明 |
|---------|-------|------|
| 非空断言 | `assert result is not None` | 结果不应为 None |
| 长度断言 | `assert len(cars) > 0` | 至少有1个结果 |
| 内容断言 | `assert "关键词" in text` | 包含预期内容 |
| 条件断言 | `assert all(c.brand == "品牌" for c in cars)` | 所有结果都满足条件 |
| 范围断言 | `assert 0 < x < 10` | 值在预期范围内 |

## 测试建议

### 1. 测试边界情况
```python
# 最小预算
ctx = CallContext(budget="10万左右")

# 最大预算
ctx = CallContext(budget="100万左右")

# 特殊格式
ctx = CallContext(budget="15~20")
ctx = CallContext(budget="50w")
```

### 2. 测试异常输入
```python
# 空输入
ctx = CallContext(brand="", budget="")

# 无效品牌
ctx = CallContext(brand="不存在的品牌", budget="20万")

# 无效预算格式
ctx = CallContext(budget="随便看看")
```

### 3. 测试数据一致性
```python
# 验证数据库中特定品牌的车数量
db = get_database()
audi_cars = db.search_by_brand("奥迪")
assert len(audi_cars) == 3  # 应该是3款奥迪

# 验证价格范围
for car in audi_cars:
    assert 0 < car.price_low < 100
    assert 0 < car.price_high < 100
```

## 常见问题

### Q1: ModuleNotFoundError: No module named 'rag'

**原因**: Python 找不到项目模块

**解决**:
```bash
# 方法1: 设置 PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"  # Linux/Mac
set PYTHONPATH=%CD%;  # Windows

# 方法2: 在项目目录下运行
cd "项目根目录"
python tests/test_retriever.py

# 方法3: 使用 -c 参数
python -c "import sys; sys.path.insert(0, '.'); from tests.test_retriever import *; ..."
```

### Q2: AssertionError

**原因**: 测试断言失败

**解决**: 检查测试数据和预期结果是否匹配，修改测试或代码

### Q3: 测试通过但实际运行有问题

**原因**: 测试场景覆盖不全

**解决**: 添加更多边界测试用例

## 持续集成

### 使用 pytest 配置文件

创建 `pytest.ini`:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

### 运行测试并生成报告

```bash
# 生成 HTML 报告
pytest tests/ --html=report.html

# 生成覆盖率报告
pytest tests/ --cov=rag --cov-report=html
```

## 运行示例

```bash
# 完整测试流程
python tests/test_retriever.py

# 只测试沃尔沃检索
python -c "import sys; sys.path.insert(0, '.'); from tests.test_retriever import test_retrieve_volvo; test_retrieve_volvo()"

# 只测试预算解析
python -c "import sys; sys.path.insert(0, '.'); from tests.test_retriever import test_extract_budget_range; test_extract_budget_range()"
```
