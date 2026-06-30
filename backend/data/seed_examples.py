"""Seed few-shot examples into the ChromaDB vector store.

Run once to populate the example store with curated question-SQL pairs.
The Agent will retrieve similar examples at query time to improve SQL accuracy.

Usage:
    python -X utf8 data/seed_examples.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agent.few_shot import few_shot_store

# ── Curated Examples ──
# Each pair represents a common analytics question and its correct SQL.
# These serve as "teaching examples" for the Agent via few-shot prompting.

SEED_EXAMPLES = [
    # ── 销售排名类 ──
    {
        "question": "销量最高的5个产品是哪些",
        "sql": """SELECT p.name AS 商品名称, SUM(oi.quantity) AS 总销量
FROM products p
JOIN order_items oi ON p.id = oi.product_id
GROUP BY p.id, p.name
ORDER BY 总销量 DESC
LIMIT 5""",
        "description": "商品销量排名：JOIN products + order_items，SUM(quantity)",
    },
    {
        "question": "各商品类目的销售总额排名",
        "sql": """SELECT c.name AS 类目名称, ROUND(SUM(oi.subtotal), 2) AS 销售总额
FROM categories c
JOIN products p ON c.id = p.category_id
JOIN order_items oi ON p.id = oi.product_id
JOIN orders o ON oi.order_id = o.id
WHERE o.status != 'cancelled'
GROUP BY c.id, c.name
ORDER BY 销售总额 DESC""",
        "description": "类目销售额排名：四表JOIN，排除取消订单，SUM(subtotal)",
    },
    {
        "question": "本月销售额是多少",
        "sql": """SELECT ROUND(SUM(total_amount), 2) AS 本月销售额
FROM orders
WHERE status != 'cancelled'
  AND YEAR(created_at) = YEAR(CURDATE())
  AND MONTH(created_at) = MONTH(CURDATE())""",
        "description": "月度销售额：WHERE时间筛选 + SUM",
    },

    # ── 趋势分析类 ──
    {
        "question": "最近3个月每月的订单金额趋势",
        "sql": """SELECT DATE_FORMAT(created_at, '%Y-%m') AS 月份,
       COUNT(*) AS 订单数,
       ROUND(SUM(total_amount), 2) AS 订单总金额
FROM orders
WHERE status != 'cancelled'
  AND created_at >= DATE_SUB(CURDATE(), INTERVAL 3 MONTH)
GROUP BY DATE_FORMAT(created_at, '%Y-%m')
ORDER BY 月份""",
        "description": "月度趋势：DATE_FORMAT分组 + 时间范围筛选",
    },
    {
        "question": "每天的订单量变化趋势",
        "sql": """SELECT DATE(created_at) AS 日期,
       COUNT(*) AS 订单数,
       ROUND(SUM(total_amount), 2) AS 日销售额
FROM orders
WHERE status != 'cancelled'
  AND created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
GROUP BY DATE(created_at)
ORDER BY 日期""",
        "description": "日趋势：DATE()函数 + 近30天筛选",
    },

    # ── 分布/占比类 ──
    {
        "question": "各支付方式的订单数量分布",
        "sql": """SELECT payment_method AS 支付方式,
       COUNT(*) AS 订单数量,
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM orders WHERE status != 'cancelled'), 1) AS 占比百分比
FROM orders
WHERE status != 'cancelled'
GROUP BY payment_method
ORDER BY 订单数量 DESC""",
        "description": "支付方式分布：GROUP BY + 百分比计算（子查询）",
    },
    {
        "question": "各城市的客户数量排名前10",
        "sql": """SELECT city AS 城市, COUNT(*) AS 客户数量
FROM customers
GROUP BY city
ORDER BY 客户数量 DESC
LIMIT 10""",
        "description": "城市客户排名：简单GROUP BY + ORDER BY + LIMIT",
    },
    {
        "question": "订单状态分布情况",
        "sql": """SELECT status AS 订单状态,
       COUNT(*) AS 数量,
       ROUND(AVG(total_amount), 2) AS 平均金额
