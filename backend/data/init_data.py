"""E-commerce Demo Data Generator.

Creates the `ecommerce_demo` database with 6 tables and populates
them with realistic fake data using Faker. Also creates the
`smart_analyst` application database.

Usage:
    python -X utf8 data/init_data.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from datetime import datetime, timedelta

from faker import Faker
from sqlalchemy import create_engine, text

from app.core.config import settings

fake = Faker("zh_CN")
fake.en = Faker("en_US")

# ── Database Connection (without database name, for CREATE DATABASE) ──
root_url = f"mysql+pymysql://{settings.biz_db_user}:{settings.biz_db_password}@{settings.biz_db_host}:{settings.biz_db_port}"
engine = create_engine(root_url)


# ── Schema ──
SCHEMA_SQL = """
CREATE DATABASE IF NOT EXISTS ecommerce_demo CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS smart_analyst CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
"""

TABLES = {
    "categories": """
    CREATE TABLE IF NOT EXISTS categories (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(50) NOT NULL COMMENT '类目名称',
        description VARCHAR(200) COMMENT '类目描述',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品类目表';
    """,
    "products": """
    CREATE TABLE IF NOT EXISTS products (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(150) NOT NULL COMMENT '商品名称',
        description TEXT COMMENT '商品描述',
        price DECIMAL(10,2) NOT NULL COMMENT '价格(元)',
        stock INT DEFAULT 0 COMMENT '库存数量',
        category_id INT COMMENT '类目ID',
        status VARCHAR(20) DEFAULT 'active' COMMENT '状态(active/inactive)',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '上架时间',
        FOREIGN KEY (category_id) REFERENCES categories(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品表';
    """,
    "customers": """
    CREATE TABLE IF NOT EXISTS customers (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50) NOT NULL COMMENT '用户名',
        email VARCHAR(100) COMMENT '邮箱',
        phone VARCHAR(20) COMMENT '手机号',
        gender VARCHAR(10) COMMENT '性别(男/女)',
        city VARCHAR(50) COMMENT '城市',
        province VARCHAR(50) COMMENT '省份',
        member_level VARCHAR(20) DEFAULT '普通' COMMENT '会员等级(普通/银卡/金卡/钻石)',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间'
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='客户表';
    """,
    "orders": """
    CREATE TABLE IF NOT EXISTS orders (
        id INT AUTO_INCREMENT PRIMARY KEY,
        customer_id INT NOT NULL COMMENT '客户ID',
        total_amount DECIMAL(10,2) NOT NULL COMMENT '订单总金额',
        status VARCHAR(20) DEFAULT 'pending' COMMENT '状态(pending/paid/shipped/completed/cancelled)',
        payment_method VARCHAR(20) COMMENT '支付方式(alipay/wechat/card/cash)',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '下单时间',
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单表';
    """,
    "order_items": """
    CREATE TABLE IF NOT EXISTS order_items (
        id INT AUTO_INCREMENT PRIMARY KEY,
        order_id INT NOT NULL COMMENT '订单ID',
        product_id INT NOT NULL COMMENT '商品ID',
        quantity INT NOT NULL COMMENT '购买数量',
        unit_price DECIMAL(10,2) NOT NULL COMMENT '单价',
        subtotal DECIMAL(10,2) NOT NULL COMMENT '小计金额',
        FOREIGN KEY (order_id) REFERENCES orders(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单明细表';
    """,
    "reviews": """
    CREATE TABLE IF NOT EXISTS reviews (
        id INT AUTO_INCREMENT PRIMARY KEY,
        product_id INT NOT NULL COMMENT '商品ID',
        customer_id INT NOT NULL COMMENT '客户ID',
        order_id INT NOT NULL COMMENT '订单ID',
        rating INT NOT NULL COMMENT '评分(1-5)',
        content TEXT COMMENT '评价内容',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '评价时间',
        FOREIGN KEY (product_id) REFERENCES products(id),
        FOREIGN KEY (customer_id) REFERENCES customers(id),
        FOREIGN KEY (order_id) REFERENCES orders(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='评价表';
    """,
}

# ── Category Data ──
CATEGORIES = [
    ("手机数码", "智能手机、平板电脑、数码配件等"),
    ("电脑办公", "笔记本电脑、台式机、显示器、键鼠等"),
    ("家用电器", "冰箱、洗衣机、空调、小家电等"),
    ("服装鞋包", "男装、女装、鞋靴、箱包等"),
    ("食品饮料", "零食、饮品、生鲜、粮油等"),
    ("美妆护肤", "面部护肤、彩妆、香水、个护等"),
    ("图书教育", "文学、科技、教辅、电子书等"),
    ("运动户外", "运动鞋服、健身器材、户外装备等"),
]

# ── Product Name Templates ──
PRODUCT_TEMPLATES = {
    "手机数码": [
        "{} 5G智能手机 {}GB+{}GB", "{} 真无线蓝牙耳机", "{} 智能手表 运动版",
        "{} 平板电脑 {}英寸", "{} 快充移动电源 {}mAh", "{} 手机壳 防摔款",
        "{} Type-C数据线 1.5m", "{} 蓝牙音箱 便携版", "{} 运动手环 {}代",
        "{} 4K高清摄像头",
    ],
    "电脑办公": [
        "{} 轻薄笔记本 {}英寸", "{} 游戏本 RTX显卡", "{} 机械键盘 {}键",
        "{} 无线鼠标 静音版", "{} 显示器 {}英寸 {}Hz", "{} 固态硬盘 {}GB",
        "{} 内存条 {}GB DDR5", "{} 电脑包 {}英寸", "{} 桌面台灯 护眼款",
        "{} USB扩展坞",
    ],
    "家用电器": [
        "{} 双门冰箱 {}L", "{} 变频空调 {}匹", "{} 滚筒洗衣机 {}kg",
        "{} 微波炉 {}L", "{} 电饭煲 {}L", "{} 空气净化器",
        "{} 扫地机器人 智能版", "{} 电热水壶 {}L", "{} 破壁机 多功能",
        "{} 电风扇 落地式",
    ],
    "服装鞋包": [
        "{} 男士休闲T恤", "{} 女士连衣裙 夏季款", "{} 运动跑鞋 轻便款",
        "{} 双肩背包 大容量", "{} 牛仔裤 修身款", "{} 羽绒服 冬季款",
        "{} 商务公文包 真皮", "{} 休闲帆布鞋", "{} 防晒衣 UPF50+",
        "{} 真皮腰带",
    ],
    "食品饮料": [
        "{} 坚果礼盒 {}g", "{} 即食燕麦片 {}g", "{} 蛋白棒 12支装",
        "{} 精品咖啡豆 {}g", "{} 混合果汁 {}L", "{} 牛肉干 {}g",
        "{} 有机牛奶 {}盒装", "{} 黑巧克力 {}g", "{} 冻干水果 {}g",
        "{} 矿泉水 24瓶装",
    ],
    "美妆护肤": [
        "{} 水乳套装", "{} 防晒霜 SPF50+", "{} 精华液 {}ml",
        "{} 口红 热门色号", "{} 粉底液 持妆款", "{} 面膜 {}片装",
        "{} 洗面奶 氨基酸款", "{} 眼影盘 {}色", "{} 卸妆水 {}ml",
        "{} 身体乳 {}ml",
    ],
    "图书教育": [
        "《{}编程入门》", "《{}经济学原理》", "《{}简史》",
        "《{}的力量》", "《{}思维》", "《{}设计模式》",
        "《Python {}实战》", "《{}艺术》", "《{}心理学》",
        "《{}项目管理》",
    ],
    "运动户外": [
        "{} 瑜伽垫 {}mm", "{} 跑步鞋 专业版", "{} 登山杖 碳纤维",
        "{} 运动水壶 {}ml", "{} 速干T恤", "{} 健身哑铃 {}kg",
        "{} 露营帐篷 {}人", "{} 骑行头盔", "{} 跳绳 计数款",
        "{} 弹力带 套装",
    ],
}

BRAND_NAMES = [
    "华为", "小米", "苹果", "三星", "OPPO", "vivo", "联想", "戴尔",
    "惠普", "华硕", "海尔", "美的", "格力", "松下", "飞利浦", "索尼",
    "耐克", "阿迪达斯", "李宁", "安踏", "优衣库", "ZARA",
    "兰蔻", "雅诗兰黛", "欧莱雅", "农夫山泉", "蒙牛", "伊利",
    "当当", "京东", "当当自营", "中信出版",
]

REVIEW_TEMPLATES = [
    "非常好用，{}！物流也很快，下次还会回购。",
    "质量不错，{}，性价比高，推荐购买。",
    "一般般吧，{}，没有想象中那么好。",
    "有点失望，{}，和描述不太一样。",
    "超级满意！{}，完全超出预期！",
    "朋友推荐买的，{}，确实不错。",
    "用了一段时间了，{}，整体还行。",
    "包装很好，{}，送人也很体面。",
    "价格便宜，{}，物超所值。",
    "客服态度好，{}，售后也有保障。",
]

REVIEW_ASPECTS = [
    "做工精细", "手感很好", "功能强大", "外观漂亮", "性能稳定",
    "很轻便", "屏幕清晰", "续航持久", "音质不错", "拍照效果好",
    "操作简单", "很舒适", "容量大", "运行速度快", "散热好",
]


def generate_data():
    """Generate all demo data."""
    print("=== 电商示例数据集生成器 ===\n")

    # 1. Create databases
    print("[1/7] 创建数据库...")
    with engine.connect() as conn:
        for sql in SCHEMA_SQL.strip().split(";"):
            sql = sql.strip()
            if sql:
                conn.execute(text(sql))
        conn.commit()

    # Connect to ecommerce_demo
    biz_engine = create_engine(settings.biz_database_url)

    # 2. Create tables
    print("[2/7] 创建数据表...")
    with biz_engine.connect() as conn:
        for table_name, ddl in TABLES.items():
            conn.execute(text(ddl))
            print(f"  ✓ {table_name}")
        conn.commit()

    # 3. Insert categories
    print("[3/7] 生成类目数据...")
    with biz_engine.connect() as conn:
        for name, desc in CATEGORIES:
            conn.execute(
                text("INSERT INTO categories (name, description) VALUES (:name, :desc)"),
                {"name": name, "desc": desc},
            )
        conn.commit()
        cat_ids = [r[0] for r in conn.execute(text("SELECT id FROM categories ORDER BY id"))]
        print(f"  ✓ {len(cat_ids)} 个类目")

    # 4. Insert products (~200)
    print("[4/7] 生成商品数据...")
    products = []
    with biz_engine.connect() as conn:
        for cat_idx, (cat_name, _) in enumerate(CATEGORIES):
            templates = PRODUCT_TEMPLATES[cat_name]
            cat_id = cat_ids[cat_idx]
            for _ in range(25):
                brand = random.choice(BRAND_NAMES)
                template = random.choice(templates)
                # Fill template placeholders
                name = template
                while "{}" in name:
                    name = name.replace("{}", str(random.choice([
                        brand, str(random.randint(64, 512)),
                        str(random.randint(10, 65)), str(random.randint(100, 9999)),
                        str(random.randint(2, 6)), "Pro", "Max", "Plus", "Lite",
                    ])), 1)

                price = round(random.uniform(9.9, 9999.9), 2)
                stock = random.randint(0, 5000)
                status = random.choice(["active"] * 9 + ["inactive"])
                desc = fake.paragraph(nb_sentences=2)
                created = fake.date_time_between(start_date="-1y", end_date="now")

                conn.execute(
                    text("""
                        INSERT INTO products (name, description, price, stock, category_id, status, created_at)
                        VALUES (:name, :desc, :price, :stock, :cat_id, :status, :created)
                    """),
                    {"name": name, "desc": desc, "price": price, "stock": stock,
                     "cat_id": cat_id, "status": status, "created": created},
                )
                products.append({"name": name, "price": price, "cat_id": cat_id})

            conn.commit()
        print(f"  ✓ {len(products)} 个商品")

    # 5. Insert customers (~500)
    print("[5/7] 生成客户数据...")
    cities_provinces = [
        ("北京", "北京市"), ("上海", "上海市"), ("广州", "广东省"), ("深圳", "广东省"),
        ("杭州", "浙江省"), ("南京", "江苏省"), ("成都", "四川省"), ("武汉", "湖北省"),
        ("西安", "陕西省"), ("长沙", "湖南省"), ("重庆", "重庆市"), ("苏州", "江苏省"),
        ("天津", "天津市"), ("郑州", "河南省"), ("青岛", "山东省"), ("大连", "辽宁省"),
        ("厦门", "福建省"), ("合肥", "安徽省"), ("福州", "福建省"), ("昆明", "云南省"),
    ]
    levels = ["普通"] * 5 + ["银卡"] * 3 + ["金卡"] * 1 + ["钻石"] * 1

    customer_count = 500
    with biz_engine.connect() as conn:
        for i in range(customer_count):
            city, province = random.choice(cities_provinces)
            conn.execute(
                text("""
                    INSERT INTO customers (username, email, phone, gender, city, province, member_level, created_at)
                    VALUES (:username, :email, :phone, :gender, :city, :province, :level, :created)
                """),
                {
                    "username": fake.user_name(),
                    "email": fake.email(),
                    "phone": fake.phone_number(),
                    "gender": random.choice(["男", "女"]),
                    "city": city,
                    "province": province,
                    "level": random.choice(levels),
                    "created": fake.date_time_between(start_date="-2y", end_date="now"),
                },
            )
        conn.commit()
        print(f"  ✓ {customer_count} 个客户")

    # 6. Insert orders (~2000) and order_items (~5000)
    print("[6/7] 生成订单数据...")
    order_statuses = ["pending"] * 1 + ["paid"] * 2 + ["shipped"] * 2 + ["completed"] * 4 + ["cancelled"] * 1
    payment_methods = ["alipay", "wechat", "card", "cash"]

    order_count = 2000
    item_count = 0
    with biz_engine.connect() as conn:
        for i in range(order_count):
            customer_id = random.randint(1, customer_count)
            order_date = fake.date_time_between(start_date="-6m", end_date="now")
            status = random.choice(order_statuses)
            payment = random.choice(payment_methods)

            # Each order has 1-5 items
            n_items = random.choices([1, 2, 3, 4, 5], weights=[3, 3, 2, 1, 1])[0]
            order_total = 0
            items = []
            used_products = set()
            for _ in range(n_items):
                # Pick a random product
                prod = random.choice(products)
                prod_id = products.index(prod) + 1
                if prod_id in used_products:
                    continue
                used_products.add(prod_id)
                qty = random.randint(1, 5)
                unit_price = prod["price"]
                subtotal = round(qty * unit_price, 2)
                order_total += subtotal
                items.append((prod_id, qty, unit_price, subtotal))

            order_total = round(order_total, 2)

            # Insert order
            result = conn.execute(
                text("""
                    INSERT INTO orders (customer_id, total_amount, status, payment_method, created_at, updated_at)
                    VALUES (:cid, :total, :status, :payment, :created, :updated)
                """),
                {
                    "cid": customer_id, "total": order_total, "status": status,
                    "payment": payment, "created": order_date,
                    "updated": order_date + timedelta(hours=random.randint(1, 72)),
                },
            )
            order_id = result.lastrowid

            # Insert items
            for prod_id, qty, price, subtotal in items:
                conn.execute(
                    text("""
                        INSERT INTO order_items (order_id, product_id, quantity, unit_price, subtotal)
                        VALUES (:oid, :pid, :qty, :price, :subtotal)
                    """),
                    {"oid": order_id, "pid": prod_id, "qty": qty, "price": price, "subtotal": subtotal},
                )
                item_count += 1

            if (i + 1) % 500 == 0:
                conn.commit()
                print(f"  ... {i + 1}/{order_count} 订单")

        conn.commit()
        print(f"  ✓ {order_count} 个订单, {item_count} 条明细")

    # 7. Insert reviews (~800, only for completed orders)
    print("[7/7] 生成评价数据...")
    review_count = 0
    with biz_engine.connect() as conn:
        completed = conn.execute(text(
            "SELECT o.id, o.customer_id, oi.product_id "
            "FROM orders o JOIN order_items oi ON o.id = oi.order_id "
            "WHERE o.status = 'completed' "
            "ORDER BY RAND() LIMIT 800"
        )).fetchall()

        for order_id, customer_id, product_id in completed:
            rating = random.choices([1, 2, 3, 4, 5], weights=[1, 2, 3, 5, 9])[0]
            aspect = random.choice(REVIEW_ASPECTS)
            template = random.choice(REVIEW_TEMPLATES)
            content = template.format(aspect)

            conn.execute(
                text("""
                    INSERT INTO reviews (product_id, customer_id, order_id, rating, content, created_at)
                    VALUES (:pid, :cid, :oid, :rating, :content, :created)
                """),
                {
                    "pid": product_id, "cid": customer_id, "oid": order_id,
                    "rating": rating, "content": content,
                    "created": fake.date_time_between(start_date="-3m", end_date="now"),
                },
            )
            review_count += 1

        conn.commit()
        print(f"  ✓ {review_count} 条评价")

    # ── Summary ──
    print("\n=== 数据生成完成 ===")
    with biz_engine.connect() as conn:
        for table in ["categories", "products", "customers", "orders", "order_items", "reviews"]:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"  {table}: {count:,} 行")

    print(f"\n数据库: ecommerce_demo")
    print(f"应用库: smart_analyst")
    print("可以启动后端服务了: python -X utf8 -m uvicorn app.main:app --reload")


if __name__ == "__main__":
    generate_data()
