"""演示数据：幂等写入 30 个商品、6 个分类、SKU 与券。

只在不存在时创建，不覆盖已有价格/库存，避免重跑把演示改价和库存重置掉。
分类与封面属于结构信息，已有商品缺这两项时补齐，已有值不动。
"""

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from catalog.models import SKU, Product
from promotion.models import Coupon

K = Product.Category.KEYBOARD
M = Product.Category.MOUSE
H = Product.Category.HEADSET
N = Product.Category.MONITOR
S = Product.Category.STAND
D = Product.Category.DOCK

CATALOG = [
    {
        "name": "机械键盘 87 键",
        "subtitle": "热插拔轴体，PBT 键帽",
        "description": "87 键紧凑布局，省下鼠标的活动空间。轴体热插拔，不用焊接就能换手感；键帽长期不打油。",
        "category": K,
        "cover": "/img/products/kbd-87.svg",
        "skus": [("KBD-87-BRN", "茶轴", "289.00", 80), ("KBD-87-RED", "红轴", "299.00", 60)],
    },
    {
        "name": "机械键盘 104 键",
        "subtitle": "全键无冲，带数字小键盘",
        "description": "104 键全尺寸，带独立数字区，适合报表和记账。全键无冲，六键同时按下也不丢字符。",
        "category": K,
        "cover": "/img/products/kbd-104.svg",
        "featured": True,
        "skus": [("KBD-104-BRN", "茶轴", "359.00", 50)],
    },
    {
        "name": "矮轴机械键盘 68 键",
        "subtitle": "厚度 22mm，蓝牙三模",
        "description": "矮轴机身比常规机械键盘薄三分之一，装进背包不硌。蓝牙可连三台设备，来回切。",
        "category": K,
        "cover": "/img/products/kbd-68.svg",
        "featured": True,
        "skus": [("KBD-68-LOW", "矮红轴", "429.00", 35)],
    },
    {
        "name": "静电容键盘",
        "subtitle": "35g 轻压力，长时间不累",
        "description": "静电容没有物理触点磨损，按压力度只有常规红轴的一半。敲一天代码手指不发酸，声音也闷。",
        "category": K,
        "cover": "/img/products/kbd-ec.svg",
        "skus": [("KBD-EC-87", "35g 全域", "899.00", 12)],
    },
    {
        "name": "分体人体工学键盘",
        "subtitle": "左右分离，手腕不外翻",
        "description": "左右两半分开摆，肩膀自然打开，手腕不用往里撇。倾角三档可调，配掌托用一天也不别扭。",
        "category": K,
        "cover": "/img/products/kbd-split.svg",
        "skus": [("KBD-SPLIT", "分体式", "1299.00", 8)],
    },
    {
        "name": "无线鼠标",
        "subtitle": "静音微动，2.4G + 蓝牙",
        "description": "微动做了静音处理，夜里用不吵人。2.4G 和蓝牙各一路，插着接收器也能同时连平板。",
        "category": M,
        "cover": "/img/products/mou-wireless.svg",
        "featured": True,
        "skus": [("MOU-2G", "黑色", "99.00", 200), ("MOU-2G-W", "白色", "109.00", 150)],
    },
    {
        "name": "垂直人体工学鼠标",
        "subtitle": "55 度握姿，缓解腕部压力",
        "description": "55 度倾斜让手掌立起来，前臂不用拧着放。前两天会不适应，一周后手腕酸胀通常明显减轻。",
        "category": M,
        "cover": "/img/products/mou-ergo.svg",
        "featured": True,
        "skus": [("MOU-ERG", "中号", "159.00", 90), ("MOU-ERG-L", "大号", "169.00", 60)],
    },
    {
        "name": "轻量化游戏鼠标",
        "subtitle": "58g 机身，8000 DPI",
        "description": "58g 的重量甩起来不费劲，长时间对局手腕负担小。传感器最高 8000 DPI，四档一键切换。",
        "category": M,
        "cover": "/img/products/mou-game.svg",
        "featured": True,
        "skus": [("MOU-GAME-58", "黑色", "349.00", 40)],
    },
    {
        "name": "静音办公鼠标",
        "subtitle": "按键无声，一节电池用一年",
        "description": "左右键和滚轮都做了消音，开放办公室用不打扰同事。一节 5 号电池约能用一年。",
        "category": M,
        "cover": "/img/products/mou-silent.svg",
        "skus": [("MOU-SILENT", "灰色", "79.00", 180)],
    },
    {
        "name": "无线充电鼠标垫套装",
        "subtitle": "鼠标 + 充电垫，桌面少一根线",
        "description": "垫子内置无线充电线圈，鼠标放上去就充，不用插线也不用换电池。硬质细面，滑动顺滑。",
        "category": M,
        "cover": "/img/products/mou-pad.svg",
        "skus": [("MOU-PAD", "套装", "199.00", 70)],
    },
    {
        "name": "降噪蓝牙耳机",
        "subtitle": "40dB 主动降噪，通勤可用",
        "description": "40dB 主动降噪，地铁和飞机的低频噪音基本压住。通透模式一键切换，不摘也听得清报站。",
        "category": H,
        "cover": "/img/products/ear-anc.svg",
        "featured": True,
        "skus": [("EAR-100", "标准版", "399.00", 120), ("EAR-100-PRO", "旗舰版", "599.00", 40)],
    },
    {
        "name": "头戴式游戏耳麦",
        "subtitle": "50mm 单元，可拆麦克风",
        "description": "50mm 动圈单元，低频量足但不糊。麦克风可拆，不听语音时取下来当普通耳机用。",
        "category": H,
        "cover": "/img/products/ear-game.svg",
        "featured": True,
        "skus": [("EAR-GAME", "黑色", "329.00", 55)],
    },
    {
        "name": "真无线入耳耳机",
        "subtitle": "单次 8 小时，充电盒共 32 小时",
        "description": "单耳 8 小时续航，配充电盒合计 32 小时，通勤够用一周。入耳检测摘下自动暂停。",
        "category": H,
        "cover": "/img/products/ear-tws.svg",
        "featured": True,
        "skus": [("EAR-TWS", "白色", "249.00", 110), ("EAR-TWS-B", "黑色", "249.00", 95)],
    },
    {
        "name": "开放式运动耳机",
        "subtitle": "不入耳，跑步能听见环境音",
        "description": "骨传导不入耳，跑步时能听见车和环境音，安全性比入耳高。IPX6 防水，出汗淋雨都不怕。",
        "category": H,
        "cover": "/img/products/ear-open.svg",
        "skus": [("EAR-OPEN", "黑色", "459.00", 45)],
    },
    {
        "name": "桌面 USB 会议耳麦",
        "subtitle": "双麦降噪，免驱即插即用",
        "description": "双麦克风阵列做指向收音，键盘声和风扇声会被压掉。USB 免驱，插上任何系统都能直接用。",
        "category": H,
        "cover": "/img/products/ear-usb.svg",
        "skus": [("EAR-USB", "USB-A", "289.00", 60)],
    },
    {
        "name": "便携显示器 15.6 寸",
        "subtitle": "1080p IPS，Type-C 供电",
        "description": "一根 Type-C 同时供电和传画面，出门带一根线就够。重量 780g，能塞进 15 寸电脑包。",
        "category": N,
        "cover": "/img/products/mon-156.svg",
        "featured": True,
        "skus": [("MON-156", "标配", "799.00", 25)],
    },
    {
        "name": "27 寸 2K 显示器",
        "subtitle": "75Hz IPS，可升降底座",
        "description": "2560×1440 分辨率，27 寸上字比 1080p 锐利很多。底座支持升降旋转，竖屏不用另买支架。",
        "category": N,
        "cover": "/img/products/mon-27.svg",
        "featured": True,
        "skus": [("MON-27-2K", "2K 75Hz", "1099.00", 18)],
    },
    {
        "name": "24 寸 1080p 办公显示器",
        "subtitle": "低蓝光不闪屏，副屏够用",
        "description": "24 寸 1080p，做副屏看文档和聊天窗口足够。低蓝光加不闪屏，看一整天眼睛不那么干。",
        "category": N,
        "cover": "/img/products/mon-24.svg",
        "skus": [("MON-24", "标配", "649.00", 30)],
    },
    {
        "name": "34 寸带鱼屏显示器",
        "subtitle": "21:9 曲面，等于并排两块屏",
        "description": "3440×1440 分辨率，宽度相当于两块 27 寸并排，剪辑时间线不用来回滚。曲面贴合视线。",
        "category": N,
        "cover": "/img/products/mon-34.svg",
        "skus": [("MON-34-UW", "曲面 144Hz", "2299.00", 10)],
    },
    {
        "name": "便携副屏 14 寸",
        "subtitle": "磁吸贴笔记本背面",
        "description": "14 寸 1080p，磁吸贴在笔记本背面，合盖也能带走。开会演示时翻过来给对方看。",
        "category": N,
        "cover": "/img/products/mon-14.svg",
        "skus": [("MON-14", "标配", "599.00", 22)],
    },
    {
        "name": "桌面显示器支架",
        "subtitle": "单臂气压，17-32 寸",
        "description": "气压弹簧单臂，17 到 32 寸都能撑住。夹桌安装不用打孔，桌面腾出来的空间能放键盘。",
        "category": S,
        "cover": "/img/products/arm-single.svg",
        "skus": [("ARM-S1", "单臂", "259.00", 45)],
    },
    {
        "name": "双屏显示器支架",
        "subtitle": "双臂独立，横竖可调",
        "description": "两臂独立调节，可以一横一竖摆，也能拼成一块大画布。每臂承重 9kg，两块 27 寸也稳。",
        "category": S,
        "cover": "/img/products/arm-dual.svg",
        "skus": [("ARM-D2", "双臂", "429.00", 28)],
    },
    {
        "name": "笔记本立式支架",
        "subtitle": "铝合金，合盖竖放",
        "description": "合盖竖放省桌面，铝合金导热还能帮着散一点热。硅胶垫不刮机身，15 到 25mm 厚都夹得住。",
        "category": S,
        "cover": "/img/products/stand-nb.svg",
        "skus": [("STAND-NB", "银色", "89.00", 140)],
    },
    {
        "name": "显示器增高架",
        "subtitle": "抬高 10cm，底下能收纳",
        "description": "把屏幕抬高 10cm 让视线平齐，脖子不用往前伸。架子底下放得下键盘和鼠标。",
        "category": S,
        "cover": "/img/products/stand-riser.svg",
        "skus": [("STAND-RISER", "原木色", "129.00", 85)],
    },
    {
        "name": "气压悬臂支架",
        "subtitle": "承重 12kg，六轴可调",
        "description": "六轴关节，屏幕能拉到床边或沙发旁躺着看。承重 12kg，大屏和一体机都撑得住。",
        "category": S,
        "cover": "/img/products/arm-gas.svg",
        "skus": [("ARM-GAS", "长臂款", "699.00", 15)],
    },
    {
        "name": "USB-C 扩展坞",
        "subtitle": "七合一，带 HDMI",
        "description": "七合一：HDMI、三个 USB-A、SD 卡、TF 卡和 100W 供电。笔记本只有一个口也能接显示器。",
        "category": D,
        "cover": "/img/products/dock-7in1.svg",
        "featured": True,
        "skus": [("DOCK-7IN1", "七合一", "219.00", 70)],
    },
    {
        "name": "雷电 4 扩展坞",
        "subtitle": "双 4K 输出，96W 反向供电",
        "description": "雷电 4 接口能同时驱动两台 4K 60Hz。96W 反向供电，一根线充电、传数据、出画面。",
        "category": D,
        "cover": "/img/products/dock-tb4.svg",
        "featured": True,
        "skus": [("DOCK-TB4", "雷电 4", "1299.00", 9)],
    },
    {
        "name": "六合一便携扩展坞",
        "subtitle": "口袋大小，出差带",
        "description": "六合一，机身只有打火机大小。出差塞进电脑包侧袋，酒店里接电视放片也够用。",
        "category": D,
        "cover": "/img/products/dock-6in1.svg",
        "skus": [("DOCK-6IN1", "六合一", "149.00", 130)],
    },
    {
        "name": "USB-C 多口充电器",
        "subtitle": "100W 三口，一充顶三个",
        "description": "100W 三口输出，笔记本、手机、耳机一起充。氮化镓方案，体积比同功率老充电器小一半。",
        "category": D,
        "cover": "/img/products/dock-charger.svg",
        "skus": [("CHG-100W", "100W 三口", "299.00", 75)],
    },
    {
        "name": "千兆网卡转换器",
        "subtitle": "USB 转 RJ45，免驱",
        "description": "USB 转千兆网口，会议室和酒店只有网线时救急用。免驱，Windows、macOS、Linux 插上就认。",
        "category": D,
        "cover": "/img/products/dock-net.svg",
        "skus": [("NET-GBE", "千兆", "79.00", 160)],
    },
]

