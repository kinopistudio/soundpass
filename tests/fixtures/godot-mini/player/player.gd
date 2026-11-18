extends CharacterBody2D

signal jumped
signal coin_collected

func _physics_process(delta: float) -> void:
	if Input.is_action_just_pressed("jump") and is_on_floor():
		velocity.y = -400.0
		jumped.emit()

func _on_coin_area_entered(area: Area2D) -> void:
	coin_collected.emit()
	area.queue_free()

func explode() -> void:
	queue_free()
