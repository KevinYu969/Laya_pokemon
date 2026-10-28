"""Source anchors only calibrate NPC reads; only current positions block walking.

Fixed Victory Road 2F/3F only. No input, tick, memory write, inferred hidden state,
or changes to source boulder cases. Parent calls only in ordinary waypoint flow.
"""
SOURCE_COMMIT='a53671100ec22e5394ff26ec028d0812a238dae2'
FLOORS={194:(13,('2f_switch1','2f_switch2')),198:(10,('3f_switch1','3f_hole'))}
TOGGLES={194:((6,91),(7,92),(8,93),(9,94),(10,95),(13,96)),
         198:((5,120),(6,121),(10,122))}
GRID_SOURCE='wOverworldMap C6E8 / map header D368-D369 / tileset D52B-D535; fixed Red ROM'


def applies(map_id):return type(map_id) is int and map_id in FLOORS
def _int(v,low=0,high=255):return type(v) is int and low<=v<=high


def _unknown(reason):
    return dict(read_valid=False,read_error=reason,review_reason='victory_navigation_'+reason)


def source_anchors(map_id,*,boulder_module):
    """Union of exact static source cases is calibration, never blocked cells."""
    if not applies(map_id) or getattr(boulder_module,'SOURCE_COMMIT',None)!=SOURCE_COMMIT:return None
    if getattr(boulder_module,'TOGGLE_TABLES',None)!=TOGGLES:return None
    count,keys=FLOORS[map_id];anchors=set()
    try:
        for key in keys:
            case=boulder_module.CASES[key];objects=case['source_all_c2_objects']
            if (case['map_id']!=map_id or case['object_count']!=count or type(objects) is not list
                    or len(objects)!=count):return None
            for i,obj in enumerate(objects,1):
                if (type(obj) is not dict or set(obj)!={'slot','x','y'}
                        or not _int(obj['slot'],1,count) or obj['slot']!=i
                        or not _int(obj['x'],0,29) or not _int(obj['y'],0,17)):return None
                anchors.add((obj['x'],obj['y']))
    except (KeyError,TypeError,AttributeError):return None
    return tuple(sorted(anchors))


def _grid_verified(grid,location,frame):
    if (type(grid) is not dict or grid.get('source')!=GRID_SOURCE
            or type(location) is not dict or set(location)!={'map_id','x','y'}
            or not applies(location['map_id']) or not _int(location['x'],0,29) or not _int(location['y'],0,17)
            or type(frame) is not int or frame<0 or type(grid.get('observation_frame')) is not int
            or grid['observation_frame']!=frame or type(grid.get('tileset_id')) is not int or grid['tileset_id']!=17
            or type(grid.get('verified_location')) is not list
            or any(type(v) is not int for v in grid['verified_location'])
            or grid['verified_location']!=[location['map_id'],location['x'],location['y']]
            or not _int(grid.get('screen_cells_verified'),12,540)):return False
    cells=grid.get('walkable')
    return (type(cells) is list and len(cells)==18 and all(type(row) is list and len(row)==30
        and all(_int(v,0,1) for v in row) for row in cells))