COUPONS = [
    ("满 199 减 30", "199.00", "30.00", 100),
    ("满 99 减 10", "99.00", "10.00", 200),
    ("新客满 49 减 5", "49.00", "5.00", 50),
]


class Command(BaseCommand):
    help = "写入演示商品、SKU 与券（幂等，不覆盖已存在的数据）"

    @transaction.atomic
    def handle(self, *args, **options):
        created_products = 0
        filled_products = 0
        created_skus = 0
        created_coupons = 0

        for entry in CATALOG:
            product, product_created = Product.objects.get_or_create(
                name=entry["name"],
                defaults={
                    "subtitle": entry["subtitle"],
                    "description": entry["description"],
                    "category": entry["category"],
                    "cover": entry["cover"],
                    "is_featured": entry.get("featured", False),
                },
            )
            created_products += int(product_created)

            if not product_created:
                # 分类与封面是结构信息，缺了补上；已有的值不覆盖，admin 改过的保持原样。
                missing = {
                    field: entry[field] for field in ("category", "cover") if not getattr(product, field)
                }
                if missing:
                    Product.objects.filter(pk=product.pk).update(**missing)
                    filled_products += 1

            for sku_code, title, price, stock in entry["skus"]:
                _, sku_created = SKU.objects.get_or_create(
                    sku_code=sku_code,
                    defaults={
                        "product": product,
                        "title": title,
                        "price": Decimal(price),
                        "stock": stock,
                    },
                )
                created_skus += int(sku_created)

        now = timezone.now()
        for name, threshold, discount, total_qty in COUPONS:
            _, coupon_created = Coupon.objects.get_or_create(
                name=name,
                defaults={
                    "threshold_amount": Decimal(threshold),
                    "discount_amount": Decimal(discount),
                    "total_qty": total_qty,
                    "start_at": now - timedelta(days=1),
                    "end_at": now + timedelta(days=30),
                },
            )
            created_coupons += int(coupon_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"新增商品 {created_products} 个、补齐分类/封面 {filled_products} 个、"
                f"SKU {created_skus} 个、券 {created_coupons} 张；"
                f"当前商品 {Product.objects.count()} 个、SKU {SKU.objects.count()} 个、"
                f"券 {Coupon.objects.count()} 张"
            )
        )
        self._report_categories()

    def _report_categories(self):
        total = Product.objects.count()
        keys = [value for value, _ in Product.Category.choices]
        unknown = Product.objects.exclude(category__in=keys).count()
        if unknown:
            self.stdout.write(self.style.WARNING(f"有 {unknown} 个商品没有分类，首页分类入口会漏掉它们"))
        for value, label in Product.Category.choices:
            self.stdout.write(f"  {label}: {Product.objects.filter(category=value).count()} 个")
        featured = Product.objects.filter(is_featured=True).count()
        if featured < 8:
            self.stdout.write(self.style.WARNING(f"热销只有 {featured} 个，首页热销位会不满 8 个"))
        if total != 30:
            self.stdout.write(self.style.WARNING(f"商品总数是 {total}，与计划的 30 个不一致"))
