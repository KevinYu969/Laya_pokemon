"""Route16 真六人子選單格的回歸；只用封存投影，不讀ROM/state或操作遊戲。"""
from copy import deepcopy

import pytest

from laya_pokemon.field_moves import CutController


# 封存 route16-cut-submenu-pause-20261024.json 的 clone1 原始18×20格。
# 實況campaign frame1436457；clone frame1不冒稱同一實況幀。
RAW_ROWS = (
    "   NIDOKING   36    ",
    "             121/121",
    "   SNORLAX    41    ",
    "             198/198",
    "   EEVEE      35    ",
    "              90/ 90",
    "   VENUSAUR   35    ",
    "▷            111/111",
    "   FEAROW           ",
    "                    ",
    "   LAPRAS   ▶CUT    ",
    "                    ",
    "             STATS  ",
    "                    ",
    " Choose a P  SWITCH ",
    "                    ",
    "             CANCEL ",
    "                    ",
)
PARTY = [
    dict(species=7, species_name="NIDOKING", level=36, hp=121, max_hp=121,
         exp=42254, status=0, moves=[61,57,30,40], pp=[20,15,25,35]),
    dict(species=132, species_name="SNORLAX", level=41, hp=198, max_hp=198,
         exp=91196, status=0, moves=[70,133,156,34], pp=[15,20,10,15]),
    dict(species=102, species_name="EEVEE", level=35, hp=90, max_hp=90,
         exp=43317, status=0, moves=[33,28,98,39], pp=[35,15,30,30]),
    dict(species=154, species_name="VENUSAUR", level=35, hp=111, max_hp=111,
         exp=36804, status=0, moves=[75,15,73,22], pp=[25,30,10,10]),
    dict(species=35, species_name="FEAROW", level=37, hp=114, max_hp=114,
         exp=51794, status=0, moves=[64,65,43,31], pp=[35,20,30,20]),
    dict(species=19, species_name="LAPRAS", level=30, hp=124, max_hp=124,
         exp=33943, status=0, moves=[55,34,47,54], pp=[25,15,15,30]),
]
LOCATION = dict(map_id=27, x=34, y=10, facing="up")


def packet(rows=RAW_ROWS):
    assert len(rows) == 18 and all(len(row) == 20 for row in rows)
    return dict(profile="gen1-visible-tile-text-candidates-v1-unvalidated",
                read_valid=True, alignment_verified=True, window_visible=True,
                read_error=None, cells=[list(row) for row in rows])


def progress():
    pairs = [(4,6),(42,1),(49,1),(63,1),(228,1),(196,1),(224,1),(74,1),
             (72,1),(40,1),(73,1),(3,9),(206,1),(198,1),(199,1),(48,1),(1,1),(246,1)]
    return dict(profile="gen1-wrapper-ram-progress-v1-unvalidated",
                initialization_candidate=True, party_read_valid=True, party_count=6,
                badges_raw=63, player_name_raw="KEVIN", money=55372,
                party=deepcopy(PARTY),
                inventory=[dict(item=i,quantity=q) for i,q in pairs])


def selected_controller():
    p = progress()
    c = CutController(dict(kind="use_cut", species=154, map_id=27, tree_x=34, tree_y=9))
    grid = dict(tileset_id=0, screen_cells_verified=90,
                tiles=[[0x2C]*36 for _ in range(12)],
                walkable=[[1]*36 for _ in range(12)])
    grid["tiles"][9][34], grid["walkable"][9][34] = 0x3D, 0
    assert c.context(packet([" "*20]*18), p, location=LOCATION, grid=grid,
                     overworld_ready=True)["available_actions"] == ["start","wait"]
    # 前一隊伍頁為合成源槽位；真正重播的raw子選單保持上述格完整不變。
    party_rows = [[" "]*20 for _ in range(18)]
    for i, mon in enumerate(p["party"]):
        name = mon["species_name"]
        party_rows[2*i][3:3+len(name)] = list(name)
    party_rows[7][0] = "▶"
    chosen = c.context(dict(cells=party_rows), p, location=LOCATION)
    assert chosen["available_actions"] == ["a","wait"]
    assert chosen["party_target_index"] == 3 and c.field_user_confirmed is True
    return c, p


def review(out):
    assert out["phase"] == "campaign_review" and out["available_actions"] == ["wait"], out


def test_actual_six_member_raw_submenu_accepts_only_cut_without_mutating_progress():
    c, p = selected_controller()
    t, before_p = packet(), deepcopy(p)
    before_t, before_baseline = deepcopy(t), deepcopy(c.baseline)
    out = c.context(t, p, location=LOCATION)
    assert out["available_actions"] == ["a","wait"] and out["menu_label"] == "CUT"
    assert out["cut_user_species"] == 154 and c.stage == "cut_selected"
    assert p == before_p and t == before_t and c.baseline == before_baseline


@pytest.mark.parametrize("slot", range(6))
def test_every_visible_source_name_is_required_in_its_actual_slot(slot):
    c, p = selected_controller()
    t = packet()
    t["cells"][2*slot][3] = "X"
    before = deepcopy(p)
    review(c.context(t, p, location=LOCATION))
    assert p == before and c.stage != "cut_selected"


@pytest.mark.parametrize("position,marker", [
    ((0,1),"▷"), ((1,7),"▷"), ((12,12),"▷"),
    ((12,12),"▶"), ((0,7),"▶"), ((11,10),"▶"),
])
def test_foreign_or_duplicate_cursor_cannot_be_ignored(position, marker):
    c, p = selected_controller()
    t = packet()
    x,y = position
    t["cells"][y][x] = marker
    review(c.context(t, p, location=LOCATION))
    assert c.stage != "cut_selected"


@pytest.mark.parametrize("confirmed", [False, None, 1])
def test_static_background_requires_true_previously_selected_cut_user(confirmed):
    c, p = selected_controller()
    c.field_user_confirmed = confirmed
    review(c.context(packet(), p, location=LOCATION))
    assert c.stage != "cut_selected"


def test_marker_at_other_member_is_not_a_selected_user_receipt():
    c, p = selected_controller()
    t = packet()
    t["cells"][7][0] = " "
    t["cells"][5][0] = "▷"
    review(c.context(t, p, location=LOCATION))


@pytest.mark.parametrize("row,label", [(10,"CUTTER"),(12,"STAT"),(14,"SWAP"),(16,"EXIT")])
def test_six_member_exception_does_not_relax_any_fixed_submenu_label(row, label):
    c, p = selected_controller()
    t = packet()
    t["cells"][row][13:] = list(label.ljust(7))
    review(c.context(t, p, location=LOCATION))


def test_existing_normal_up_navigation_remains_without_confirming_stats():
    c, p = selected_controller()
    t = packet()
    t["cells"][10][12], t["cells"][12][12] = " ", "▶"
    out = c.context(t, p, location=LOCATION)
    assert out["available_actions"] == ["up","wait"] and c.stage == "cut_menu"


def test_raw_packet_inactive_slot_is_the_venusaur_hp_row_not_a_second_active_cursor():
    assert [(x,y) for y,row in enumerate(RAW_ROWS) for x,char in enumerate(row)
            if char == "▷"] == [(0,7)]
    assert [(x,y) for y,row in enumerate(RAW_ROWS) for x,char in enumerate(row)
            if char == "▶"] == [(12,10)]
    assert RAW_ROWS[8][3:13].strip() == "FEAROW"
    assert RAW_ROWS[10][3:12].strip() == "LAPRAS"