def read_victory_road_npcs(pyboy,grid,location,*,world_map_module,boulder_module,overworld_ready=False):
    """None only means another floor; known-floor unknown is a read_valid=False receipt."""
    if type(location) is not dict or not applies(location.get('map_id')):return None
    if overworld_ready is not True:return _unknown('closed_world_required')
    frame=getattr(pyboy,'frame_count',None)
    if not _grid_verified(grid,location,frame):return _unknown('frame_or_grid_unverified')
    mid=location['map_id'];count,_=FLOORS[mid]
    anchors=source_anchors(mid,boulder_module=boulder_module)
    if not anchors:return _unknown('fixed_source_anchors_unverified')
    try:
        def sample():
            header=tuple(pyboy.memory[a] for a in (0xD35E,0xD367,0xD368,0xD369,0xD4E1))
            records=tuple((slot,pyboy.memory[0xC100+16*slot],
                pyboy.memory[0xC200+16*slot+5],pyboy.memory[0xC200+16*slot+4]) for slot in range(1,count+1))
            return header,records
        first=sample()
        if (any(not _int(v) for v in first[0]) or first[0]!=(mid,17,9,15,count)
                or any(not _int(pic,1,255) or not _int(x,4,33) or not _int(y,4,21)
                       for slot,pic,x,y in first[1])):return _unknown('native_header_or_objects_unverified')
        observed=world_map_module.read_npc_obstacles(pyboy,grid,anchors,overworld_ready=True)
        second=sample();after=pyboy.frame_count
    except (AttributeError,KeyError,IndexError,TypeError,ValueError):return _unknown('getter_failed')
    if type(after) is not int or after!=frame or first!=second:return _unknown('torn_native_snapshot')
    if (type(observed) is not dict or not _int(observed.get('source_anchor_matches'),1,30)
            or observed.get('toggle_source_calibrated') is not True):return _unknown('npc_or_toggle_calibration_unverified')
    toggle=observed.get('toggle_snapshot')
    if (type(toggle) is not dict or toggle.get('read_valid') is not True
            or toggle.get('profile')!='fixed-red-toggleable-object-snapshot-v1'
            or toggle.get('source_commit')!=SOURCE_COMMIT
            or type(toggle.get('observed_frame')) is not int or toggle['observed_frame']!=frame
            or type(toggle.get('map')) is not int or toggle['map']!=mid
            or type(toggle.get('sprite_count')) is not int or toggle['sprite_count']!=count
            or type(toggle.get('objects')) is not list):return _unknown('toggle_receipt_unverified')
    objects=toggle['objects']
    try:
        if (tuple((o['slot'],o['index']) for o in objects)!=TOGGLES[mid]
                or any(type(o.get('slot')) is not int or type(o.get('index')) is not int
                       or type(o.get('hidden')) is not bool for o in objects)):
            return _unknown('fixed_toggle_pairs_unverified')
        hidden={o['slot'] for o in objects if o['hidden']}
        positions=[(x-4,y-4) for slot,pic,x,y in first[1] if slot not in hidden]
        if (type(observed.get('positions')) is not list or any(type(p) is not tuple or len(p)!=2
                or any(type(v) is not int for v in p) for p in observed['positions'])
                or not set(positions)<=set(observed['positions'])):
            return _unknown('current_positions_unverified')
    except (KeyError,TypeError):return _unknown('toggle_receipt_unverified')
    # Count/header constrain the actual loaded map. Extra unused sprite slots
    # are not current objects; source anchors themselves are never obstacles.
    return dict(observed,read_valid=True,read_error=None,positions=positions,
        fixed_floor=mid,observation_frame=frame,source_anchors=list(anchors),
        source_commit=SOURCE_COMMIT)


def blocked_for_move(plan_blocked,receipt,*,location,target):
    """Preserve explicit walls, release true hidden source cells, use current NPCs."""
    if type(receipt) is not dict or receipt.get('read_valid') is not True:return None
    try:
        old=set()
        for p in plan_blocked:
            if type(p) not in (tuple,list) or len(p)!=2 or any(type(v) is not int for v in p):return None
            old.add(tuple(p))
        current=set(receipt['positions']);cleared=set(map(tuple,receipt['hidden_source_positions']))
        if type(target) is not dict or set(target)!={'x','y'} or any(type(v) is not int for v in target.values()):return None
        endpoint=(max(0,min(29,target['x'])),max(0,min(17,target['y'])));start=(location['x'],location['y'])
        # world_direction intentionally removes an endpoint from obstacles for
        # general interactions. Ordinary known-floor moves may not push one.
        if endpoint in current and endpoint!=start:return None
        return sorted((old-cleared)|current)
    except (KeyError,TypeError,ValueError):return None
