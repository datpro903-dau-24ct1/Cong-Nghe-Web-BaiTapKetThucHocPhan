from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from io import BytesIO
import json
from pathlib import Path
import ssl
import urllib.parse
import urllib.request

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from django.db import transaction
from PIL import Image

from catalog import services
from catalog.models import Brand, Category, Product, Series


LOCAL_IMAGE_DIR = Path(r"c:\Users\ADMIN\OneDrive\Hình ảnh\HinhShop")

# 6 sản phẩm lấy trực tiếp từ thư mục HinhShop của máy
LOCAL_PRODUCTS = [
    (
        "Mô hình Jujutsu Kaisen - Satoru Gojo Hollow Purple Ver.",
        "Scale Figure",
        "Jujutsu Kaisen",
        "Kotobukiya",
        Decimal("3450000"),
        12,
        True,
        "1/7",
        "PVC & ABS",
        "26cm",
        ["Gojo Satoru.jpg"],
    ),
    (
        "Nendoroid Spy x Family - Anya Forger Casual Outfit Ver.",
        "Nendoroid",
        "Spy x Family",
        "Good Smile Company",
        Decimal("1150000"),
        25,
        True,
        "Non-scale",
        "ABS & PVC",
        "10cm",
        [
            "good-smile-company-nendoroid-anya-forger-casual-outfit-ver-figure-spy-x-family__49069.jpg",
            "good-smile-company-nendoroid-anya-forger-casual-outfit-ver-figure-spy-x-family__50060.webp",
        ],
    ),
    (
        "Mô hình Jujutsu Kaisen - Yuji Itadori Black Flash Battle Ver.",
        "SH Figuarts",
        "Jujutsu Kaisen",
        "Bandai",
        Decimal("1490000"),
        18,
        True,
        "1/12",
        "PVC & ABS",
        "15cm",
        ["itadori.jpg", "itadori2.jpg", "itadori3.jpg"],
    ),
    (
        "Mô hình Naruto Shippuden - Naruto Uzumaki Kurama Link Mode",
        "Prize Figure",
        "Naruto",
        "Banpresto",
        Decimal("790000"),
        22,
        True,
        "Non-scale",
        "PVC",
        "22cm",
        [
            "mo-hinh-naruto-shippuden-figure-kurama-kurama-link-mode-banpresto-bandai-2_925417_6a35085ac6e0c8.52903040.webp"
        ],
    ),
    (
        "Nendoroid Jujutsu Kaisen - Megumi Fushiguro (#1406)",
        "Nendoroid",
        "Jujutsu Kaisen",
        "Good Smile Company",
        Decimal("1190000"),
        20,
        False,
        "Non-scale",
        "ABS & PVC",
        "10cm",
        [
            "sogestore_Nendoroid-Megumi-Fushiguro-1.webp",
            "sogestore_Nendoroid-Megumi-Fushiguro-3.webp",
        ],
    ),
    (
        "Nendoroid Chainsaw Man - Power & Nyako (#1580)",
        "Nendoroid",
        "Chainsaw Man",
        "Good Smile Company",
        Decimal("1250000"),
        16,
        True,
        "Non-scale",
        "ABS & PVC",
        "10cm",
        [
            "152422753_246791776992021_2520026736163511522_n.jpg",
            "154570643_246791766992022_7918051224246404850_n.jpg",
        ],
    ),
]

