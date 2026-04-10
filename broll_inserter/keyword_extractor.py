import re
from typing import List


def _extract_simple(text: str) -> List[str]:
    """
    janomeなしのフォールバック。
    カタカナ・漢字複合語を抽出してそのまま返す。
    """
    katakana = re.findall(r'[ァ-ヺー]{2,}', text)
    kanji = re.findall(r'[一-龯]{2,}', text)
    words = katakana + kanji
    # 重複除去・短すぎるもの除去
    seen = set()
    result = []
    for w in words:
        if w not in seen and len(w) >= 2:
            seen.add(w)
            result.append(w)
    return result[:4] if result else [text[:8]]


def _extract_janome(text: str) -> List[str]:
    """janomeで名詞を抽出"""
    try:
        from janome.tokenizer import Tokenizer
        t = Tokenizer()
        keywords = []
        seen = set()
        for token in t.tokenize(text):
            pos = token.part_of_speech.split(',')[0]
            sub = token.part_of_speech.split(',')[1] if ',' in token.part_of_speech else ''
            surface = token.surface
            # 名詞かつ意味のあるもの（数字・記号は除く）
            if pos == '名詞' and sub not in ('数', '記号') and len(surface) >= 2:
                if surface not in seen:
                    seen.add(surface)
                    keywords.append(surface)
        return keywords[:5] if keywords else _extract_simple(text)
    except ImportError:
        return _extract_simple(text)


def extract_keywords(text: str) -> List[str]:
    """テキストから検索用キーワードを抽出する"""
    return _extract_janome(text)


def translate_keywords(keywords: List[str]) -> str:
    """
    日本語キーワードリストを英語の検索クエリに変換する。
    deep-translatorが入っていない場合は日本語のままにする。
    """
    joined = ' '.join(keywords)
    try:
        from deep_translator import GoogleTranslator
        result = GoogleTranslator(source='ja', target='en').translate(joined)
        return result
    except ImportError:
        # ライブラリなし → ローマ字変換なども難しいのでそのまま
        return joined
    except Exception:
        return joined


def text_to_search_query(text: str) -> str:
    """字幕テキスト1行 → Pexels検索クエリ（英語）"""
    keywords = extract_keywords(text)
    query = translate_keywords(keywords)
    return query
