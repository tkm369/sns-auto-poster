# エロゲ特化プリセット定義
# 全コンテンツR18前提

GENRES = {
    "1": {
        "name": "学園・青春",
        "setting": "現代日本の高校・大学",
        "atmosphere": "青春・甘エロ",
        "bg_examples": "教室、屋上、図書室、部室、体育倉庫、保健室",
    },
    "2": {
        "name": "異世界ファンタジー",
        "setting": "剣と魔法の異世界王国",
        "atmosphere": "冒険・ハーレム・魔法",
        "bg_examples": "王宮、森の隠れ家、宿屋の寝室、魔法使いの塔、ダンジョン",
    },
    "3": {
        "name": "現代・日常",
        "setting": "現代日本のアパート・都市",
        "atmosphere": "ほのぼの・同棲・日常エロ",
        "bg_examples": "アパートの寝室、バスルーム、キッチン、カフェ、公園の夜",
    },
    "4": {
        "name": "SF・近未来",
        "setting": "近未来の宇宙ステーション・AI社会",
        "atmosphere": "SF・近未来・アンドロイド",
        "bg_examples": "宇宙船の個室、研究施設、サイバーシティ、実験室",
    },
    "5": {
        "name": "和風・時代劇",
        "setting": "江戸〜明治時代の日本",
        "atmosphere": "和風・艶やか・花魁",
        "bg_examples": "遊郭、武家屋敷、温泉宿、桜の庭、月夜の縁側",
    },
    "6": {
        "name": "ダーク・ホラー",
        "setting": "廃墟・呪われた洋館・異界",
        "atmosphere": "ダーク・催眠・支配",
        "bg_examples": "廃洋館の寝室、地下室、霧の森、古い神社",
    },
    "7": {
        "name": "職場・社会人",
        "setting": "現代日本のオフィス・会社",
        "atmosphere": "社内恋愛・上司部下・不倫",
        "bg_examples": "残業中のオフィス、会議室、社内トイレ、出張ホテル",
    },
    "8": {
        "name": "異種族・モンスター娘",
        "setting": "人間と亜人が共存する世界",
        "atmosphere": "異種族交流・ファンタジーエロ",
        "bg_examples": "異種族の里、洞窟、神殿、湖畔",
    },
}

# シナリオ形式（旧FORMATS）
SCENARIOS = {
    "1": {
        "name": "純愛",
        "description": "一人のヒロインと真剣に向き合う純粋な恋愛。甘くて切ない展開。",
        "heroine_count": 1,
        "h_intensity": "甘め",
    },
    "2": {
        "name": "ハーレム",
        "description": "複数のヒロインが主人公を慕う。賑やかで幸福な展開。全員攻略可能。",
        "heroine_count": 3,
        "h_intensity": "中程度",
    },
    "3": {
        "name": "百合（GL）",
        "description": "女性主人公と女性ヒロインの濃密な関係。女性同士の絡みが中心。",
        "heroine_count": 2,
        "h_intensity": "中程度",
    },
    "4": {
        "name": "NTR（寝取られ）",
        "description": "大切な人を寝取られる絶望と興奮。主人公視点での屈辱・快楽展開。",
        "heroine_count": 1,
        "h_intensity": "濃厚",
    },
    "5": {
        "name": "調教・支配",
        "description": "主人公がヒロインを調教・支配する展開。服従・快楽堕ちがメイン。",
        "heroine_count": 2,
        "h_intensity": "濃厚",
    },
    "6": {
        "name": "逆調教・雌堕ち",
        "description": "強気なヒロインが徐々に快楽に溺れて堕ちていく過程を描く。",
        "heroine_count": 1,
        "h_intensity": "濃厚",
    },
    "7": {
        "name": "催眠・洗脳",
        "description": "催眠や魔法でヒロインの心を操る展開。段階的な変化が見どころ。",
        "heroine_count": 2,
        "h_intensity": "濃厚",
    },
    "8": {
        "name": "寝取り（NTS）",
        "description": "主人公が他の男性のヒロインを寝取る展開。禁断の快楽がテーマ。",
        "heroine_count": 1,
        "h_intensity": "濃厚",
    },
}

