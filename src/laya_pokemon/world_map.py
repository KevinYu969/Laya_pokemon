"""唯讀解碼目前已載入地圖，供森林迷宮尋路；不修改ROM／RAM。"""
from collections import deque


def read_world_grid(pyboy, location):
    width, height = int(pyboy.memory[0xD369]), int(pyboy.memory[0xD368])
    if not 1 <= width <= 40 or not 1 <= height <= 72 or (width+6)*(height+6) > 1300:
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
    return {'walkable': [[int(tile in collision) for tile in row] for row in tiles],
            'tiles': tiles, 'grass': grass, 'screen_cells_verified': len(compared),
            'source': 'wOverworldMap C6E8 / map header D368-D369 / tileset D52B-D535; fixed Red ROM'}


def world_direction(grid, location, target, blocked=()):
    """BFS找完整路線；圖外出口先走到邊界，下一步才踏出。"""
    cells = grid['walkable'];height=len(cells);width=len(cells[0])
    start = location['x'],location['y'];raw = target['x'],target['y']
    end = max(0,min(width-1,raw[0])),max(0,min(height-1,raw[1]))
    if start == end:
        if raw == end:return None
        direction='left' if raw[0]<0 else 'right' if raw[0]>=width else 'up' if raw[1]<0 else 'down'
        return {'direction':direction,'path_length':1,'endpoint':list(raw),'kind':'map_exit'}
    obstacles=set(blocked)-{start,end}
    parents={start:None};queue=deque([start])
    while queue:
        x,y=queue.popleft()
        if (x,y)==end:break
        for dx,dy in ((0,-1),(-1,0),(1,0),(0,1)):
            p=x+dx,y+dy
            if (0<=p[0]<width and 0<=p[1]<height and cells[p[1]][p[0]]==1
                    and p not in parents and p not in obstacles):
                parents[p]=(x,y);queue.append(p)
    if end not in parents:return None
    path=[];p=end
    while p is not None:path.append(p);p=parents[p]
    path.reverse();dx,dy=path[1][0]-start[0],path[1][1]-start[1]
    return {'direction':{(0,-1):'up',(0,1):'down',(-1,0):'left',(1,0):'right'}[(dx,dy)],
            'path_length':len(path)-1,'endpoint':list(end),'screen_cells_verified':grid['screen_cells_verified']}
