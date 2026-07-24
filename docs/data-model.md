# 数据模型设计 v2

> 2026-07-24 · 砍掉拼多多/taoke-mcp，仅保留大淘客单源 · 后端用 Pydantic v2 + PG + Milvus + Redis

## 0. 分层总览

| 层 | 载体 | 内容 | 里程碑 |
|---|---|---|---|
| 归一化商品模型 | Pydantic（内存/缓存/fixture 共用） | 大淘客商品统一结构 | M1 |
| 需求结构 | Pydantic（agent 间契约） | 澄清 agent 的结构化输出 | M1 |
| 打分与决策报告 | Pydantic（agent 间契约）+ PG 存档 | 可解释打分明细 | M2 |
| 业务表 | PostgreSQL（`app` schema） | 用户/线程/报告/记忆 | M1 起 |
| 向量库 | Milvus（3 collections） | 口碑语料/情景记忆/商品池 | M3 |
| 缓存 | Redis key 规范 | API 缓存/画像热点/限流 | M1 起 |

## 1. 大淘客 API 接口完整字段

host 统一为 `https://openapi.dataoke.com`，所有接口需公共参数 `appKey` + `version` + `type`（签名校验，`sign` 由 SDK 生成）。

### 1.1 大淘客搜索 id=9 `/api/goods/get-dtk-search-goods`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| pageSize | Number | 是 | 每页条数，默认 100，最大 100，仅支持 10/50/100 |
| pageId | String | 是 | 分页 id，默认 1，支持 scroll_id 翻页 |
| keyWords | String | 否 | 关键词搜索 |
| cids | String | 否 | 一级分类 id，多个英文逗号分隔（1-女装，2-母婴，3-美妆…） |
| subcid | Number | 否 | 二级分类 id |
| juHuaSuan | Number | 否 | 聚划算筛选 |
| taoQiangGou | Number | 否 | 淘抢购筛选 |
| tmall | Number | 否 | 是否天猫商品 |
| tchaoshi | Number | 否 | 天猫超市筛选 |
| goldSeller | Number | 否 | 金牌卖家筛选 |
| haitao | Number | 否 | 海淘商品筛选 |
| brand | Number | 否 | 品牌商品筛选 |
| brandIds | String | 否 | 品牌 id |
| priceLowerLimit | Number | 否 | 价格下限（券后价） |
| priceUpperLimit | Number | 否 | 价格上限（券后价） |
| couponPriceLowerLimit | Number | 否 | 优惠券金额下限 |
| commissionRateLowerLimit | Number | 否 | 佣金比率下限 |
| monthSalesLowerLimit | Number | 否 | 月销量下限 |
| sort | String | 否 | 排序：0-综合，1-上架时间，2-热销，3-领券量，4-佣金，5-价格降序，6-价格升序 |
| freeshipRemoteDistrict | Number | 否 | 偏远地区包邮筛选 |
| hasCoupon | Number | 否 | 是否有券 |
| inspectedGoods | Number | 否 | 是否验货商品 |

**返回字段（顶层，部分核心字段）：**

