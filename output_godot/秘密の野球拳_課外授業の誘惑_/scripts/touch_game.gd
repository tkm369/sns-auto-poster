extends Node2D

# ── ノード参照 ────────────────────────────────────────────────────────
@onready var character:     Node2D    = $Character
@onready var meter_fill:    ColorRect = $UI/MeterFill
@onready var meter_pct:     Label     = $UI/MeterPct
@onready var state_lbl:     Label     = $UI/StateLbl
@onready var reaction_lbl:  Label     = $UI/ReactionLbl
@onready var strip_btn:     Button    = $UI/BottomBar/StripBtn
@onready var hint_lbl:      Label     = $UI/HintLbl

# ── 定数 ──────────────────────────────────────────────────────────────
const METER_MAX_W := 706.0   # MeterBg幅（offset 15→725）
const METER_LEFT  := 15.0    # MeterBg offset_left

const STATE_NAMES := ["着衣", "セーターずれ", "胸露出", "スカート落ち", "下着のみ", "トップレス", "全裸 ♡"]

# タッチゾーン（キャラ中心からの相対Y: scale=0.38 対応）
const CHAR_CX := 640.0
const CHAR_CY := 375.0
const ZONES := {
	"head":  [-315.0, -190.0],
	"face":  [-190.0,  -62.0],
	"chest": [ -62.0,   70.0],
	"waist": [  70.0,  225.0],
}

# ── 内部状態 ──────────────────────────────────────────────────────────
var _strip_pulse_tween: Tween = null

# ── 初期化 ────────────────────────────────────────────────────────────
func _ready() -> void:
	for zone in ["head", "face", "chest", "waist", "kiss"]:
		var btn: Button = $UI/BottomBar.get_node_or_null(zone.capitalize() + "Btn") as Button
		if btn:
			var z: String = zone
			btn.pressed.connect(func(): _touch(z))

	strip_btn.pressed.connect(_strip)

	GameManager.arousal_changed.connect(_on_arousal)
	GameManager.state_changed.connect(_on_state)
	GameManager.reaction_popup.connect(_on_reaction)

	GameManager.reset()
	_style_buttons()

func _touch(zone: String) -> void:
	if not GameManager.can_do(zone): return
	GameManager.touch(zone)
	character.react_touch()
	_refresh_strip()

func _strip() -> void:
	if not GameManager.can_strip(): return
	GameManager.strip()
	_refresh_strip()

# ── シグナルハンドラ ──────────────────────────────────────────────────
func _on_arousal(v: float) -> void:
	var r := v / 100.0
	meter_fill.offset_right = METER_LEFT + METER_MAX_W * r
	var col: Color
	if r < 0.5:
		col = Color(0.25, 0.55, 1.0).lerp(Color(1.0, 0.35, 0.65), r * 2.0)
	else:
		col = Color(1.0, 0.35, 0.65).lerp(Color(1.0, 0.08, 0.15), (r - 0.5) * 2.0)
	meter_fill.color = col
	meter_pct.text   = "%d%%" % int(v)
	_refresh_strip()

func _on_state(s: int) -> void:
	state_lbl.text = STATE_NAMES[clampi(s, 0, STATE_NAMES.size() - 1)]
	_refresh_btns()

func _on_reaction(text: String) -> void:
	if text == "": return
	reaction_lbl.text     = text
	reaction_lbl.modulate = Color(1, 1, 1, 1)
	var tw := create_tween()
	tw.tween_interval(1.8)
	tw.tween_property(reaction_lbl, "modulate:a", 0.0, 0.6)

# ── UI 更新 ───────────────────────────────────────────────────────────
func _refresh_btns() -> void:
	for zone in ["head", "face", "chest", "waist", "kiss"]:
		var btn: Button = $UI/BottomBar.get_node_or_null(zone.capitalize() + "Btn") as Button
		if not btn: continue
		var ok := GameManager.can_do(zone)
		btn.disabled = not ok
		btn.modulate = Color(1, 1, 1, 1) if ok else Color(0.4, 0.4, 0.4, 0.5)
	_refresh_strip()

