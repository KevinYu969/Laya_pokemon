"""道館與關鍵事件時間帳；原始畫面與狀態證據留本機。"""
from datetime import datetime,timezone,timedelta
from pathlib import Path
from .core import utc_now,write_json,append_jsonl,sha256_file

GYMS=[('brock','灰色徽章／小剛',1),('misty','藍色徽章／小霞',2),('lt_surge','橘色徽章／馬志士',4),('erika','彩虹徽章／莉佳',8),('koga','粉紅徽章／阿桔',16),('sabrina','金色徽章／娜姿',32),('blaine','深紅徽章／夏伯',64),('viridian_gym_giovanni','綠色徽章／坂木',128)]


class Journal:
    def __init__(self,output,baseline):
        self.output=Path(output);self.seen_events={k for k,v in baseline['story_event_bits'].items() if v}
        self.known_event_names=set(baseline['story_event_bits'])
        self.readable_event_names={k for k,v in baseline['story_event_bits'].items() if type(v) is bool}
        self.seen_gyms={name for name,label,bit in GYMS if baseline['story_event_bits'].get('beat_'+name) and (baseline['badges_raw'] or 0)&bit}
        self.armed_gyms={name for name,label,bit in GYMS if baseline['story_event_bits'].get('beat_'+name) is False
                         and type(baseline.get('badges_raw')) is int and not baseline['badges_raw']&bit}
        self.captures=set();self.serial=0
    def battle_loss(self,pyboy,state,evidence,timing,save):
        capture=self.capture(pyboy,'battle-loss',state,timing)
        checkpoint=save('battle-loss-%05d.state'%self.serial)
        item={'at':utc_now(),'kind':'battle_loss','evidence':evidence,'timing':timing,
              'checkpoint_sha256':sha256_file(checkpoint),'capture':capture,'review_status':'required'}
        append_jsonl(self.output/'battle-losses.jsonl',item)
        write_json(self.output/'loss-review-template.json',{
            'cause':'','evidence':'','adjustments':'','validation':''})
        return item
    def capture(self,pyboy,kind,state,timing):
        key=(kind,tuple(sorted(state.get('location',{}).items())),state.get('enemy_species'),tuple(state.get('visible_text_candidates',[])))
        if key in self.captures:return None
        self.captures.add(key);self.serial+=1
        filename=f'{self.serial:05d}-{kind}.png';path=self.output/'keyframes'/filename;path.parent.mkdir(exist_ok=True)
        pyboy.screen.image.save(path)
        item={'at':utc_now(),'kind':kind,'file':'keyframes/'+filename,'sha256':sha256_file(path),'location':state.get('location'),'text':state.get('visible_text_candidates',[]),'timing':timing}
        append_jsonl(self.output/'captures.jsonl',item);return item
    def observe(self,pyboy,state,timing,save):
        progress=state['progress'];new=[]
        for name,label,bit in GYMS:
            event=progress['story_event_bits'].get('beat_'+name);badges=progress.get('badges_raw')
            if event is False and type(badges) is int and not badges&bit:self.armed_gyms.add(name)
            if name not in self.seen_gyms and event is True and (badges or 0)&bit and name not in self.armed_gyms:
                self.seen_gyms.add(name)  # 首次可讀就已完成；沒有本輪完成時間證據。
            if name not in self.seen_gyms and event is True and (badges or 0)&bit and state['phase']=='unclassified' and state.get('battle_state',{}).get('kind')=='none':
                self.seen_gyms.add(name);new.append((name,label,'gym'))
        for name,value in progress['story_event_bits'].items():
            if name not in self.known_event_names or name not in self.readable_event_names:
                self.known_event_names.add(name)
                if type(value) is bool:self.readable_event_names.add(name)
                if value is True:self.seen_events.add(name)
                continue  # 熱增觀測項的已成立事件只作基線，不杜撰完成時間。
            if value is True and name not in self.seen_events:
                self.seen_events.add(name)
                if not name.startswith('beat_') or name in {'beat_cerulean_rival','beat_mt_moon_exit_super_nerd','beat_loreleis_room_trainer_0','beat_brunos_room_trainer_0','beat_agathas_room_trainer_0','beat_lance','beat_champion_rival'}:new.append((name,name,'story'))
        records=[]
        for name,label,kind in new:
            now=utc_now();capture=self.capture(pyboy,'milestone-'+name,state,timing);checkpoint=save('milestone-'+name+'.state')
            item={'id':name,'label':label,'kind':kind,'completed_at_utc':now,'completed_at_taipei':datetime.fromisoformat(now).astimezone(timezone(timedelta(hours=8), 'Asia/Taipei')).isoformat(),'timing':timing,'badges_raw':progress['badges_raw'],'story_event_bits':progress['story_event_bits'],'party':progress['party'],'checkpoint_sha256':sha256_file(checkpoint),'capture':capture}
            append_jsonl(self.output/'milestones.jsonl',item);records.append(item)
        return records
