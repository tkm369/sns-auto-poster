extends CanvasLayer

@onready var scene_image:   TextureRect = $SceneImage
@onready var dialogue_box:  CanvasLayer = $DialogueBox
@onready var dialogue_lbl:  Label       = $DialogueBox/DialogueLbl
@onready var speaker_lbl:   Label       = $DialogueBox/SpeakerLbl
@onready var next_btn:      Button      = $DialogueBox/NextBtn
@onready var close_btn:     Button      = $CloseBtn
@onready var auto_timer:    Timer       = $AutoTimer
@onready var auto_btn:      Button      = $AutoBtn

var scene_id:     int  = -1
var page:         int  = 0
var auto_advance: bool = false
var is_drag:      bool = false

const IMG_W := 1500.0
const IMG_H := 845.0
const PAN_DUR := 40.0

var pan_tween: Tween = null

const SCENES := {
	0: {
		"image": "res://assets/h_scenes/fellatio.png",
		"lines": [
			{"speaker": "涼子", "text": "んっ…♡　胸で…きもちいい…？"},
			{"speaker": "涼子", "text": "もっと…激しくして…♡　ずっとしてあげる…"},
			{"speaker": "涼子", "text": "あっ…あぁっ…♡　もう…我慢できない…"},
		]
	},
	1: {
		"image": "res://assets/h_scenes/sex.png",
		"lines": [
			{"speaker": "涼子", "text": "はぁ…♡　奥まで…来て…"},
			{"speaker": "涼子", "text": "あぁっ…！　すごい…気持ちいいっ…！"},
			{"speaker": "涼子", "text": "もっと…激しく…！　私だけを見てて…！"},
			{"speaker": "涼子", "text": "ふぅ…もうすぐ…一緒に…♡"},
		]
	},
}

func _ready() -> void:
	visible = false
	dialogue_box.visible = false
	next_btn.pressed.connect(_next)
	close_btn.pressed.connect(_close)
	auto_btn.pressed.connect(_toggle_auto)
	auto_timer.timeout.connect(func(): if auto_advance: _next())
	GameManager.h_scene_triggered.connect(_on_trigger)

func _input(event: InputEvent) -> void:
	if not visible: return
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_RIGHT:
			is_drag = mb.pressed
			if mb.pressed: _stop_pan()
	elif event is InputEventMouseMotion and is_drag:
		scene_image.position += (event as InputEventMouseMotion).relative
		_clamp()

func _clamp() -> void:
	scene_image.position.x = clamp(scene_image.position.x, -(IMG_W - 1280), 0)
	scene_image.position.y = clamp(scene_image.position.y, -(IMG_H - 720),  0)

func show_scene(id: int) -> void:
	scene_id = id
	page     = 0
	if not SCENES.has(id): return
	var tex = load(SCENES[id]["image"])
	if tex:
		scene_image.texture  = tex
		scene_image.size     = Vector2(IMG_W, IMG_H)
		scene_image.position = Vector2(-110, -62)
	_show_page(0)
	visible = true
	dialogue_box.visible = true
	_start_pan()

func _show_page(p: int) -> void:
	if not SCENES.has(scene_id): return
	var lines: Array = SCENES[scene_id]["lines"]
	if p < 0 or p >= lines.size(): return
	var l: Dictionary = lines[p]
	speaker_lbl.text = l.get("speaker", "")
	dialogue_lbl.text = l.get("text", "")

func _next() -> void:
	if not SCENES.has(scene_id): return
	var lines: Array = SCENES[scene_id]["lines"]
	if page < lines.size() - 1:
		page += 1
		_show_page(page)
		if auto_advance: auto_timer.start()
	else:
		_close()

func _close() -> void:
	_stop_pan()
	visible = false
	dialogue_box.visible = false
	auto_advance = false
	auto_btn.text = "AUTO"
	auto_timer.stop()
	scene_image.size     = Vector2(1280, 720)
	scene_image.position = Vector2.ZERO

func _toggle_auto() -> void:
	auto_advance = not auto_advance
	auto_btn.text = "AUTO ✓" if auto_advance else "AUTO"
	if auto_advance: auto_timer.start()
	else: auto_timer.stop()

func _start_pan() -> void:
	_stop_pan()
	pan_tween = create_tween().set_loops()
	pan_tween.tween_property(scene_image, "position:x", -110 - 100, PAN_DUR)\
		.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	pan_tween.tween_property(scene_image, "position:x", -110, PAN_DUR)\
		.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)

func _stop_pan() -> void:
	if pan_tween: pan_tween.kill(); pan_tween = null

func _on_trigger(id: int) -> void:
	show_scene(id)
