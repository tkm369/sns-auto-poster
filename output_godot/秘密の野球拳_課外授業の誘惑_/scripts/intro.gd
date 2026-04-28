extends Node2D

@onready var speaker_bg: ColorRect      = $UILayer/SpeakerBg
@onready var speaker_label: Label       = $UILayer/SpeakerLabel
@onready var dialogue_label: Label      = $UILayer/DialogueLabel
@onready var click_hint: Label          = $UILayer/ClickHint
@onready var start_button: Button       = $UILayer/StartButton
@onready var character_sprite: Sprite2D = $CharNode/CharacterSprite

const DIALOGUE := [
	{"speaker": "ナレーション", "text": "放課後の誰もいない教室。薄暗い室内に、見知った姿があった。",     "color": Color(0.8, 0.8, 0.8, 1)},
	{"speaker": "涼子",         "text": "……来てくれたんだ。ちゃんと来てくれると思ってたよ♪",            "color": Color(1, 0.7, 0.8, 1)},
	{"speaker": "あなた",       "text": "なんで俺だけ呼び出されたんだ？",                             "color": Color(0.7, 0.9, 1, 1)},
	{"speaker": "涼子",         "text": "ひみつのゲームをしたくって。……ふたりきりで、ね。",              "color": Color(1, 0.7, 0.8, 1)},
	{"speaker": "あなた",       "text": "ゲーム……？",                                               "color": Color(0.7, 0.9, 1, 1)},
	{"speaker": "涼子",         "text": "触れ合いゲームよ。私が喜ぶほど……もっと大胆になってあげる。",   "color": Color(1, 0.7, 0.8, 1)},
	{"speaker": "涼子",         "text": "髪でも、頬でも、……もっと大事なところでも。触れてみてよ？",     "color": Color(1, 0.7, 0.8, 1)},
	{"speaker": "あなた",       "text": "（なんで断れないんだ……俺のドキドキが止まらない）",             "color": Color(0.7, 0.9, 1, 1)},
	{"speaker": "涼子",         "text": "感度が高まったら……脱いであげるから。さあ、始めましょ♡",         "color": Color(1, 0.7, 0.8, 1)},
]

var current_line: int = 0

# ── シェーダー・アニメーション ────────────────────────────────
var shader_mat: ShaderMaterial = null
var shader_time: float         = 0.0
var idle_time: float           = 0.0
var base_scale: Vector2        = Vector2(0.34, 0.34)

const BREATHE_SPEED := 0.85
const BREATHE_Y     := 14.0
const SWAY_SPEED    := 0.37
const SWAY_X        := 9.0
const SWAY_ROT      := 0.024
const MOUSE_ROT_STR := 0.022
const MOUSE_POS_STR := 7.0
const MOUSE_LERP    := 3.0

var spring_pos: float = 0.0
var spring_vel: float = 0.0
const SPRING_K := 14.0
const SPRING_D := 3.8

func _ready() -> void:
	var tex = load("res://assets/characters/state_0.png")
	if tex:
		character_sprite.texture = tex

	base_scale = character_sprite.scale

	# シェーダー適用
	var shader = load("res://assets/shaders/character_wave.gdshader")
	if shader:
		shader_mat = ShaderMaterial.new()
		shader_mat.shader = shader
		shader_mat.set_shader_parameter("wave_time", 0.0)
		shader_mat.set_shader_parameter("intensity", 1.0)
		character_sprite.material = shader_mat

	# 登場アニメーション
	character_sprite.modulate.a = 0.0
	character_sprite.position.y = 70.0
	var intro := create_tween()
	intro.set_parallel(true)
	intro.tween_property(character_sprite, "modulate:a", 1.0, 0.8).set_trans(Tween.TRANS_QUAD)
	intro.tween_property(character_sprite, "position:y", 0.0, 0.8).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)

	start_button.visible = false
	start_button.pressed.connect(_start_game)
	_show_line(0)

func _process(delta: float) -> void:
	idle_time   += delta
	shader_time += delta

	var sway := sin(idle_time * SWAY_SPEED)

	# スプリング物理
	var spring_force := (sway - spring_pos) * SPRING_K - spring_vel * SPRING_D
	spring_vel += spring_force * delta
	spring_pos += spring_vel * delta

	if shader_mat:
		shader_mat.set_shader_parameter("wave_time",     shader_time)
		shader_mat.set_shader_parameter("spring_offset", spring_pos)

	var breathe := sin(idle_time * BREATHE_SPEED)

	var vp_size:   Vector2 = get_viewport().get_visible_rect().size
	var mouse_pos: Vector2 = get_viewport().get_mouse_position()
	var norm_x:    float   = clamp((mouse_pos.x - vp_size.x * 0.5) / (vp_size.x * 0.5), -1.0, 1.0)

	var final_x:   float = sway * SWAY_X   + norm_x * MOUSE_POS_STR
	var final_rot: float = sway * SWAY_ROT + norm_x * MOUSE_ROT_STR

	character_sprite.position.x = lerp(character_sprite.position.x, final_x,   delta * MOUSE_LERP)
	character_sprite.position.y = breathe * BREATHE_Y
	character_sprite.rotation   = lerp(character_sprite.rotation,   final_rot,  delta * MOUSE_LERP)
	var s := 1.0 + breathe * 0.018
	character_sprite.scale = base_scale * Vector2(s, s)

func _input(event: InputEvent) -> void:
	if start_button.visible:
		return
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		_advance()
	if event is InputEventKey and event.pressed and event.keycode in [KEY_ENTER, KEY_SPACE, KEY_Z]:
		_advance()

func _advance() -> void:
	current_line += 1
	if current_line >= DIALOGUE.size():
		_show_start()
	else:
		_show_line(current_line)

func _show_line(idx: int) -> void:
	var line: Dictionary = DIALOGUE[idx]
	speaker_label.text     = line["speaker"]
	speaker_label.modulate = line["color"]
	speaker_bg.visible     = (line["speaker"] != "ナレーション")
	dialogue_label.text    = line["text"]
	click_hint.visible     = true

func _show_start() -> void:
	speaker_label.text     = "涼子"
	speaker_label.modulate = Color(1, 0.7, 0.8, 1)
	speaker_bg.visible     = true
	dialogue_label.text    = "……さあ、触れてみて♡　怖くないから。"
	click_hint.visible     = false
	start_button.visible   = true

func _start_game() -> void:
	get_tree().change_scene_to_file("res://scenes/main.tscn")
