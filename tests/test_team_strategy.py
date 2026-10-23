"""第一世代規則回歸；特別阻擋重製版招式與稀有 TM 誤用。"""
from laya_pokemon.team_strategy import (
    reference, learn_move_plan, choose_damage_move, capture_plan, desired_captures, TM_RESERVATIONS,
)
from laya_pokemon.battle import battle_context, learning_context
from laya_pokemon.shopping import shopping_context
from test_battle import text_at


def test_pinned_gen1_facts_and_no_frlg_dig_on_nidoking():
    data = reference()
    assert len(data["species"]) == 151 and len(data["moves"]) == 165
    assert data["source_commit"] == "a53671100ec22e5394ff26ec028d0812a238dae2"
    assert "DIG" not in data["species"]["NIDOKING"]["tmhm"]
    assert {"level": 17, "move": "SLEEP_POWDER"} in data["species"]["BUTTERFREE"]["level_moves"]
    for move, recipient in TM_RESERVATIONS.items():
        assert move in data["species"][recipient]["tmhm"]


def test_learn_early_utility_then_replace_growl_not_attack_or_hm():
    assert learn_move_plan("BULBASAUR", [33, 45, 0, 0], "LEECH_SEED", level=7)["decision"] == "learn"
    plan = learn_move_plan("BULBASAUR", ["TACKLE", "GROWL", "LEECH_SEED", "CUT"], "VINE_WHIP", level=13)
    assert plan["forget"] == "GROWL" and plan["replace_index"] == 1
    assert learn_move_plan("BULBASAUR", [33, 45, 0, 0], "SLEEP_POWDER", level=7)["decision"] == "review"
    plan = learn_move_plan("VENUSAUR", ["TACKLE", "FLASH", "GROWTH", "LEECH_SEED"], "SLEEP_POWDER", level=55)
    assert plan["forget"] != "TACKLE" and plan["forget"] != "FLASH"
    assert learn_move_plan("UNKNOWN", [33], "TACKLE", level=5)["decision"] == "review"


def test_type_advantage_pp_and_gen1_ghost_psychic_bug():
    assert choose_damage_move("BULBASAUR", [33, 22, 45, 0], [35, 10, 40, 0], "ONIX") == "VINE_WHIP"
    assert choose_damage_move("BULBASAUR", [33, 22, 45, 0], [35, 0, 40, 0], "ONIX") == "TACKLE"
    assert choose_damage_move("GASTLY", ["LICK", "NIGHT_SHADE"], [30, 15], "ABRA") is None
    assert choose_damage_move("BULBASAUR", [33, 45], [0, 40]) is None
    assert choose_damage_move("KADABRA", ["PSYCHIC_M", "CONFUSION"], [10, 25], "GASTLY") == "PSYCHIC_M"
    assert learn_move_plan("KADABRA", ["PSYBEAM", "RECOVER", "DISABLE", "CONFUSION"],
                           "PSYCHIC_M", level=38)["forget"] == "DISABLE"


def test_capture_never_steals_duplicates_or_overflows_party():
    assert capture_plan("NIDORAN♂", [153], 8, wild=True, party_count=1)["tactic"] == "throw_ball"
    assert capture_plan("NIDORAN_M", ["NIDOKING"], 8, wild=True, party_count=1)["tactic"] == "not_capture"
    assert capture_plan("NIDORAN_M", [153], 8, wild=False, party_count=1)["tactic"] == "not_capture"
    assert capture_plan("NIDORAN_M", [153], 0, wild=True, party_count=1)["tactic"] == "resupply"
    assert capture_plan("NIDORAN_M", [153], 8, wild=True, party_count=6)["tactic"] == "review"
    assert capture_plan("ZAPDOS", [153], 8, wild=True, party_count=1)["tactic"] == "review"
    assert "CATERPIE" not in desired_captures(["BUTTERFREE"])


def test_actual_move_menu_subgoal_uses_new_grass_move():
    party = [{"species": 153, "moves": [33, 45, 73, 22], "pp": [30, 40, 10, 10]}]
    text = text_at((1, 0, "ONIX"), (6, 13, "TACKLE"), (6, 14, "GROWL"),
                   (6, 15, "LEECH SEED"), (6, 16, "VINE WHIP"), (5, 13, "▶"))
    result = battle_context(text, {"active": True, "kind": "trainer"}, party, [])
    assert result["chosen_move"] == "VINE_WHIP" and result["objective"] == "Move DOWN."
    assert result["battle_target_tile"] == [6, 16]