FROM orders
GROUP BY status
ORDER BY 数量 DESC""",
        "description": "订单状态分布：GROUP BY + AVG",
    },

    # ── 会员/客户分析类 ──
    {
        "question": "不同会员等级的客户平均消费是多少",
        "sql": """SELECT c.member_level AS 会员等级,
       COUNT(DISTINCT c.id) AS 客户数,
       ROUND(AVG(o.total_amount), 2) AS 平均订单金额,
       ROUND(SUM(o.total_amount), 2) AS 总消费金额
FROM customers c
JOIN orders o ON c.id = o.customer_id
WHERE o.status != 'cancelled'
GROUP BY c.member_level
ORDER BY 平均订单金额 DESC""",
        "description": "会员等级消费分析：JOIN customers+orders + COUNT DISTINCT",
    },
    {
        "question": "消费金额最高的10个客户",
        "sql": """SELECT c.username AS 客户名, c.member_level AS 会员等级,
       COUNT(o.id) AS 订单数,
       ROUND(SUM(o.total_amount), 2) AS 总消费
FROM customers c
JOIN orders o ON c.id = o.customer_id
WHERE o.status != 'cancelled'
GROUP BY c.id, c.username, c.member_level
ORDER BY 总消费 DESC
LIMIT 10""",
        "description": "TOP客户：JOIN + SUM + 排序取前N",
    },
    {
        "question": "各省份的客户分布情况",
        "sql": """SELECT province AS 省份,
       COUNT(*) AS 客户数量,
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM customers), 1) AS 占比
FROM customers
GROUP BY province
ORDER BY 客户数量 DESC""",
        "description": "省份分布：GROUP BY province + 百分比",
    },

    # ── 商品评价类 ──
    {
        "question": "评分最高的商品有哪些",
        "sql": """SELECT p.name AS 商品名称, c.name AS 类目,
       ROUND(AVG(r.rating), 2) AS 平均评分,
       COUNT(r.id) AS 评价数量
FROM products p
JOIN categories c ON p.category_id = c.id
JOIN reviews r ON p.id = r.product_id
GROUP BY p.id, p.name, c.name
HAVING COUNT(r.id) >= 3
ORDER BY 平均评分 DESC
LIMIT 10""",
        "description": "商品评分排名：JOIN三表 + HAVING过滤低评价数",
    },
    {
        "question": "各评分区间的商品数量",
        "sql": """SELECT CASE
         WHEN avg_rating >= 4.5 THEN '优秀(4.5-5)'
         WHEN avg_rating >= 3.5 THEN '良好(3.5-4.5)'
         WHEN avg_rating >= 2.5 THEN '一般(2.5-3.5)'
         ELSE '较差(<2.5)'
       END AS 评分区间,
       COUNT(*) AS 商品数量
FROM (
    SELECT p.id, AVG(r.rating) AS avg_rating
    FROM products p
    JOIN reviews r ON p.id = r.product_id
    GROUP BY p.id
    HAVING COUNT(r.id) >= 2
) AS rated_products
GROUP BY 评分区间
ORDER BY 评分区间""",
        "description": "评分区间分布：子查询+CASE WHEN分段",
    },

    # ── 库存/商品状态类 ──
    {
        "question": "库存低于10的商品有哪些",
        "sql": """SELECT p.name AS 商品名称, p.price AS 价格,
       p.stock AS 库存, c.name AS 类目
FROM products p
JOIN categories c ON p.category_id = c.id
WHERE p.stock < 10 AND p.status = 'active'
ORDER BY p.stock ASC""",
        "description": "低库存预警：WHERE stock < N + JOIN类目",
    },
    {
        "question": "各类目的商品数量和平均价格",
        "sql": """SELECT c.name AS 类目名称,
       COUNT(p.id) AS 商品数量,
       ROUND(AVG(p.price), 2) AS 平均价格,
       ROUND(MIN(p.price), 2) AS 最低价,
       ROUND(MAX(p.price), 2) AS 最高价