func _refresh_strip() -> void:
	var can := GameManager.can_strip()
	strip_btn.disabled = not can
	if can:
		hint_lbl.text     = "✨ 脱がせる！"
		hint_lbl.modulate = Color(1.0, 0.88, 0.30, 1.0)
		if _strip_pulse_tween == null:
			_strip_pulse_tween = create_tween().set_loops()
			_strip_pulse_tween.tween_property(strip_btn, "modulate",
				Color(1.0, 0.90, 0.30, 1.0), 0.38)
			_strip_pulse_tween.tween_property(strip_btn, "modulate",
				Color(1.0, 0.55, 0.72, 1.0), 0.38)
	else:
		if _strip_pulse_tween:
			_strip_pulse_tween.kill()
			_strip_pulse_tween = null
		strip_btn.modulate = Color(0.45, 0.45, 0.45, 0.55)
		var need := int(GameManager.STRIP_THRESHOLD - GameManager.arousal)
		hint_lbl.text     = "あと %d%% で脱がせる" % need if need > 0 else ""
		hint_lbl.modulate = Color(0.62, 0.62, 0.62, 1.0)

# ── キャラクターへの直接クリック ─────────────────────────────────────
func _input(event: InputEvent) -> void:
	if not (event is InputEventMouseButton): return
	var mb := event as InputEventMouseButton
	if not mb.pressed or mb.button_index != MOUSE_BUTTON_LEFT: return

	if mb.position.y > 560: return

	var rel := mb.position - Vector2(CHAR_CX, CHAR_CY)
	if abs(rel.x) > 240: return

	var zone: String = ""
	for z: String in ZONES:
		var rng: Array = ZONES[z]
		if rel.y >= rng[0] and rel.y < rng[1]:
			zone = z
			break

	if zone == "" or not GameManager.can_do(zone): return
	GameManager.touch(zone)
	character.react_touch()
	_refresh_strip()
	_heart(mb.position)

func _heart(pos: Vector2) -> void:
	var opts: Array[String] = ["♡", "💕", "✨", "♪", "💖"]
	var lbl := Label.new()
	lbl.text = opts[randi() % opts.size()]
	lbl.add_theme_font_size_override("font_size", 28)
	lbl.add_theme_color_override("font_color", Color(1, 0.55, 0.75, 1))
	lbl.position = pos + Vector2(randf_range(-24.0, 24.0) - 14.0, -18.0)
	add_child(lbl)
	var tw := create_tween()
	tw.set_parallel(true)
	tw.tween_property(lbl, "position:y", lbl.position.y - 65.0, 0.70)\
		.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tw.tween_property(lbl, "modulate:a", 0.0, 0.70)
	get_tree().create_timer(0.75).timeout.connect(lbl.queue_free)

# ── ボタンスタイリング ─────────────────────────────────────────────────
func _style_buttons() -> void:
	var names: Array[String] = [
		"HeadBtn", "FaceBtn", "ChestBtn", "WaistBtn", "KissBtn", "StripBtn"
	]
	var colors: Array[Color] = [
		Color(0.28, 0.18, 0.48),
		Color(0.44, 0.14, 0.34),
		Color(0.54, 0.10, 0.26),
		Color(0.38, 0.16, 0.42),
		Color(0.60, 0.07, 0.20),
		Color(0.52, 0.18, 0.06),
	]
	for i: int in names.size():
		var btn: Button = $UI/BottomBar.get_node_or_null(names[i]) as Button
		if btn:
			_apply_btn_style(btn, colors[i])

func _mk_sb(c: Color) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color                   = c
	sb.corner_radius_top_left     = 10
	sb.corner_radius_top_right    = 10
	sb.corner_radius_bottom_left  = 10
	sb.corner_radius_bottom_right = 10
	sb.content_margin_top         = 6.0
	sb.content_margin_bottom      = 6.0
	sb.content_margin_left        = 6.0
	sb.content_margin_right       = 6.0
	return sb

func _apply_btn_style(btn: Button, base: Color) -> void:
	btn.add_theme_stylebox_override("normal",   _mk_sb(base))
	btn.add_theme_stylebox_override("hover",    _mk_sb(base.lightened(0.28)))
	btn.add_theme_stylebox_override("pressed",  _mk_sb(base.darkened(0.22)))
	btn.add_theme_stylebox_override("disabled", _mk_sb(Color(0.10, 0.08, 0.16)))
	btn.add_theme_stylebox_override("focus",    _mk_sb(base.lightened(0.15)))
	btn.add_theme_color_override("font_color",          Color(1.00, 0.92, 0.96))
	btn.add_theme_color_override("font_hover_color",    Color(1.00, 1.00, 1.00))
	btn.add_theme_color_override("font_pressed_color",  Color(1.00, 0.85, 0.90))
	btn.add_theme_color_override("font_disabled_color", Color(0.28, 0.24, 0.34))
