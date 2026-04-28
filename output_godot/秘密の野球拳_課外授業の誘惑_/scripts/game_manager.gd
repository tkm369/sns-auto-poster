extends Node

# ── シグナル ──────────────────────────────────────────────────────────
signal arousal_changed(value: float)
signal state_changed(new_state: int)
signal strip_performed(new_state: int)
signal h_scene_triggered(scene_id: int)
signal reaction_popup(text: String)

# ── 定数 ──────────────────────────────────────────────────────────────
const MAX_AROUSAL        := 100.0
const STRIP_THRESHOLD    := 70.0
const AROUSAL_DROP_STRIP := 25.0
const MAX_STATE          := 6

# ── 変数 ──────────────────────────────────────────────────────────────
var arousal:        float = 0.0
var clothing_state: int   = 0
var h_scene_index:  int   = 0

# ── アクション定義 ────────────────────────────────────────────────────
const ACTIONS := {
	"head":  {"gain": 8.0,  "min_state": 0},   # 頭・髪
	"face":  {"gain": 10.0, "min_state": 0},   # 顔・頬
	"chest": {"gain": 18.0, "min_state": 0},   # 胸（最初から触れる）
	"waist": {"gain": 12.0, "min_state": 0},   # 腰・スカート（最初から触れる）
	"kiss":  {"gain": 22.0, "min_state": 0},   # キス
}

# ── セリフ（フェーズ 0/1/2 × ゾーン） ────────────────────────────────
const LINES := {
	"head": [
		["ん…♡", "くすぐったい…", "やさしいのね…"],
		["はぁ…♡", "もっと…触って…", "気持ちいい…"],
		["あぁ…♡", "止まらないで…", "全部あなたのもの…"],
	],
	"face": [
		["あっ…", "恥ずかしい…♡", "ドキドキする…"],
		["んっ…♡", "熱くなって…", "顔が赤い…？"],
		["はぁっ…♡", "我慢できない…", "もっと…感じてる…"],
	],
	"chest": [
		["ひゃっ！", "だめ…そこは…！", "やさしく…"],
		["あぁッ…！", "胸が…溶けちゃう…♡", "もっと…触って…"],
		["ンッ…♡", "全部あなたのもの…♡", "大好き…♡"],
	],
	"waist": [
		["やだ！見ないで！", "恥ずかしい…下着が…", "もう…///"],
		["あっ…ダメ…！", "そこ…見られたら…♡", "意地悪…♡"],
		["あぁ…もう好きにして…♡", "全部見せてあげる…", "恥ずかしい…でも嬉しい…♡"],
	],
	"kiss": [
		["んっ…♡", "じゅる…♡", "もっと…♡"],
		["はぁ…♡", "舌を…絡めて…", "とろけちゃいそう…♡"],
		["ふぁ…♡ もう限界…", "ずっとキスしてて…♡", "全部感じてる…♡"],
	],
	"strip": [
		["やだ…脱いじゃうの…？", "あっ…こんな格好で…", "見ないで…！！"],
		["あぁ…恥ずかしい…", "脱がされちゃう…", "ドキドキする…"],
		["全部見られちゃった…", "もう…隠せない…♡", "あなたのものにして…♡"],
	],
}

func _ready() -> void:
	reset()

func reset() -> void:
	arousal        = 0.0
	clothing_state = 0
	h_scene_index  = 0
	arousal_changed.emit(arousal)
	state_changed.emit(clothing_state)

func get_ratio() -> float:
	return arousal / MAX_AROUSAL

func can_strip() -> bool:
	return arousal >= STRIP_THRESHOLD and clothing_state < MAX_STATE

func can_do(zone: String) -> bool:
	return ACTIONS.has(zone) and clothing_state >= ACTIONS[zone]["min_state"]

func touch(zone: String) -> void:
	if not can_do(zone):
		return
	var gain: float = ACTIONS[zone]["gain"] * (1.0 + clothing_state * 0.18)
	arousal = minf(arousal + gain, MAX_AROUSAL)
	arousal_changed.emit(arousal)
	reaction_popup.emit(_line(zone))
	_check_h()

func strip() -> void:
	if not can_strip():
		return
	clothing_state += 1
	arousal = maxf(0.0, arousal - AROUSAL_DROP_STRIP)
	state_changed.emit(clothing_state)
	strip_performed.emit(clothing_state)
	arousal_changed.emit(arousal)
	reaction_popup.emit(_line("strip"))
	if clothing_state >= MAX_STATE:
		_check_h()

func _check_h() -> void:
	if clothing_state >= MAX_STATE and arousal >= MAX_AROUSAL:
		h_scene_triggered.emit(h_scene_index)
		h_scene_index = mini(h_scene_index + 1, 1)
		arousal = 15.0
		arousal_changed.emit(arousal)

func _line(zone: String) -> String:
	if not LINES.has(zone): return ""
	var phase := clampi(clothing_state / 2, 0, 2)
	var arr: Array = LINES[zone][phase]
	return arr[randi() % arr.size()]