FROM categories c
LEFT JOIN products p ON c.id = p.category_id AND p.status = 'active'
GROUP BY c.id, c.name
ORDER BY 商品数量 DESC""",
        "description": "类目商品统计：LEFT JOIN + 多聚合函数(MIN/MAX/AVG)",
    },

    # ── 综合/复合查询类 ──
    {
        "question": "复购率是多少（下过多单的客户比例）",
        "sql": """SELECT
    COUNT(DISTINCT CASE WHEN order_count > 1 THEN customer_id END) AS 复购客户数,
    COUNT(DISTINCT customer_id) AS 总客户数,
    ROUND(
        COUNT(DISTINCT CASE WHEN order_count > 1 THEN customer_id END) * 100.0
        / COUNT(DISTINCT customer_id), 1
    ) AS 复购率百分比
FROM (
    SELECT customer_id, COUNT(*) AS order_count
    FROM orders WHERE status != 'cancelled'
    GROUP BY customer_id
) AS customer_orders""",
        "description": "复购率：子查询统计订单数 + CASE WHEN条件计数",
    },
    {
        "question": "客单价（平均每单金额）是多少",
        "sql": """SELECT
    ROUND(AVG(total_amount), 2) AS 平均客单价,
    ROUND(MIN(total_amount), 2) AS 最低订单,
    ROUND(MAX(total_amount), 2) AS 最高订单,
    COUNT(*) AS 总订单数
FROM orders
WHERE status != 'cancelled'""",
        "description": "客单价：简单聚合 AVG/MIN/MAX/COUNT",
    },
    {
        "question": "哪些商品经常一起购买",
        "sql": """SELECT p1.name AS 商品A, p2.name AS 商品B,
       COUNT(*) AS 共同购买次数
FROM order_items oi1
JOIN order_items oi2 ON oi1.order_id = oi2.order_id AND oi1.product_id < oi2.product_id
JOIN products p1 ON oi1.product_id = p1.id
JOIN products p2 ON oi2.product_id = p2.id
GROUP BY p1.id, p1.name, p2.id, p2.name
HAVING COUNT(*) >= 2
ORDER BY 共同购买次数 DESC
LIMIT 10""",
        "description": "购物篮分析：自JOIN order_items + 去重(product_id < product_id)",
    },
    {
        "question": "新客户（本月注册的）有多少",
        "sql": """SELECT COUNT(*) AS 新客户数
FROM customers
WHERE YEAR(created_at) = YEAR(CURDATE())
  AND MONTH(created_at) = MONTH(CURDATE())""",
        "description": "新注册客户：WHERE时间筛选本月",
    },
    {
        "question": "各类目在每种支付方式下的销售额",
        "sql": """SELECT c.name AS 类目, o.payment_method AS 支付方式,
       ROUND(SUM(oi.subtotal), 2) AS 销售额
FROM categories c
JOIN products p ON c.id = p.category_id
JOIN order_items oi ON p.id = oi.product_id
JOIN orders o ON oi.order_id = o.id
WHERE o.status != 'cancelled'
GROUP BY c.id, c.name, o.payment_method
ORDER BY c.name, 销售额 DESC""",
        "description": "交叉分析：类目×支付方式多维GROUP BY",
    },
]


def seed():
    """Load all seed examples into the vector store."""
    print(f"=== Few-shot 种子数据加载器 ===")
    print(f"准备加载 {len(SEED_EXAMPLES)} 条示例...\n")

    # Clear existing examples
    current_count = few_shot_store.count()
    if current_count > 0:
        print(f"已有 {current_count} 条示例，将重新加载")

    # Add all examples
    few_shot_store.add_examples(SEED_EXAMPLES)

    print(f"\n加载完成！向量库共 {few_shot_store.count()} 条示例。")
    print("\n=== 测试检索效果 ===\n")

    # Demo retrieval
    test_questions = [
        "这个月卖得最好的产品",
        "微信支付的订单占比",
        "钻石会员平均花多少钱",
    ]

    for q in test_questions:
        print(f"问题: {q}")
        results = few_shot_store.get_similar(q, k=2)
        for i, r in enumerate(results):
            print(f"  相似示例 {i+1} (距离={r['distance']:.3f}):")
            print(f"    问题: {r['question']}")
            print(f"    SQL:  {r['sql'][:80]}...")
        print()


if __name__ == "__main__":
    seed()
