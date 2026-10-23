"""唯讀解碼目前已載入地圖，供森林迷宮尋路；不修改ROM／RAM。"""
from collections import deque


CAVERN_TILESET_ID = 17
CAVERN_LAND_TILE_PAIRS = ((0x20, 0x05), (0x41, 0x05), (0x2A, 0x05), (0x05, 0x21))
PAIR_COLLISION_SOURCE = "https://github.com/pret/pokered/blob/a53671100ec22e5394ff26ec028d0812a238dae2/data/tilesets/pair_collision_tile_ids.asm"


def cavern_pair_blocked_edges(grid):
    """將固定紅版洞穴陸地雙格碰撞轉成相鄰雙向禁邊，不把整格當牆。

    上游 ``read_world_grid`` 已將每個移動格的左下背景圖塊與畫面核對。
    其他 tileset／一般網格不加規則；聲明為 CAVERN 卻缺少完整圖塊矩陣
    時回傳 ``None``，避免用不完整資料規劃可能穿過高低差的路線。
    """
    if grid.get('tileset_id') != CAVERN_TILESET_ID:
        return set()
    cells, tiles = grid.get('walkable'), grid.get('tiles')
    if (not isinstance(cells, (list, tuple)) or not cells or not cells[0]
            or not isinstance(tiles, (list, tuple)) or len(tiles) != len(cells)):
        return None
    width = len(cells[0])
    if any(not isinstance(row, (list, tuple)) or len(row) != width for row in cells):
        return None
    if any(not isinstance(row, (list, tuple)) or len(row) != width
           or any(type(tile) is not int or not 0 <= tile <= 255 for tile in row) for row in tiles):
        return None
    pairs = {frozenset(pair) for pair in CAVERN_LAND_TILE_PAIRS}
    edges = set()
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            for nx, ny in ((x+1, y), (x, y+1)):
                if nx >= width or ny >= len(tiles):
                    continue
                if frozenset((tile, tiles[ny][nx])) in pairs:
                    edges.add(((x, y), (nx, ny)))
                    edges.add(((nx, ny), (x, y)))
    return edges


def read_npc_obstacles(pyboy,grid,expected):
    """固定紅版SpriteStateData2：NPC格座標含4格邊界；須有來源座標錨點才使用。"""
    try:
        positions=[];height=len(grid['walkable']);width=len(grid['walkable'][0])
        for slot in range(1,16):
            if not pyboy.memory[0xC100+16*slot]:continue
            x=int(pyboy.memory[0xC200+16*slot+5])-4
            y=int(pyboy.memory[0xC200+16*slot+4])-4
            if 0<=x<width and 0<=y<height:positions.append((x,y))
        anchors=len(set(positions)&set(expected))
        if not anchors:return None
        return {'positions':positions,'source_anchor_matches':anchors,
                'source':'fixed Red C100/C200 sprite slots; wram.asm StateData2 mapY+4/mapX+5 minus4'}
    except (AttributeError,IndexError,KeyError,TypeError,ValueError):return None