def test_capture_command_and_learning_stop_before_any_forgetting():
    party = [{"species": 153, "level": 13, "moves": [33, 45, 73, 15], "pp": [30, 40, 10, 10]}]
    text = text_at((1, 0, "NIDORAN♂"), (10, 14, "FIGHT"), (10, 16, "ITEM"), (16, 16, "RUN"), (9, 14, "▶"))
    result = battle_context(text, {"active": True, "kind": "wild"}, party, [{"item": 4, "quantity": 8}])
    assert result["battle_tactic"] == "capture" and result["objective"] == "Move DOWN."
    text = text_at((1, 14, "trying to learn"), (1, 16, "VINE WHIP!"))
    result = learning_context(text, party)
    assert result["phase"] == "strategy_review" and result["learn_move_plan"]["forget"] == "GROWL"


def test_shop_never_buys_unknown_quantity_or_spends_below_ball_price():
    assert shopping_context(text_at(), None, 3000)["phase"] == "strategy_review"
    assert shopping_context(text_at(), [], 100)["phase"] == "strategy_review"
    text = text_at((1, 14, "How many?"), (10, 9, "×01"))
    assert shopping_context(text, [], 3000)["objective"] == "Confirm the current selection."
    text["cells"][9][12] = "8"
    assert shopping_context(text, [], 3000)["phase"] == "strategy_review"
    assert shopping_context(text, [{"item": 4, "quantity": 8}], 1400)["objective"].startswith("Cancel")
    assert shopping_context(text_at(), [{"item": 4, "quantity": 8}], 1400) is None


def test_capture_route_keeps_east_of_optional_rival_and_returns_to_heal():
    from laya_pokemon.capture_route import team_waypoint
    party = [{"species": 153, "hp": 21, "max_hp": 21}]
    flags = {"got_pokedex": True}
    location = {"map_id": 33, "x": 35, "y": 10}
    result = team_waypoint(location, flags, party, 8, grass_world=[(29, 4), (29, 5), (34, 10)])
    assert result["controller_waypoint"] == {"map_id": 33, "x": 34, "y": 10}
    party[0]["hp"] = 10
    assert team_waypoint(location, flags, party, 8)["goal"] == "return_route22_east"
    party.append({"species": 3, "hp": 10, "max_hp": 10})  # 0x03 = Nidoran male, not dex#3.
    assert team_waypoint(location, flags, party, 8)["goal"] == "first_team_capture_complete"


def test_capture_bag_selection_does_not_confuse_dialogue_or_other_item():
    party = [{"species": 153}]
    text = text_at((1, 0, "NIDORAN♂"), (2, 3, "POKé BALL"), (2, 5, "POTION"), (1, 5, "▶"))
    result = battle_context(text, {"active": True, "kind": "wild"}, party, [{"item": 4, "quantity": 8}])
    assert result["phase"] == "battle_bag" and result["objective"] == "Move UP."


def test_bag_keeps_target_identity_when_menu_covers_enemy_hud():
    from types import SimpleNamespace
    from laya_pokemon.battle import read_battle_state
    battle = read_battle_state(SimpleNamespace(memory={0xD057: 1, 0xD059: 0, 0xCFE5: 3}))
    assert battle["wild_opponent_species"] == "NIDORAN_M"
    text = text_at((2, 3, "POKé BALL"), (1, 3, "▶"))
    result = battle_context(text, {"active": True, "kind": "wild", "wild_opponent_species": "NIDORAN_M"},
                            [{"species": 153}], [{"item": 4, "quantity": 8}])
    assert result["phase"] == "battle_bag" and result["objective"].startswith("Confirm")
    text = text_at((1, 0, "RATTATA"))
    assert battle_context(text, {"active": True, "kind": "wild", "wild_opponent_species": "NIDORAN_M"})["phase"] == "strategy_review"


def test_actual_mart_quantity_box_is_verified_without_how_many_text():
    text = text_at((6, 3, "POKé BALL"), (8, 9, "×08"), (1, 14, "Take your time."))
    assert shopping_context(text, [], 3000)["phase"] == "strategy_review"


def test_teleport_only_party_is_not_blindly_confirmed_in_trainer_battle():
    text = text_at((6, 13, "TELEPORT"), (5, 13, "▶"))
    result = battle_context(text, {"active": True, "kind": "trainer"},
                            [{"species": 148, "moves": [100, 0, 0, 0], "pp": [20, 0, 0, 0]}])
    assert result["phase"] == "strategy_review"