| 字段 | 类型 | 说明 |
|---|---|---|
| goodsId | String | 淘宝商品 id |
| goodsSign | String | 新商品 id（每次转链后变化） |
| title | String | 淘宝标题 |
| dtitle | String | 大淘客短标题 |
| originalPrice | Number | 商品原价（元） |
| actualPrice | Number | 券后价（元） |
| shopType | Number | 店铺类型，1-天猫，0-淘宝 |
| monthSales | Number | 30 天热销 |
| twoHoursSales | Number | 2 小时热销 |
| dailySales | Number | 当日热销 |
| commissionType | Number | 佣金类型，0-通用，1-定向，2-高佣，3-营销计划 |
| desc | String | 推广文案 |
| couponReceiveNum | Number | 领券量 |
| couponLink | String | 优惠券链接 |
| couponEndTime | String | 优惠券结束时间 |
| couponStartTime | String | 优惠券开始时间 |
| couponPrice | Number | 优惠券金额（元） |
| couponConditions | String | 优惠券使用条件 |
| activityType | Number | 活动类型，1-无活动，2-淘抢购，3-聚划算 |
| createTime | String | 商品上架时间 |
| mainPic | String | 商品主图链接 |
| marketingMainPic | String | 营销主图链接 |
| sellerId | String | 淘宝卖家 id |
| cid | Number | 大淘客分类 id |
| subcid | List[Number] | 大淘客二级分类 id |
| tbcid | Number | 淘宝分类 id |
| discounts | Number | 折扣力度 |
| commissionRate | Number | 佣金比例（%） |
| couponTotalNum | Number | 券总量 |
| activityStartTime | String | 活动开始时间 |
| activityEndTime | String | 活动结束时间 |
| shopName | String | 店铺名称 |
| shopLevel | Number | 淘宝店铺等级 |
| descScore | Number | 描述分 |
| dsrScore | Number | 描述相符 |
| dsrPercent | Number | 描述同行比 |
| shipScore | Number | 物流服务 |
| shipPercent | Number | 物流同行比 |
| serviceScore | Number | 服务态度 |
| servicePercent | Number | 服务同行比 |
| brand | Number | 是否品牌商品 |
| brandId | Number | 品牌 id |
| brandName | String | 品牌名称 |
| hotPush | Number | 热推值 |
| teamName | String | 放单人名称 |
| itemLink | String | 商品淘宝链接 |
| quanMLink | Number | 定金（无则 0） |
| hzQuanOver | Number | 立减（无则 0） |
| yunfeixian | Number | 0-不包运费险，1-包运费险 |
| estimateAmount | Number | 预估淘礼金 |
| freeshipRemoteDistrict | Number | 0-不包邮，1-包邮 |
| brandList | List | 品牌列表（brandId/brandLogo/brandName） |
| discountType | Number | 1-购物津贴，2-跨店满减，0-无 |
| discountFull | Number | 活动满减的满值 |
| discountCut | Number | 活动满减的减值 |
| marketGroup | marketGroup | 热门活动 ID |
| activityInfo | activityInfo | 活动信息（activityName/activityId） |
| inspectedGoods | Number | 0-未验货，1-已验货 |
| shopLogo | String | 店铺 logo |

### 1.2 商品列表 id=5 `/api/goods/get-goods-list`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| pageId | String | 是 | 分页 id，默认 1，支持 scroll_id |
| pageSize | Number | 否 | 每页条数，默认 10，最大 100，仅支持 10/50/100 |
| ai_summarize_score | Number | 否 | 1-返回 AI 爆品清单 |
| sort | String | 否 | 排序，0-综合，1-上架时间，2-热销，3-领券量，4-佣金，5-价格降序，6-价格升序，7-券金额降序 |
| cids | String | 否 | 一级分类 id |
| subcid | Number | 否 | 二级分类 id |
| specialId | Number | 否 | 专项筛选 |
| juHuaSuan / taoQiangGou / tmall / tchaoshi / goldSeller / haitao / pre / preSale / brand / brandIds | Number | 否 | 各类筛选标记 |
| priceLowerLimit / priceUpperLimit | Number | 否 | 券后价范围 |
| couponPriceLowerLimit | Number | 否 | 优惠券金额下限 |
| commissionRateLowerLimit | Number | 否 | 佣金比率下限 |
| monthSalesLowerLimit | Number | 否 | 月销量下限 |
| freeshipRemoteDistrict | Number | 否 | 偏远地区包邮 |
| directCommissionType | Number | 否 | 定向佣金类型 |
| flagShipStore | Number | 否 | 旗舰店筛选 |
| isNew | Number | 否 | 新品筛选 |
| lowestPrice | Number | 否 | 历史最低价筛选 |
| activityId | String | 否 | 活动 id 筛选 |
| hasCoupon | Number | 否 | 是否有券 |
| inspectedGoods | Number | 否 | 验货商品 |
| maxCouponAmount | Number | 否 | 最大券金额 |
| maxCommissionRate | Number | 否 | 最大佣金率 |