# ヒロインの属性タイプ
HEROINE_ARCHETYPES = {
    "1":  {"name": "ツンデレ",    "description": "最初は素直になれないが実はデレデレ"},
    "2":  {"name": "幼馴染",      "description": "ずっと側にいた気の置けない存在"},
    "3":  {"name": "妹",          "description": "ブラコン気味の甘えん坊な妹"},
    "4":  {"name": "お姉さん",    "description": "包容力のある年上の女性"},
    "5":  {"name": "後輩",        "description": "慕ってくれる純粋な後輩"},
    "6":  {"name": "先生・上司",  "description": "立場はあるが内面は乙女"},
    "7":  {"name": "メイド・奴隷","description": "主人公に仕える忠実な存在"},
    "8":  {"name": "天使・神様",  "description": "神聖な存在が人間の欲望に目覚める"},
    "9":  {"name": "悪役令嬢",    "description": "高飛車だが純粋な貴族令嬢"},
    "10": {"name": "魔族・悪魔",  "description": "人間を誘惑する魔性の存在"},
    "11": {"name": "巨乳おっとり","description": "天然でふわっとした大人の女性"},
    "12": {"name": "クール美人",  "description": "無表情だが内に秘めた欲求がある"},
}

# Hシーンの内容タグ
H_TAGS = {
    "vanilla":    {"name": "バニラ（甘め）",      "description": "愛情ある優しいHシーン"},
    "intense":    {"name": "激しめ",              "description": "情熱的で激しい交わり"},
    "outdoor":    {"name": "野外・公共",          "description": "露出・野外プレイ要素"},
    "uniform":    {"name": "制服・コスプレ",      "description": "衣装フェチ要素"},
    "oral":       {"name": "口淫・奉仕",          "description": "奉仕・口淫シーン多め"},
    "toy":        {"name": "玩具・道具",          "description": "アダルトグッズ使用シーン"},
    "group":      {"name": "複数・乱交",          "description": "複数人での絡みシーン"},
    "blackmail":  {"name": "弱み・脅迫",          "description": "弱みを握られた関係性"},
    "pregnant":   {"name": "孕ませ",              "description": "孕ませ・妊娠を匂わせる展開"},
    "exhib":      {"name": "露出・命令",          "description": "命令プレイ・露出シーン"},
}

LENGTHS = {
    "1": {"name": "短編",   "scenes": 4,  "h_scenes": 2,  "description": "サクッと読める短編（Hシーン2個）"},
    "2": {"name": "中編",   "scenes": 8,  "h_scenes": 4,  "description": "読み応えのある中編（Hシーン4個）"},
    "3": {"name": "長編",   "scenes": 14, "h_scenes": 7,  "description": "ボリューム満点の長編（Hシーン7個）"},
    "4": {"name": "超長編", "scenes": 20, "h_scenes": 10, "description": "大作・フルボイス向け（Hシーン10個）"},
}

ART_STYLES = {
    "1": {
        "name": "2D（アニメ調・エロゲ王道）",
        "mode": "2d",
        "description": "萌えアニメ風立ち絵。エロゲ王道スタイル。SD/NovelAI用プロンプト生成",
        "sd_base_positive": "masterpiece, best quality, anime style, eroge cg, visual novel sprite, beautiful detailed face, perfect body",
        "sd_base_negative": "lowres, bad anatomy, bad hands, blurry, cropped, worst quality, deformed, ugly",
        "bg_style": "anime background, detailed, painterly, visual novel background",
        "expression_list": ["通常", "笑顔", "照れ", "喘ぎ", "恍惚", "泣き顔", "驚き"],
    },
    "2": {
        "name": "3D（リアル調・ゲームCG）",
        "mode": "3d",
        "description": "3Dレンダリング風。Koikatsu / VRM / DAZ3D 向けキャラ設定ファイル生成",
        "sd_base_positive": "masterpiece, best quality, 3d render, realistic, photorealistic, game cg, beautiful woman",
        "sd_base_negative": "lowres, flat color, anime, cartoon, 2d, deformed",
        "bg_style": "3d render, realistic environment, game background, unreal engine",
        "expression_list": ["neutral", "smile", "blush", "ahegao", "crying", "surprised"],
    },
}

# RPGエロゲ用設定
RPG_EROGE_SCENARIOS = {
    "defeat":   {"name": "戦闘敗北H",      "description": "敵に負けるとHシーンが発生"},
    "story":    {"name": "ストーリーH",     "description": "ストーリー進行でHシーンが解放"},
    "inn":      {"name": "宿屋・拠点H",    "description": "宿屋・拠点でヒロインとHシーン"},
    "capture":  {"name": "捕獲・調教H",    "description": "敵を捕獲して調教するシステム"},
    "all":      {"name": "全部盛り",        "description": "上記すべての要素を含む"},
}

RPG_H_INTENSITY = {
    "light":  {"name": "薄め（ストーリー重視）", "description": "Hシーンは少なめ、ストーリー優先"},
    "medium": {"name": "普通",                   "description": "ストーリーとHシーンのバランス"},
    "heavy":  {"name": "濃厚（エロ重視）",       "description": "Hシーンを多く、詳細に描写"},
}