def read_world_grid(pyboy, location):
    width, height = int(pyboy.memory[0xD369]), int(pyboy.memory[0xD368])
    if not 1 <= width <= 100 or not 1 <= height <= 72 or (width+6)*(height+6) > 1300:
        return None
    bank = int(pyboy.memory[0xD52B])
    pointer = int(pyboy.memory[0xD52C]) + (int(pyboy.memory[0xD52D]) << 8)
    collision_ptr = int(pyboy.memory[0xD530]) + (int(pyboy.memory[0xD531]) << 8)
    if not 0x4000 <= pointer < 0x8000 or not 0 <= collision_ptr < 0x8000:
        return None
    def rom(address):
        return int(pyboy.memory[0 if address < 0x4000 else bank, address])
    collision = set()
    for i in range(384):
        tile = rom(collision_ptr+i)
        if tile == 255:
            break
        collision.add(tile)
    else:
        return None
    grass = int(pyboy.memory[0xD535])
    if grass != 255:
        collision.add(grass)
    tiles = []
    for y in range(height*2):
        row = []
        for x in range(width*2):
            block = int(pyboy.memory[0xC6E8 + (y//2+3)*(width+6) + x//2+3])
            address = pointer + block*16 + (y%2*2+1)*4 + x%2*2
            if not 0x4000 <= address < 0x8000:
                return None
            row.append(rom(address))
        tiles.append(row)
    sprites = [pyboy.get_sprite(index) for index in range(4)]
    sx, sy = min(s.x for s in sprites), min(s.y for s in sprites)
    if sx%16 or (sy+4)%16:
        return None
    ox, oy = location['x']-sx//16, location['y']-(sy+4)//16
    screen = pyboy.game_wrapper._get_screen_background_tilemap()[1::2,::2] % 256
    compared = [(tiles[y+oy][x+ox], int(tile)) for y,row in enumerate(screen) for x,tile in enumerate(row)
                if 0 <= y+oy < height*2 and 0 <= x+ox < width*2]
    if len(compared) < 12 or any(a != b for a,b in compared):
        return None  # 轉場／捲動／選單不一致，不把錯誤地圖當成路徑。
    return {'walkable': [[int(tile in collision) for tile in row] for row in tiles], 'tileset_id':int(pyboy.memory[0xD367]),
            'tiles': tiles, 'grass': grass, 'screen_cells_verified': len(compared),
            'source': 'wOverworldMap C6E8 / map header D368-D369 / tileset D52B-D535; fixed Red ROM'}


def world_direction(grid, location, target, blocked=(), blocked_edges=()):
    """BFS找完整路線；圖外出口先走到邊界，下一步才踏出。"""
    cells = grid['walkable'];height=len(cells);width=len(cells[0])
    start = location['x'],location['y'];raw = target['x'],target['y']
    pair_edges = cavern_pair_blocked_edges(grid)
    if pair_edges is None:
        return None
    forbidden=set(blocked_edges) | pair_edges
    end = max(0,min(width-1,raw[0])),max(0,min(height-1,raw[1]))
    if raw != end and not cells[end[1]][end[0]]:
        if raw[1]<0:candidates=[(x,0) for x,v in enumerate(cells[0]) if v]
        elif raw[1]>=height:candidates=[(x,height-1) for x,v in enumerate(cells[-1]) if v]
        elif raw[0]<0:candidates=[(0,y) for y,row in enumerate(cells) if row[0]]
        else:candidates=[(width-1,y) for y,row in enumerate(cells) if row[-1]]
        if not candidates:return None
        end=min(candidates,key=lambda p:abs(p[0]-raw[0])+abs(p[1]-raw[1]))
    if start == end:
        if raw == end:return None
        direction='left' if raw[0]<0 else 'right' if raw[0]>=width else 'up' if raw[1]<0 else 'down'
        if (start,raw) in forbidden:return None
        return {'direction':direction,'path_length':1,'endpoint':list(raw),'kind':'map_exit'}
    obstacles=set(blocked)-{start,end}
    jumps={}
    if grid.get('tileset_id')==0 and grid.get('tiles'):
        from .navigation import verified_down_ledge
        for yy,row in enumerate(grid['tiles'][:-2]):
            for xx,tile in enumerate(row):
                if (tile,grid['tiles'][yy+1][xx]) not in {(0x2C,0x37),(0x39,0x36),(0x39,0x37)}:continue
                ledge=verified_down_ledge(cells,grid['tiles'],(xx,yy))
                if ledge and ((xx,yy),(xx,yy+1)) not in forbidden:jumps[(xx,yy)]=tuple(ledge['landing_cell'])
    parents={start:None};queue=deque([start])
    while queue:
        x,y=queue.popleft()
        if (x,y)==end:break
        neighbors=[(x,y-1),(x-1,y),(x+1,y),(x,y+1)]
        if (x,y) in jumps:neighbors.append(jumps[(x,y)])
        for p in neighbors:
            if (0<=p[0]<width and 0<=p[1]<height and cells[p[1]][p[0]]==1
                    and p not in parents and p not in obstacles):
                if ((x,y),p) in forbidden:continue
                parents[p]=(x,y);queue.append(p)
    if end not in parents:return None
    path=[];p=end
    while p is not None:path.append(p);p=parents[p]
    path.reverse();dx,dy=path[1][0]-start[0],path[1][1]-start[1]
    return {'direction':{(0,-1):'up',(0,1):'down',(0,2):'down',(-1,0):'left',(1,0):'right'}[(dx,dy)],'ledge_jump':dy==2,
            'path_length':len(path)-1,'endpoint':list(end),'screen_cells_verified':grid['screen_cells_verified']}