**返回字段：** 与搜索(9)基本一致，额外含以下字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| video | String | 商品视频链接 |
| couponTotalNum | Number | 券总量 |
| couponReceiveNum | Number | 领券量 |
| couponEndTime / couponStartTime | String | 券有效期 |
| previewStartTime | String | 商品开始时间（大于当前时间为预告） |
| activityType | Number | 1-无活动，2-淘抢购，3-聚划算 |
| activityStartTime / activityEndTime | String | 活动时间 |
| haitao | Number | 1-海淘，0-非海淘 |
| sellerId | String | 淘宝卖家 id |
| shopLevel | Number | 店铺等级 |
| descScore | Number | 描述分 |
| dsrScore / dsrPercent | Number | 描述相符及同行比 |
| shipScore / shipPercent | Number | 物流服务及同行比 |
| serviceScore / servicePercent | Number | 服务态度及同行比 |
| hotPush | Number | 热推值 |
| teamName | String | 放单人名称 |
| quanMLink | Number | 定金 |
| hzQuanOver | Number | 立减 |
| yunfeixian | Number | 是否包运费险 |
| estimateAmount | Number | 预估淘礼金 |
| shopLogo | String | 店铺 logo |
| specialText | List | 特色文案（买一送一/第二件 0 元等） |
| freeshipRemoteDistrict | Number | 偏远地区包邮 |
| goldSellers | Number | 是否金牌卖家 |
| directCommissionType / directCommission / directCommissionLink | Number/String | 定向佣金信息 |
| discountType / discountFull / discountCut | Number | 满减信息 |
| marketGroup | marketGroup | 配置活动 ID |
| activityInfo | activityInfo | 活动信息（activityName/activityId） |
| inspectedGoods | Number | 是否验货 |
| aiSummarizeScore | Number | AI 总结得分（80-90 四星，90+ 五星） |

### 1.3 高效转链 id=7 `/api/goods/get-privilege-link`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| goodsId | String | 是 | 淘宝商品 id |
| couponId | String | 否 | 优惠券 ID |
| pid | string | 否 | 推广位 ID，不填用默认 |
| channelId | string | 否 | 渠道 id（对应联盟 relationId） |
| bizSceneId | Number | 否 | 2023/02/24 后不再支持 |
| promtionType | Number | 否 | 促销类型 |
| rebateType | Number | 否 | 返利类型 |
| specialId | string | 否 | 专项 id |
| externalId | string | 否 | 外部 id |
| xid | string | 否 | - |
| leftSymbol / rightSymbol | string | 否 | 自定义前后缀 |
| authId | Number | 否 | 平台授权 ID（项目不传，走默认） |
| bybtqdyh | string | 否 | - |
| getTopnRate | Number | 否 | 获取前 N 件佣金率 |

**返回字段：**

| 字段 | 类型 | 说明 |
|---|---|---|
| couponEndTime | String | 优惠券结束时间 |
| couponInfo | String | 优惠券面额（满 16 减 10 元） |
| couponStartTime | String | 优惠券开始时间 |
| itemId | Number | 商品 id |
| couponTotalCount | Number | 优惠券总量 |
| couponRemainCount | Number | 优惠券剩余量 |
| itemUrl | String | 商品淘客链接 |
| tpwd | String | 淘口令 |
| longTpwd | String | 长淘口令（适配 iOS14） |
| maxCommissionRate | String | 佣金比例（%） |
| shortUrl | String | 短链接 |
| minCommissionRate | String | 预估最低佣金率（传 channelId 等） |
| kuaiZhanUrl | String | 快站链接（微信端可直访） |
| originalPrice | Number | 商品原价 |
| actualPrice | Number | 券后价 |
| topnEndTime / topnStartTime | String | 前 N 件佣金时间 |
| topnQuantity | Number | 前 N 件剩余库存 |
| topnTotalCount | Number | 前 N 件初始总库存 |

### 1.4 万能解析转链 id=33 `/api/goods/parse-link`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| content | String | 是 | 包含淘口令、链接的文本，优先解析淘口令再解析链接 |
| pid | String | 否 | 推广位 ID，不填用默认 |
| channelId | String | 否 | 渠道 id |
| authId | Number | 否 | 授权 ID（不传） |
| bybtqdyh | String | 否 | - |
| specialId | string | 否 | 专项 id |
| isSupered | string | 否 | 超红相关 |

**返回字段：**

| 字段 | 类型 | 说明 |
|---|---|---|
| originUrl | String | 原始链接 |
| originType | String | 链接信息类型（二合一券等） |
| originInfo | object | 链接信息详情 |
| originInfo.title | String | 商品标题 |
| originInfo.shopName | String | 店铺名 |
| originInfo.shopLogo | String | 店铺 LOGO |
| originInfo.image | String | 商品主图 |
| originInfo.startTime / endTime | String | 券时间 |
| originInfo.amount | Number | 券金额 |
| originInfo.startFee | Number | 券门槛金额 |
| originInfo.price | Number | 商品价格 |
| originInfo.activityId | String | 券 ID |
| originInfo.pid | String | PID |
| originInfo.status | Number | 券状态，0-可用 |
| itemId / itemName / mainPic | String | 商品信息（dataType=goods） |
| dataType | String | goods / activity |
| couponSrcScene | Number | 优惠券类型，0-全网公开券，1-阿里妈妈券 |
| itemLink | String | 商品链接 |
| couponLink | String | 优惠券链接 |
| bizSceneId | Number | 场景 ID |
| real_post_fee | Number | 商品邮费 |
| cpsLongUrl / cpsFullTpwd / shortUrl / shortTpwd | String | CPS 转链（长链/长口令/短链/短口令） |
| couponSuperedLongUrl / couponSuperedLongTpwd / couponSuperedShortUrl / couponSuperedShortTpwd | String | 超红二合一链接 |
| cpsSuperedLongUrl / cpsSuperedLongTpwd / cpsSuperedShortUrl / cpsSuperedShortTpwd | String | 超红 CPS 链接 |
| couponLongUrl | String | 二合一长链接 |