# 44 sản phẩm tải ảnh thật từ hệ thống cửa hàng figure Nhật Bản (Animota / JumpIchiban)
REMOTE_PRODUCTS = [
    # One Piece (7)
    ("S.H.Figuarts One Piece - Monkey D. Luffy Gear 5", "SH Figuarts", "One piece", "Bandai", Decimal("1850000"), 15, True, "1/12", "PVC & ABS", "15.5cm", "Luffy Gear 5 figure"),
    ("Portrait.Of.Pirates One Piece - Roronoa Zoro King of Hell", "Scale Figure", "One piece", "MegaHouse", Decimal("4500000"), 8, True, "1/8", "PVC & ABS", "24cm", "Roronoa Zoro figure"),
    ("Mô hình One Piece Battle Record Collection - Vinsmoke Sanji", "Prize Figure", "One piece", "Banpresto", Decimal("550000"), 30, False, "Non-scale", "PVC", "19cm", "Sanji One Piece figure"),
    ("Mô hình One Piece King of Artist - Trafalgar Law Wano Ver.", "Prize Figure", "One piece", "Banpresto", Decimal("650000"), 20, False, "Non-scale", "PVC", "23cm", "Trafalgar Law figure"),
    ("S.H.Figuarts One Piece - Portgas D. Ace Fire Fist", "SH Figuarts", "One piece", "Bandai", Decimal("1650000"), 14, False, "1/12", "PVC & ABS", "15cm", "Portgas D Ace figure"),
    ("Mô hình One Piece DXF The Grandline Series - Shanks", "Prize Figure", "One piece", "Banpresto", Decimal("620000"), 18, False, "Non-scale", "PVC", "17cm", "Shanks One Piece figure"),
    ("Mô hình One Piece Glitter & Glamours - Boa Hancock", "Prize Figure", "One piece", "Banpresto", Decimal("590000"), 24, False, "Non-scale", "PVC", "25cm", "Boa Hancock figure"),

    # Jujutsu Kaisen (4)
    ("ARTFX J Jujutsu Kaisen - Yuta Okkotsu 1/8 Scale", "Scale Figure", "Jujutsu Kaisen", "Kotobukiya", Decimal("3250000"), 9, True, "1/8", "PVC & ABS", "21cm", "Yuta Okkotsu figure"),
    ("Figma Jujutsu Kaisen - Nobara Kugisaki", "Figma", "Jujutsu Kaisen", "Max Factory", Decimal("1690000"), 12, False, "1/12", "ABS & PVC", "14cm", "Nobara Kugisaki figure"),
    ("Mô hình Jujutsu Kaisen King of Artist - Toji Fushiguro", "Prize Figure", "Jujutsu Kaisen", "Banpresto", Decimal("680000"), 25, False, "Non-scale", "PVC", "22cm", "Toji Fushiguro figure"),
    ("Mô hình Jujutsu Kaisen Jukon no Kata - Suguru Geto", "Prize Figure", "Jujutsu Kaisen", "Banpresto", Decimal("640000"), 19, False, "Non-scale", "PVC", "18cm", "Suguru Geto figure"),

    # Demon Slayer (6)
    ("ARTFX J Demon Slayer - Tanjiro Kamado Hinokami Kagura", "Scale Figure", "Demon Slayer", "Kotobukiya", Decimal("3200000"), 10, True, "1/8", "PVC & ABS", "21cm", "Tanjiro Kamado figure"),
    ("Nendoroid Demon Slayer - Nezuko Kamado Blood Demon Art Ver.", "Nendoroid", "Demon Slayer", "Good Smile Company", Decimal("1190000"), 22, False, "Non-scale", "ABS & PVC", "10cm", "Nezuko Kamado figure"),
    ("Figma Demon Slayer - Zenitsu Agatsuma DX Edition", "Figma", "Demon Slayer", "Max Factory", Decimal("1950000"), 11, False, "1/12", "ABS & PVC", "13.5cm", "Zenitsu Agatsuma figure"),
    ("S.H.Figuarts Demon Slayer - Kyojuro Rengoku Flame Hashira", "SH Figuarts", "Demon Slayer", "Bandai", Decimal("1690000"), 13, True, "1/12", "PVC & ABS", "15cm", "Kyojuro Rengoku figure"),
    ("S.H.Figuarts Demon Slayer - Shinobu Kocho Insect Hashira", "SH Figuarts", "Demon Slayer", "Bandai", Decimal("1620000"), 15, False, "1/12", "PVC & ABS", "14cm", "Shinobu Kocho figure"),
    ("Mô hình Demon Slayer Vibration Stars - Tengen Uzui", "Prize Figure", "Demon Slayer", "Banpresto", Decimal("620000"), 20, False, "Non-scale", "PVC", "18cm", "Tengen Uzui figure"),

    # Naruto (4)
    ("S.H.Figuarts Naruto Shippuden - Sasuke Uchiha Susanoo Ver.", "SH Figuarts", "Naruto", "Bandai", Decimal("1550000"), 14, False, "1/12", "PVC & ABS", "14.5cm", "Sasuke Uchiha figure"),
    ("Precious G.E.M. Series Naruto Shippuden - Itachi Uchiha Susanoo", "Scale Figure", "Naruto", "MegaHouse", Decimal("5400000"), 5, True, "Non-scale", "PVC & ABS", "38cm", "Itachi Uchiha figure"),
    ("Mô hình Naruto Shippuden Vibration Stars - Kakashi Hatake", "Prize Figure", "Naruto", "Banpresto", Decimal("610000"), 26, False, "Non-scale", "PVC", "18cm", "Kakashi Hatake figure"),
    ("Mô hình Naruto Shippuden Panel Spectacle - Minato Namikaze", "Prize Figure", "Naruto", "Banpresto", Decimal("690000"), 18, False, "Non-scale", "PVC", "20cm", "Minato Namikaze figure"),

    # Dragon Ball (5)
    ("S.H.Figuarts Dragon Ball Super - Vegeta Super Saiyan Blue", "SH Figuarts", "DraggonBall", "Bandai", Decimal("1350000"), 16, False, "1/12", "PVC & ABS", "14cm", "Vegeta figure"),
    ("Mô hình Dragon Ball Super Blood of Saiyans - Son Gohan Beast", "Prize Figure", "DraggonBall", "Banpresto", Decimal("680000"), 22, True, "Non-scale", "PVC", "20cm", "Son Gohan Beast figure"),
    ("Mô hình Dragon Ball Super Clearise - Broly Full Power", "Prize Figure", "DraggonBall", "Banpresto", Decimal("750000"), 15, False, "Non-scale", "PVC", "23cm", "Broly Dragon Ball figure"),
    ("S.H.Figuarts Dragon Ball Z - Future Trunks Boy From The Future", "SH Figuarts", "DraggonBall", "Bandai", Decimal("1580000"), 12, False, "1/12", "PVC & ABS", "14cm", "Trunks Dragon Ball figure"),
    ("S.H.Figuarts Dragon Ball Z - Frieza Fourth Form Final Battle", "SH Figuarts", "DraggonBall", "Bandai", Decimal("1290000"), 17, False, "1/12", "PVC & ABS", "12.5cm", "Frieza Dragon Ball figure"),

    # Attack on Titan (3)
    ("ARTFX J Attack on Titan - Levi Ackerman Fortitude Ver. 1/7", "Scale Figure", "Attack On Titan", "Kotobukiya", Decimal("3650000"), 7, True, "1/7", "PVC & ABS", "17cm", "Levi Attack on Titan figure"),
    ("Pop Up Parade Attack on Titan - Eren Yeager Attack Titan Ver.", "Prize Figure", "Attack On Titan", "Good Smile Company", Decimal("1050000"), 20, False, "Non-scale", "ABS & PVC", "17cm", "Eren Yeager figure"),
    ("Figma Attack on Titan - Mikasa Ackerman Final Season Ver.", "Figma", "Attack On Titan", "Max Factory", Decimal("1890000"), 10, False, "1/12", "ABS & PVC", "14.5cm", "Mikasa Ackerman figure"),

    # Chainsaw Man (3)
    ("Revoltech Amazing Yamaguchi - Chainsaw Man Denji Hybrid", "Revoltech", "Chainsaw Man", "Kotobukiya", Decimal("2250000"), 9, True, "1/12", "PVC & ABS & POM", "16cm", "Chainsaw Man Denji figure"),
    ("ARTFX J Chainsaw Man - Makima 1/8 Scale Figure", "Scale Figure", "Chainsaw Man", "Kotobukiya", Decimal("3150000"), 11, False, "1/8", "PVC & ABS", "22.5cm", "Makima Chainsaw Man figure"),
    ("Mô hình Chainsaw Man Vibration Stars - Aki Hayakawa", "Prize Figure", "Chainsaw Man", "Banpresto", Decimal("630000"), 21, False, "Non-scale", "PVC", "18cm", "Aki Hayakawa figure"),

    # Mobile Suit Gundam (4)
    ("Model Kit MGEX 1/100 Strike Freedom Gundam Ver.Ka", "Model Kit", "Mobile Suit Gundam", "Bandai", Decimal("3890000"), 6, True, "1/100", "PS & ABS & PE", "19cm", "Strike Freedom Gundam"),
    ("Model Kit RG 1/144 RX-93-v2 Hi-Nu Gundam", "Model Kit", "Mobile Suit Gundam", "Bandai", Decimal("1390000"), 15, False, "1/144", "PS & ABS", "15cm", "Hi-Nu Gundam"),
    ("Model Kit HG 1/144 XVX-016 Gundam Aerial Witch from Mercury", "Model Kit", "Mobile Suit Gundam", "Bandai", Decimal("520000"), 28, False, "1/144", "PS & ABS", "13cm", "Gundam Aerial"),
    ("Model Kit MG 1/100 Gundam Barbatos Iron-Blooded Orphans", "Model Kit", "Mobile Suit Gundam", "Bandai", Decimal("1290000"), 14, False, "1/100", "PS & ABS", "18cm", "Gundam Barbatos"),

    # Spy x Family (2)
    ("S.H.Figuarts Spy x Family - Yor Forger Thorn Princess", "SH Figuarts", "Spy x Family", "Bandai", Decimal("1520000"), 16, False, "1/12", "PVC & ABS", "15cm", "Yor Forger figure"),
    ("Nendoroid Spy x Family - Loid Forger Twilight (#1701)", "Nendoroid", "Spy x Family", "Good Smile Company", Decimal("1120000"), 19, False, "Non-scale", "ABS & PVC", "10cm", "Loid Forger figure"),

    # Bleach (2)
    ("Precious G.E.M. Series Bleach - Ichigo Kurosaki Thousand-Year Blood War", "Scale Figure", "Bleach", "MegaHouse", Decimal("4100000"), 6, False, "1/8", "PVC & ABS", "25cm", "Ichigo Kurosaki figure"),
    ("Mô hình Bleach Solid and Souls - Kenpachi Zaraki", "Prize Figure", "Bleach", "Banpresto", Decimal("640000"), 18, False, "Non-scale", "PVC", "21cm", "Kenpachi Zaraki figure"),

    # Berserk (2)
    ("S.H.Figuarts Berserk - Guts Berserker Armor Unleashed", "SH Figuarts", "Berserk", "Bandai", Decimal("2190000"), 8, True, "1/12", "PVC & ABS & Fabric", "16cm", "Guts Berserk figure"),
    ("Figma Berserk - Griffith Hawk of Light Renewal Edition", "Figma", "Berserk", "Max Factory", Decimal("2050000"), 7, False, "1/12", "ABS & PVC", "15.5cm", "Griffith Berserk figure"),

    # Fate/Grand Order (2)
    ("Scale Figure Fate/Grand Order - Saber Altria Pendragon Dress Ver.", "Scale Figure", "Fate/Grand Order", "Alter", Decimal("3950000"), 7, True, "1/7", "PVC & ABS", "23cm", "Altria Pendragon figure"),
    ("Figma Fate/Grand Order - Ruler Jeanne d'Arc", "Figma", "Fate/Grand Order", "Max Factory", Decimal("1920000"), 9, False, "1/12", "ABS & PVC", "14.5cm", "Jeanne Fate figure"),
]


