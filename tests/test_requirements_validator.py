import unittest
from requirements.validator import validate_requirement_spec


VALID_SPEC_SAMPLE = """# 软件需求规格说明书（草案）

## 1. 需求标识与元数据
- **需求编号**：REQ-ORDER-PAY-20261107
- **需求名称**：扫码支付集成
- **提出人**：张三
- **分析师**：AutoDev (req-guided-v4)
- **归属项目**：/tmp/project
- **定稿时间**：2026-11-07 12:00:00

## 2. 架构拓扑与近期关联
- 📂 **功能层级归属**：属于 order 模块下的结算子功能。
- 🔗 **近期功能关联**：与近期做的 REQ-ORDER-CART 强关联，复用购物车结算实体。

## 3. 核心背景与业务目标 (Why & What)
- **业务背景**：用户在收银台结账需要快速完成付款。
- **业务目标**：3 秒内完成扫码唤起与支付确认。

## 4. 业务用例与核心流程 (Scope)
1. 顾客出示二维码；
2. 收银员扫描二维码；
3. 系统扣款成功。

## 5. 明确非目标与边界 (Non-goals)
- ❌ 本期不接入海外信用卡刷卡通道。
- ❌ 暂不支持先享后付分期业务。

## 6. 外部界面原型草图 (UI Wireframe)
```text
┌────────────────────────┐
│ 扫码收款台              │
├────────────────────────┤
│ 请扫描顾客付款码：     │
│ [ 📷 扫码中... ]        │
├────────────────────────┤
│ [ 确认收款 ] [ 取消 ]   │
└────────────────────────┘
```

## 7. 业务约束与前置依赖
- 必须接入支付网关。

## 8. 可量化验收标准清单 (Acceptance Criteria)
- 场景 1（正常扣款）：Given 余额充足 When 扫码 Then 成功扣款。
- 场景 2（余额不足）：Given 余额为零 When 扫码 Then 提示余额不足。

## 9. 下游架构设计关注点
- 幂等性控制与分布式事务补偿。
"""


class TestRequirementsValidator(unittest.TestCase):
    def test_valid_spec(self):
        res = validate_requirement_spec(VALID_SPEC_SAMPLE)
        self.assertTrue(res.is_valid, f"验证失败: {res.errors}")
        self.assertEqual(len(res.errors), 0)

    def test_missing_sections(self):
        # 缺少非目标和原型
        broken = VALID_SPEC_SAMPLE.replace("## 5. 明确非目标与边界 (Non-goals)", "## 5. 其他说明")
        res = validate_requirement_spec(broken)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("RULE-02" in err for err in res.errors))

    def test_missing_topology_dimensions(self):
        # 缺少近期功能关联
        broken = VALID_SPEC_SAMPLE.replace("🔗 **近期功能关联**", "相关描述")
        res = validate_requirement_spec(broken)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("RULE-03" in err for err in res.errors))

    def test_missing_wireframe(self):
        # 原型节没有 ```text
        broken = VALID_SPEC_SAMPLE.replace("```text", "```")
        res = validate_requirement_spec(broken)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("RULE-06" in err for err in res.errors))

    def test_forbidden_tech_overstepping(self):
        # 包含 SQL 语句
        broken = VALID_SPEC_SAMPLE + "\n数据库设计：CREATE TABLE orders (id int);"
        res = validate_requirement_spec(broken)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("RULE-08" in err for err in res.errors))


if __name__ == "__main__":
    unittest.main()