### 1.5 历史券后价 id=36 `/api/goods/price-trend`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | String | 是 | 大淘客在线商品 id |
| goodsId | String | 否 | 淘宝商品 id |

**返回字段：**

| 字段 | 类型 | 说明 |
|---|---|---|
| goodsId | String | 淘宝商品 id |
| itemLink | String | 商品淘宝链接 |
| title | String | 淘宝标题 |
| dtitle | String | 短标题 |
| originalPrice | Number | 商品原价 |
| historicalPrice | List | 历史券后价列表 |
| historicalPrice[].date | date | 日期 |
| historicalPrice[].actualPrice | Number | 对应日期的券后价 |
| monthSales | Number | 30 天热销 |
| twoHoursSales / dailySales | Number | 热销数据 |
| commissionType | Number | 佣金类型 |
| desc | String | 推广文案 |
| couponReceiveNum | Number | 领券量 |
| couponEndTime / couponStartTime | String | 券有效期 |
| couponPrice | Number | 优惠券金额 |
| couponConditions | String | 优惠券使用条件 |
| mainPic | String | 商品主图 |
| marketingMainPic | String | 营销主图 |
| commissionRate | Number | 佣金比例 |
| couponTotalNum | Number | 券总量 |
| brandId | Number | 品牌 id |
| brandName | String | 品牌名称 |

## 2. NormalizedProduct（归一化商品模型，M1 核心）

```python
class NormalizedProduct(BaseModel):
    # 标识
    platform: Literal["taobao"] = "taobao"   # 单源，预留扩展
    goods_id: str                            # 大淘客 goodsId
    goods_sign: str | None = None            # 新 id（转链后变化）
    # 基础信息
    title: str
    dtitle: str | None = None                # 大淘客短标题
    brand: str | None = None
    category_path: list[str] = []             # 尝试从 cid/subcid 映射中文名
    shop_name: str | None = None
    shop_type: str | None = None              # tmall / taobao
    # 价格（统一为元，Decimal，禁止浮点）
    price: Decimal                            # 券后价 actualPrice
    original_price: Decimal | None = None     # 原价 originalPrice
    coupon_amount: Decimal = Decimal(0)       # 优惠券金额 couponPrice
    coupon_conditions: str | None = None      # 使用条件 couponConditions
    # 市场信号
    sales: int | None = None                  # monthSales，口径=30天热销
    daily_sales: int | None = None
    commission_rate: float | None = None       # 佣金比例%
    discounts: float | None = None             # 折扣力度
    # 店铺评分
    dsr_score: float | None = None
    ship_score: float | None = None
    service_score: float | None = None
    # 内容与链接
    main_image: str
    marketing_image: str | None = None
    images: list[str] = []
    detail_url: str                            # itemLink 或转链短链
    coupon_link: str | None = None
    selling_points: str | None = None          # desc 推广文案
    special_texts: list[str] = []              # 特色文案
    # 历史价格（M2 由 price-trend 接口填充）
    price_history: list[dict] | None = None    # [{"date": "2022-10-24", "price": 28.5}]
    # 活动信息
    activity_type: str | None = None           # 无活动/淘抢购/聚划算
    has_coupon: bool = True
    free_ship: bool | False                   # freeshipRemoteDistrict
    # 溯源
    fetched_at: datetime
    extra: dict = {}                          # 平台特有字段 + 原始响应 raw
```

**大淘客字段映射表：**