SSL_CTX = ssl._create_unverified_context()
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def _to_clean_jpeg_bytes(raw_bytes: bytes) -> bytes:
    with Image.open(BytesIO(raw_bytes)) as img:
        rgb = img.convert("RGB")
        if max(rgb.size) > 1000:
            rgb.thumbnail((1000, 1000), Image.Resampling.LANCZOS)
        buf = BytesIO()
        rgb.save(buf, format="JPEG", quality=88)
        return buf.getvalue()


def _search_store_images(domain: str, query: str) -> list[str]:
    url = (
        f"https://{domain}/search/suggest.json?"
        f"q={urllib.parse.quote(query)}&resources[type]=product&resources[limit]=10"
    )
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=12, context=SSL_CTX) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    products = data.get("resources", {}).get("results", {}).get("products", [])
    urls = []
    for p in products:
        img_url = p.get("image") or p.get("featured_image", {}).get("url")
        if img_url:
            if img_url.startswith("//"):
                img_url = "https:" + img_url
            urls.append(img_url)
    return urls


def _download_bytes(url: str) -> bytes:
    sep = "&" if "?" in url else "?"
    fast_url = f"{url}{sep}width=800" if "cdn.shopify.com" in url else url
    req = urllib.request.Request(fast_url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15, context=SSL_CTX) as resp:
        return _to_clean_jpeg_bytes(resp.read())


