import re
from dataclasses import dataclass
from typing import List


@dataclass
class SubtitleEntry:
    index: int
    start_time: str
    end_time: str
    start_seconds: float
    end_seconds: float
    text: str

    def duration(self) -> float:
        return self.end_seconds - self.start_seconds


def _time_to_seconds(time_str: str) -> float:
    """HH:MM:SS,mmm または HH:MM:SS.mmm を秒に変換"""
    time_str = time_str.replace(',', '.')
    parts = time_str.split(':')
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds


def parse_srt(file_path: str) -> List[SubtitleEntry]:
    """SRTファイルを読み込んでSubtitleEntryのリストを返す"""
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()

    content = content.strip()
    entries = []
    blocks = re.split(r'\n\s*\n', content)

    for block in blocks:
        lines = [l.strip() for l in block.strip().split('\n') if l.strip()]
        if len(lines) < 3:
            continue

        try:
            index = int(lines[0])
        except ValueError:
            continue

        time_match = re.match(
            r'(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})',
            lines[1]
        )
        if not time_match:
            continue

        start_time = time_match.group(1)
        end_time = time_match.group(2)
        text = ' '.join(lines[2:])
        # HTMLタグを除去
        text = re.sub(r'<[^>]+>', '', text).strip()

        entries.append(SubtitleEntry(
            index=index,
            start_time=start_time,
            end_time=end_time,
            start_seconds=_time_to_seconds(start_time),
            end_seconds=_time_to_seconds(end_time),
            text=text
        ))

    return entries
