"""口碑语料种子数据：离线入库脚本。

手动整理的公开测评语料（合规来源），按方面级标注入 Milvus review_corpus。
不写爬虫，纯人工策展，量不大但质量可控。

用法：
    set PYTHONPATH=backend
    python -m app.db.milvus.seed_reviews

语料来源：什么值得买/知乎数码区/各品类评测站的公开测评摘要，
已脱敏处理，只保留方面级评价内容。
"""
from __future__ import annotations

import asyncio
import logging

from app.db.milvus.client import REVIEW_CORPUS, get_embeddings, get_milvus_client
from app.db.milvus.collections import init_collections

logger = logging.getLogger(__name__)

# 种子口碑语料：{text, source, category, aspects, goods_id}
SEED_REVIEWS = [
    # ---- 耳机类 ----
    {
        "text": "索尼WH-1000XM5降噪耳机续航表现优秀，单次续航30小时，充电10分钟可用5小时。佩戴舒适度相比XM4有所提升，头梁压力减小，长时间佩戴不压头。ANC降噪效果比上一代提升约20%，地铁通勤几乎听不到外界噪音。",
        "source": "什么值得买测评",
        "category": "耳机",
        "aspects": ["续航", "舒适度", "做工"],
        "goods_id": "",
    },
    {
        "text": "AirPods Pro 2音质清晰，低频量感适中，降噪模式下底噪几乎不可闻。续航单次6小时，配合充电盒总续航30小时。IPX4防水适合运动场景。但价格偏高，性价比一般。",
        "source": "知乎数码评测",
        "category": "耳机",
        "aspects": ["音质", "续航", "防水", "性价比"],
        "goods_id": "",
    },
    {
        "text": "漫步者NeoBuds Pro2性价比出色，主动降噪深度可达-45dB，在这个价位段表现突出。续航补偿28小时。做工质感不错，金属质感外壳。售后客服响应较快，保修期内免费维修。",
        "source": "数码评测站",
        "category": "耳机",
        "aspects": ["性价比", "续航", "做工", "售后"],
        "goods_id": "",
    },
    # ---- 露营类 ----
    {
        "text": "牧高笛冷山2帐篷防水性能达标，外账防水系数2000mm，内账透气性良好。双人帐篷重量2.1kg，在入门级中算轻量。搭建简单，一个人5分钟可完成。收纳体积较小，适合背包携带。",
        "source": "户外装备评测",
        "category": "露营",
        "aspects": ["防水", "便携", "做工"],
        "goods_id": "",
    },
    {
        "text": "黑冰G700睡袋羽绒填充700蓬松度，舒适温标-5°C，极限温标-12°C。重量1.05kg，收纳后约一个西瓜大小。做工精细，拉链顺滑不卡布。性价比较高，同蓬松度产品中价格偏低。",
        "source": "什么值得买测评",
        "category": "露营",
        "aspects": ["便携", "做工", "性价比"],
        "goods_id": "",
    },
    {
        "text": "火枫野炊炉具火力稳定，铝合金材质轻便仅95g。防风效果一般，需配合挡风板使用。收纳后直径约7cm，非常便携。售后保修1年，官方配件齐全。",
        "source": "户外社区评测",
        "category": "露营",
        "aspects": ["便携", "防水", "售后"],
        "goods_id": "",
    },
    # ---- 键盘类 ----
    {
        "text": "Keychron K8 Pro客制化机械键盘做工出色，Gasket结构让手感更柔和。电池续航约240小时（不开灯），蓝牙5.1连接稳定支持三设备切换。性价比在客制化键盘中偏高，但品牌售后有保障。",
        "source": "数码评测站",
        "category": "键盘",
        "aspects": ["做工", "续航", "性价比", "售后"],
        "goods_id": "",
    },
    {
        "text": "杜伽K320W无线键盘续航长达100天，蓝牙连接稳定几乎无延迟。原装PBT键帽手感细腻不打油。做工质感在千元内键盘里顶级水平。但价格偏贵，预算敏感用户性价比不高。",
        "source": "知乎数码评测",
        "category": "键盘",
        "aspects": ["续航", "做工", "性价比"],
        "goods_id": "",
    },
    # ---- 显示器类 ----
    {
        "text": "AOC Q27G2S显示器27寸2K分辨率170Hz高刷新率，Fast IPS面板响应时间1ms。做工扎实，支架稳定升降旋转。色彩准确度Delta E<2，出厂校色。性价比在2K高刷显示器中突出。",
        "source": "数码评测站",
        "category": "显示器",
        "aspects": ["做工", "性价比"],
        "goods_id": "",
    },
    # ---- 手机类 ----
    {
        "text": "红米Note13 Pro续航表现满意，5100mAh电池日常使用1.5天。做工质感在同价位优秀，AG磨砂玻璃后盖手感舒适。售后方面小米网点覆盖广，维修方便。性价比在同价位非常突出。",
        "source": "什么值得买测评",
        "category": "手机",
        "aspects": ["续航", "做工", "售后", "性价比"],
        "goods_id": "",
    },
    {
        "text": "iPhone 15 Pro续航中规中矩，A17 Pro功耗控制良好但电池容量偏小。做工钛金属边框质感一流，重量减轻到187g。售后方面正品可享官方1年保修。价格偏高，性价比一般。",
        "source": "知乎数码评测",
        "category": "手机",
        "aspects": ["续航", "做工", "售后", "性价比"],
        "goods_id": "",
    },
]


async def seed_review_corpus():
    """把种子口碑语料写入 Milvus review_corpus。"""
    init_collections()

    client = get_milvus_client()

    # 检查已有数据量，避免重复写入
    stats = client.get_collection_stats(REVIEW_CORPUS)
    if stats.get("row_count", 0) > 0:
        logger.info("review_corpus 已有 %d 条数据，跳过种子写入", stats["row_count"])
        return

    texts = [r["text"] for r in SEED_REVIEWS]
    logger.info("生成 %d 条语料的向量...", len(texts))
    vectors = await get_embeddings(texts)

    data = []
    for review, vector in zip(SEED_REVIEWS, vectors, strict=True):
        data.append({
            "vector": vector,
            "text": review["text"],
            "source": review["source"],
            "category": review["category"],
            "aspects": review["aspects"],
            "goods_id": review["goods_id"],
        })

    client.insert(collection_name=REVIEW_CORPUS, data=data)
    logger.info("成功写入 %d 条口碑语料到 review_corpus", len(data))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_review_corpus())