class Command(BaseCommand):
    help = "Xoa cac san pham generate cu (giu 3 san pham goc id 1..3) va seed 50 san pham kem anh that."

    def handle(self, *args, **options):
        # 1. Xoa cac san pham generate cu, giu nguyen 3 san pham goc (id 1, 2, 3)
        deleted_count, _ = Product.objects.exclude(id__in=[1, 2, 3]).delete()
        self.stdout.write(f"Deleted old generated products: {deleted_count}")

        # 2. Dam bao day du Category, Series, Brand
        categories = {}
        for name in ["Scale Figure", "Nendoroid", "Figma", "SH Figuarts", "Revoltech", "Prize Figure", "Model Kit"]:
            cat = Category.objects.filter(name__iexact=name).first()
            if not cat:
                cat = services.create_category(name=name)
            categories[name] = cat

        series_map = {}
        for name in [
            "One piece", "Jujutsu Kaisen", "Attack On Titan", "Naruto", "DraggonBall",
            "Demon Slayer", "Chainsaw Man", "Mobile Suit Gundam", "Spy x Family",
            "Bleach", "Berserk", "Fate/Grand Order",
        ]:
            ser = Series.objects.filter(name__iexact=name).first()
            if not ser:
                ser = services.create_series(name=name)
            series_map[name] = ser

        brands = {}
        for name in ["Good Smile Company", "Kotobukiya", "Bandai", "Banpresto", "Max Factory", "MegaHouse", "Alter"]:
            br = Brand.objects.filter(name__iexact=name).first()
            if not br:
                br = services.create_brand(name=name)
            brands[name] = br

        created_count = 0

        # 3. Tao 6 san pham tu anh co san trong thu muc HinhShop
        for name, cat_name, ser_name, br_name, price, stock, _feat, scale, mat, height, filenames in LOCAL_PRODUCTS:
            height_val = Decimal(height.replace("cm", "").strip())
            with transaction.atomic():
                product = services.create_product(
                    name=name,
                    category=categories[cat_name],
                    series=series_map[ser_name],
                    brand=brands[br_name],
                    price=price,
                    stock=stock,
                    scale=scale,
                    material=mat,
                    height_cm=height_val,
                    description=(
                        f"{name} thuộc dòng {cat_name} từ bộ {ser_name}, "
                        f"sản xuất chính hãng bởi {br_name} với chất liệu {mat} sắc nét."
                    ),
                )
                for idx, fname in enumerate(filenames):
                    fpath = LOCAL_IMAGE_DIR / fname
                    if fpath.exists():
                        clean_bytes = _to_clean_jpeg_bytes(fpath.read_bytes())
                        upload = SimpleUploadedFile(
                            name=f"{product.slug}-{idx + 1}.jpg",
                            content=clean_bytes,
                            content_type="image/jpeg",
                        )
                        services.add_product_image(product=product, image=upload, is_main=(idx == 0))
                created_count += 1

        self.stdout.write(f"Created {created_count} local-image products.")

        # 4. Tim URL anh that cho 44 san pham con lai song song
        def resolve_candidate_urls(item):
            query = item[10]
            urls = []
            for domain in ("animota.net", "jumpichiban.com"):
                try:
                    urls.extend(_search_store_images(domain, query))
                    if len(urls) >= 5:
                        break
                except Exception:
                    continue
            if not urls:
                # Fallback search by series + figure
                fallback_q = f"{item[2]} figure"
                for domain in ("animota.net", "jumpichiban.com"):
                    try:
                        urls.extend(_search_store_images(domain, fallback_q))
                    except Exception:
                        continue
            return urls

        with ThreadPoolExecutor(max_workers=8) as pool:
            candidate_lists = list(pool.map(resolve_candidate_urls, REMOTE_PRODUCTS))

        used_urls = set()
        chosen_urls = []
        for candidates in candidate_lists:
            picked = None
            for u in candidates:
                base_u = u.split("?")[0]
                if base_u not in used_urls:
                    used_urls.add(base_u)
                    picked = u
                    break
            if not picked and candidates:
                picked = candidates[0]
            chosen_urls.append(picked)

        # Tai anh song song
        def fetch_image_for_index(idx_and_url):
            idx, url = idx_and_url
            if not url:
                return idx, None
            try:
                return idx, _download_bytes(url)
            except Exception:
                return idx, None

        with ThreadPoolExecutor(max_workers=8) as pool:
            downloaded = dict(pool.map(fetch_image_for_index, enumerate(chosen_urls)))

        # Backup bytes tu anh HinhShop neu 1 URL bi timeout dot xuat
        fallback_bytes = _to_clean_jpeg_bytes((LOCAL_IMAGE_DIR / "Gojo Satoru.jpg").read_bytes())

        for idx, (name, cat_name, ser_name, br_name, price, stock, _feat, scale, mat, height, _q) in enumerate(REMOTE_PRODUCTS):
            img_bytes = downloaded.get(idx) or fallback_bytes
            height_val = Decimal(height.replace("cm", "").strip())
            with transaction.atomic():
                product = services.create_product(
                    name=name,
                    category=categories[cat_name],
                    series=series_map[ser_name],
                    brand=brands[br_name],
                    price=price,
                    stock=stock,
                    scale=scale,
                    material=mat,
                    height_cm=height_val,
                    description=(
                        f"{name} thuộc dòng {cat_name} từ bộ {ser_name}, "
                        f"sản xuất chính hãng bởi {br_name} với độ chi tiết cao ({height}, {mat})."
                    ),
                )
                upload = SimpleUploadedFile(
                    name=f"{product.slug}.jpg",
                    content=img_bytes,
                    content_type="image/jpeg",
                )
                services.add_product_image(product=product, image=upload, is_main=True)
                created_count += 1

        total = Product.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Done! Created {created_count} new products with real photos. Total products in DB: {total}."
            )
        )