| NormalizedProduct 字段 | 大淘客源字段 | 说明 |
|---|---|---|
| goods_id | goodsId | String |
| goods_sign | goodsSign | String |
| title | title | String |
| dtitle | dtitle | String |
| brand | brandName | String |
| shop_name | shopName | String |
| shop_type | shopType (1→tmall, 0→taobao) | Number→映射 |
| price | actualPrice | Number→Decimal(元) |
| original_price | originalPrice | Number→Decimal(元) |
| coupon_amount | couponPrice | Number→Decimal(元) |
| coupon_conditions | couponConditions | String |
| sales | monthSales | Number→int |
| daily_sales | dailySales | Number→int |
| commission_rate | commissionRate | Number→float |
| discounts | discounts | Number→float |
| dsr_score | dsrScore | Number→float |
| ship_score | shipScore | Number→float |
| service_score | serviceScore | Number→float |
| main_image | mainPic | String（补 https 前缀） |
| marketing_image | marketingMainPic | String |
| detail_url | itemLink | String |
| coupon_link | couponLink | String |
| selling_points | desc | String |
| special_texts | specialText | List |
| activity_type | activityType (1→无,2→淘抢购,3→聚划算) | Number→映射 |
| has_coupon | couponPrice > 0 | 推断 |
| free_ship | freeshipRemoteDistrict == 1 | Number→bool |
| price_history | historicalPrice[].{date,actualPrice} | M2 填充 |
| extra.raw | 原始 response | fixture 回放用 |
| extra.sales_caption | "30天热销" | 口径标注 |
| extra.cid / extra.subcid / extra.tbcid | cid / subcid / tbcid | 分类映射用 |
| extra.ai_score | aiSummarizeScore | AI 评分 |

设计决策：

- **金额一律 Decimal、单位元**，大淘客返回的 Number 直接转 Decimal，无除法运算。
- **`extra.raw` 保留原始响应**：fixture 落盘与 Redis 缓存共用 `model_dump_json()`，缓存层与回放层同构，测试直接喂 fixture。
- 适配器只写一个 `TaobaoDtkAdapter`，输入原始响应、输出 `NormalizedProduct`，是纯函数，单测无网络。
- `detail_url` 流程：M1 直接用 itemLink（原始链接）；M3 经高效转链(7)生成 shortUrl 后替换。

## 3. ShoppingRequirement（需求结构，澄清 agent 输出）

```python
class ShoppingRequirement(BaseModel):
    category: str                         # 品类："蓝牙耳机" / "露营装备"
    scenario: str | None = None           # 场景："通勤降噪" / "周末双人露营"
    budget_min: Decimal | None = None
    budget_max: Decimal | None = None     # 至少填一个，缺则 interrupt 反问
    must_have: list[str] = []             # 硬约束："续航>20h"、"IPX5 防水"
    nice_to_have: list[str] = []          # 软偏好："白色优先"
    excluded: list[str] = []              # 排除项："不要某品牌"
    combo: bool = False                   # 是否组合采购
    slots: list[str] = []                 # combo=True 的槽位：["帐篷","睡袋","炉具"]
```

- 这是**澄清 agent 与下游所有 agent 的契约**，LangGraph state 里的核心字段；`budget_max`/`must_have` 缺失是触发 `interrupt` 反问的判定依据。
- 硬约束（must_have/excluded）进反思校验的打回规则；软偏好只影响打分权重。

## 4. 打分明细与决策报告（M2 核心，契约先定）

```python
class AspectScore(BaseModel):
    aspect: str                           # price / value / brand / reputation / sales / price_trend
    score: float                          # 0-10
    weight: float                         # 0-1，记忆召回可动态上调（如预算敏感→price）
    evidence: str                         # 打分依据，"可解释"卖点的数据基础

class ScoredProduct(BaseModel):
    product: NormalizedProduct
    aspects: list[AspectScore]
    total: float
    rank: int

class DecisionReport(BaseModel):
    requirement: ShoppingRequirement
    recommendations: list[ScoredProduct] = []    # 单品场景
    combos: list[list[ScoredProduct]] = []       # 组合场景：2-3 套方案
    summary: str = ""                            # LLM 决策说明
    reflection_notes: list[str] = []            # 反思校验记录（打回原因等）
    created_at: datetime
```

- **`evidence` 必填**：前端决策报告卡片直接渲染它，面试演示"每个分数都有出处"。
- `reflection_notes` 保留打回历史，报告页可展示"第 1 版方案超预算 12%，已重规划"。

## 5. PostgreSQL 业务表（`app` schema）

LangGraph PostgresSaver 自建 checkpoint 表（public schema），业务表独立放 `app` schema，互不污染。

