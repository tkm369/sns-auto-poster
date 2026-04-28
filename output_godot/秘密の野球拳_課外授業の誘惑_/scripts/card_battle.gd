extends Control

@onready var opponent_card_label: Label  = $OpponentCard
@onready var result_label: Label         = $ResultLabel
@onready var selected_card_label: Label  = $SelectedCardLabel
@onready var choose_label: Label         = $ChooseLabel
@onready var card_buttons: Array[Button] = []

var player_card_value: int  = 0
var opponent_card_value: int = 0
var is_animating: bool       = false
var hand_values: Array[int]  = []   # 3枚の手札

var strip_lines: Array = [
	"ブレザーを脱いでいいの？ドキドキしちゃうけど……",
	"ワイシャツよ……胸に冷たい風が……",
	"セーターも……肌が喜ぶわね",
	"スカートだけ……もう半分だよ",
	"ストッキングも……足が涼しい……",
	"最後の一枚！これで完全にあなたのものに……"
]

func _ready() -> void:
	card_buttons = [
		$CardButton1 as Button,
		$CardButton2 as Button,
		$CardButton3 as Button,
	]
	for i in range(card_buttons.size()):
		var idx := i
		card_buttons[i].pressed.connect(func(): _on_card_selected(idx))

	GameManager.game_state_changed.connect(_on_game_state_changed)
	opponent_card_label.modulate.a = 0.0
	_deal_hand()

# ── 手札を配る ───────────────────────────────────────────────────
func _deal_hand() -> void:
	hand_values.clear()
	for i in range(3):
		hand_values.append(randi() % 10 + 1)
		card_buttons[i].text = "?"
		card_buttons[i].disabled = false
	choose_label.visible = true
	selected_card_label.text = ""
	opponent_card_label.modulate.a = 0.0
	opponent_card_label.text = "?"

# ── カードを選択 ──────────────────────────────────────────────────
func _on_card_selected(idx: int) -> void:
	if is_animating:
		return
	is_animating = true
	choose_label.visible = false

	# 選択したカードを強調、他を無効化
	for i in range(card_buttons.size()):
		if i == idx:
			card_buttons[i].text = str(hand_values[i])
			card_buttons[i].modulate = Color(1, 1, 0.5, 1)
		else:
			card_buttons[i].disabled = true
			card_buttons[i].modulate = Color(0.5, 0.5, 0.5, 0.6)

	player_card_value   = hand_values[idx]
	opponent_card_value = randi() % 10 + 1
	selected_card_label.text = "あなたのカード: %d" % player_card_value

	# 相手カードを遅延してアニメーション表示
	var tween := create_tween()
	tween.tween_interval(0.8)
	tween.tween_callback(func():
		opponent_card_label.text = str(opponent_card_value)
	)
	tween.tween_property(opponent_card_label, "modulate:a", 1.0, 0.4).from(0.0)
	tween.tween_callback(resolve_round)

# ── 勝敗判定 ──────────────────────────────────────────────────────
func resolve_round() -> void:
	var stripped_idx := GameManager.opponent_clothing_count - 1

	if player_card_value > opponent_card_value:
		result_label.text = "✨ あなたの勝ち！"
		result_label.modulate = Color(1, 1, 0.5, 1)
		GameManager.on_player_wins_round()
		if stripped_idx >= 0 and stripped_idx < strip_lines.size():
			result_label.text += "\n" + strip_lines[stripped_idx]
	elif player_card_value < opponent_card_value:
		result_label.text = "💔 恋花の勝ち……"
		result_label.modulate = Color(1, 0.5, 0.7, 1)
		GameManager.on_opponent_wins_round()
	else:
		result_label.text = "🔥 引き分け！ふたりとも脱ぐ！"
		result_label.modulate = Color(1, 0.7, 0.3, 1)
		GameManager.on_tie_round()
		if stripped_idx >= 0 and stripped_idx < strip_lines.size():
			result_label.text += "\n" + strip_lines[stripped_idx]

	_update_status_labels()

	var tween := create_tween()
	tween.tween_interval(2.5)
	tween.tween_callback(_reset_round)

# ── ステータスラベル更新 ──────────────────────────────────────────
func _update_status_labels() -> void:
	var status := get_node_or_null("/root/Main/StatusPanel/PlayerStatusLabel")
	if status:
		status.text = "あなたの服: %d枚" % GameManager.player_clothing_count

	var opp := get_node_or_null("/root/Main/StatusPanel/OpponentStatusLabel")
	if opp:
		opp.text = "星野 恋花の服: %d枚" % GameManager.opponent_clothing_count

	var rnd := get_node_or_null("/root/Main/StatusPanel/RoundLabel")
	if rnd:
		rnd.text = "ラウンド: %d" % GameManager.round_count

# ── ラウンドリセット ──────────────────────────────────────────────
func _reset_round() -> void:
	var state := GameManager.current_state
	if state == GameManager.GameState.GAME_OVER:
		_show_end("😢 ゲームオーバー……")
		return
	elif state == GameManager.GameState.PLAYER_WIN:
		_show_end("🎉 恋花を完全に落とした！")
		return

	# カードの色をリセット
	for btn in card_buttons:
		btn.modulate = Color(1, 1, 1, 1)

	result_label.text = ""
	result_label.modulate = Color(1, 1, 1, 1)
	is_animating = false
	_deal_hand()

func _show_end(msg: String) -> void:
	result_label.text = msg
	result_label.modulate = Color(1, 1, 1, 1)
	choose_label.text = "もう一度プレイ"
	choose_label.visible = true
	for btn in card_buttons:
		btn.text = ""
		btn.disabled = true
	# もう一度ボタンとして card_buttons[1 を再利用
	card_buttons[1].text = "もう一度"
	card_buttons[1].disabled = false
	card_buttons[1].modulate = Color(1, 1, 1, 1)
	# 既存の接続を切って再接続
	if card_buttons[1].pressed.is_connected(func(): _on_card_selected(1)):
		pass  # 既存のラムダは切れないのでrestart関数で上書き
	card_buttons[1].pressed.disconnect(func(): _on_card_selected(1)) if false else null
	# 一旦全disconnectしてrestart接続
	_reconnect_for_restart()

func _reconnect_for_restart() -> void:
	for btn in card_buttons:
		for conn in btn.pressed.get_connections():
			btn.pressed.disconnect(conn["callable"])
	card_buttons[1].pressed.connect(_on_restart)

func _on_restart() -> void:
	for btn in card_buttons:
		btn.modulate = Color(1, 1, 1, 1)
		for conn in btn.pressed.get_connections():
			btn.pressed.disconnect(conn["callable"])
	for i in range(card_buttons.size()):
		var idx := i
		card_buttons[i].pressed.connect(func(): _on_card_selected(idx))
	GameManager.restart()
	_update_status_labels()
	choose_label.text = "▼ 1枚選んでください"
	result_label.modulate = Color(1, 1, 1, 1)
	is_animating = false
	_deal_hand()

func _on_game_state_changed(_new_state: int) -> void:
	pass
