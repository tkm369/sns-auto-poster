extends Node2D

const SCALE := 0.38   # ビューポートに収まるサイズ

var current_state: int = 0
var is_anim: bool = false

# 4レイヤー
var spr_base:  Sprite2D = null
var spr_skirt: Sprite2D = null
var spr_body:  Sprite2D = null
var spr_hair:  Sprite2D = null

# アニメ変数
var t:          float = 0.0
var spring_pos: float = 0.0
var spring_vel: float = 0.0
const K := 9.0
const D := 3.2
var smx: float = 0.0

func _ready() -> void:
	spr_base  = _mk("res://assets/characters/state_0.png")
	spr_skirt = _mk("res://assets/characters/state_0_skirt.png")
	spr_body  = _mk("res://assets/characters/state_0_body.png")
	spr_hair  = _mk("res://assets/characters/state_0_hair.png")

	print("[char] base=%s skirt=%s body=%s hair=%s" % [
		spr_base != null, spr_skirt != null, spr_body != null, spr_hair != null])

	var layers := [spr_base, spr_skirt, spr_body, spr_hair]
	for spr in layers:
		if spr:
			spr.modulate.a = 0.0
			add_child(spr)
			create_tween().tween_property(spr, "modulate:a", 1.0, 0.8)

	GameManager.strip_performed.connect(_on_strip)

func _mk(path: String) -> Sprite2D:
	var tex = load(path)
	if not tex: return null
	var s := Sprite2D.new()
	s.texture  = tex
	s.scale    = Vector2(SCALE, SCALE)
	s.centered = true
	return s

func _process(delta: float) -> void:
	t += delta
	if is_anim or spr_hair == null: return

	var sway    := sin(t * 0.38)
	var breathe := sin(t * 0.86)
	var wave    := sin(t * 1.9)

	var force := (sway - spring_pos) * K - spring_vel * D
	spring_vel += force * delta
	spring_pos += spring_vel * delta
	var lag := spring_pos - sway

	var vp  := get_viewport().get_visible_rect().size
	var mp  := get_viewport().get_mouse_position()
	var rmx: float = clamp((mp.x - vp.x * 0.5) / (vp.x * 0.5), -1.0, 1.0)
	smx = lerp(smx, rmx, delta * 3.5)

	# base
	spr_base.position.x = sway * 3.0
	spr_base.position.y = breathe * 5.0
	spr_base.rotation   = sway * 0.005

	# body
	spr_body.position.x = sway * 8.0 + smx * 6.0
	spr_body.position.y = breathe * 13.0
	spr_body.rotation   = sway * 0.013 + smx * 0.009
	spr_body.scale      = Vector2(SCALE * (1.0 + breathe * 0.016), SCALE)

	# hair
	spr_hair.position.x = sway * 8.0 + smx * 6.0 + lag * 24.0
	spr_hair.position.y = breathe * 6.0 + sin(t * 1.05) * 3.5
	spr_hair.rotation   = sway * 0.013 + smx * 0.009 + lag * 0.075
	spr_hair.scale      = Vector2(SCALE, SCALE)

	# skirt
	spr_skirt.position.x = sway * 8.0 + smx * 6.0 + wave * 5.0
	spr_skirt.position.y = breathe * 16.0
	spr_skirt.rotation   = sway * 0.013 + wave * 0.011
	spr_skirt.scale      = Vector2(SCALE, SCALE)

func set_state(state: int) -> void:
	current_state = clampi(state, 0, 6)
	var s := current_state
	_tex(spr_base,  "res://assets/characters/state_%d.png" % s)
	_tex(spr_hair,  "res://assets/characters/state_%d_hair.png" % s)
	_tex(spr_body,  "res://assets/characters/state_%d_body.png" % s)
	_tex(spr_skirt, "res://assets/characters/state_%d_skirt.png" % s)

func _tex(spr: Sprite2D, path: String) -> void:
	if not spr: return
	var tx = load(path)
	if tx: spr.texture = tx

func _on_strip(new_state: int) -> void:
	is_anim = true
	var tw := create_tween()
	tw.tween_method(_scale_all, SCALE, SCALE * 1.15, 0.09)
	tw.tween_method(_scale_all, SCALE * 1.15, SCALE * 0.88, 0.09)
	tw.tween_callback(func(): set_state(new_state))
	tw.tween_method(_scale_all, SCALE * 0.88, SCALE, 0.22)
	tw.tween_callback(func(): is_anim = false)

func _scale_all(s: float) -> void:
	for spr in [spr_base, spr_hair, spr_body, spr_skirt]:
		if spr: spr.scale = Vector2(s, s)

# タッチリアクション（揺れ）
func react_touch() -> void:
	if is_anim: return
	var tw := create_tween()
	tw.set_parallel(true)
	tw.tween_property(spr_body, "position:x", 18.0, 0.06) if spr_body else null
	tw.tween_property(spr_body, "position:x", 0.0,  0.18).set_delay(0.06) if spr_body else null
	tw.tween_property(spr_hair, "rotation",    0.04, 0.06) if spr_hair else null
	tw.tween_property(spr_hair, "rotation",    0.0,  0.30).set_delay(0.06) if spr_hair else null