```sql
-- M1
CREATE SCHEMA IF NOT EXISTS app;

CREATE TABLE app.users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    created_at timestamptz DEFAULT now()
);

CREATE TABLE app.threads (
    id text PRIMARY KEY,                 -- 与 LangGraph thread_id 一致
    user_id uuid REFERENCES app.users(id),
    title text,
    created_at timestamptz DEFAULT now()
);

-- M2（报告存档，供历史查看与评估集建设）
CREATE TABLE app.decision_reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES app.users(id),
    thread_id text REFERENCES app.threads(id),
    requirement jsonb NOT NULL,
    report jsonb NOT NULL,
    created_at timestamptz DEFAULT now()
);

-- M3（长期记忆：结构化画像）
CREATE TABLE app.profile_facts (
    id bigserial PRIMARY KEY,
    user_id uuid REFERENCES app.users(id),
    category text NOT NULL,              -- budget / brand / size / scenario
    key text NOT NULL,                   -- "预算带" / "偏好品牌" / "排斥品牌"
    value text NOT NULL,
    confidence real DEFAULT 1.0,
    source text DEFAULT 'dialog',        -- dialog / explicit / inferred
    updated_at timestamptz DEFAULT now(),
    UNIQUE (user_id, category, key)
);

-- M3（长期记忆：情景记忆元数据，向量在 Milvus）
CREATE TABLE app.episodic_memories (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES app.users(id),
    content text NOT NULL,               -- "上次退了某品牌因为续航"
    milvus_id text NOT NULL,             -- 对应 episodic_memory collection 主键
    importance real DEFAULT 0.5,
    created_at timestamptz DEFAULT now(),
    last_recalled_at timestamptz
);
```

## 6. Milvus collections（M3，schema 先定死）

embedding 统一 qwen3-embedding（本地 Ollama，4096 维，COSINE，索引 IVF_FLAT + nprobe 16）：

| Collection | 字段 | 说明 |
|---|---|---|
| `review_corpus` | id(pk), vector(4096), text(varchar 4096), source, category, aspects(array varchar), goods_id(null) | 口碑语料 chunk，方面级标注 |
| `episodic_memory` | id(pk=uuid 字符串), vector, user_id(varchar 64), content(varchar 1024), importance(float), created_at(int64) | 与 PG episodic_memories 双写 |
| `product_pool` | id(pk), vector, user_id, goods_id, title(varchar 512), price(float), event_type(view/fav/inquire), created_at | 用户交互商品的语义召回 |

## 7. Redis key 规范（M1 起）

```
goods:search:{md5(归一化查询)}        JSON   TTL 6h    # 搜索候选缓存
goods:detail:{goods_id}               JSON   TTL 12h   # 详情缓存
goods:price_trend:{goods_id}         JSON   TTL 24h   # 历史价缓存
profile:{user_id}                     JSON   TTL 1h    # 画像热点，写穿透 PG
ratelimit:{yyyy-mm-dd}                INCR   TTL 24h   # API 配额计数与降级
mem:write_buffer:{user_id}            LIST   无 TTL    # 记忆提取写入缓冲
```

降级规则：API 失败或超限 → 读缓存（无视 TTL 兜底）→ 缓存也没有 → 读本地 fixture → 都没有则工具返回显式错误，agent 如实告知用户而非编造。

## 8. fixture 规范（测试与配额保护）

- 路径：`fixtures/{api_name}/{md5(请求参数)}.json`
- 内容：`NormalizedProduct.model_dump_json()` 或原始响应（`extra.raw` 同源）
- 单测/联调默认走 fixture；录制开关 `FIXTURE_RECORD=1` 时才打真实 API 并落盘

## 9. 落码位置

```
backend/
  app/models/product.py       # NormalizedProduct + 适配器协议
  app/models/requirement.py   # ShoppingRequirement
  app/models/decision.py      # AspectScore / ScoredProduct / DecisionReport
  app/adapters/dtk.py         # 大淘客原始响应 → NormalizedProduct
  app/db/schema.sql           # 第 5 节的 DDL
  app/cache/redis.py          # Redis 封装
  app/config.py              # pydantic-settings 读 .env
  app/main.py                # FastAPI 入口（M1 SSE 骨架）
backend/tests/
  test_adapter_dtk.py         # 适配器单测（fixture 喂入）
  conftest.py
docker-compose.yml            # PG / Redis / Milvus
requirements.txt             # Python 依赖
.env.example                  # 环境变量占位符（不含真实密钥）
```
