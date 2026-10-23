"""從已關閉的真實分段錄影整理短片，另依日誌重建牆鐘節奏。"""
import argparse,json,math,subprocess
from pathlib import Path
import imageio_ffmpeg
from PIL import Image
from laya_pokemon.core import sha256_file,write_json,utc_now


def verify(path):
    reader=imageio_ffmpeg.read_frames(str(path),pix_fmt='rgb24');meta=next(reader);count=0;first=last=None
    for raw in reader:
        if first is None:first=raw
        last=raw;count+=1
    if not count:raise ValueError('空影片')
    for suffix,raw in [('first',first),('last',last)]:
        Image.frombytes('RGB',meta['size'],raw).save(path.with_name(path.stem+'-'+suffix+'.png'))
    return {'file':path.name,'sha256':sha256_file(path),'frames_decoded':count,'fps':meta['fps'],
            'size':list(meta['size']),'playback_seconds':count/meta['fps']}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--game',required=True);parser.add_argument('--output',required=True);parser.add_argument('--kind',choices=['movement','battle','party'],required=True);parser.add_argument('--speed',type=int,choices=[1,2,4],default=4);parser.add_argument('--min-step',type=int,default=0);args=parser.parse_args()
    root=Path.cwd();game=Path(args.game).resolve();out=Path(args.output).resolve()
    if not game.is_relative_to(root/'outputs') or not out.is_relative_to(root/'outputs'):raise ValueError('只接受專案本機outputs')
    out.mkdir(parents=True,exist_ok=False);matches=[]
    for stepfile in sorted(game.glob('steps-*.jsonl')):
        rows=[json.loads(line) for line in stepfile.read_text(encoding='utf-8').splitlines()]
        video=game/stepfile.name.replace('steps-','video-').replace('.jsonl','.mp4')
        if not rows or not video.exists():continue
        # 只使用已關閉、有可讀取容器資訊的影片。
        try:
            it=imageio_ffmpeg.read_frames(str(video));next(it);it.close()
        except (OSError,RuntimeError,StopIteration):continue
        groups=[];group=[]
        for i,row in enumerate(rows):
            state=row['state'];phase=state['phase']
            selected=(state.get('battle_state',{}).get('active') is True if args.kind=='battle' else phase=='party_menu' if args.kind=='party' else phase=='overworld')
            selected=selected and row['step']>=args.min_step
            if args.kind=='movement' and i:
                selected=selected and state.get('location')!=rows[i-1]['state'].get('location')
            if selected:group.append(i)
            elif group:groups.append(group);group=[]
        if group:groups.append(group)
        for group in groups:
            if len(group)>=3:matches.append((len(group),stepfile,video,rows,group))
    if not matches:raise ValueError('尚無足夠且已關閉的影片')
    _,stepfile,video,rows,indices=max(matches,key=lambda item:item[0]);indices=indices[:120]
    first,last=indices[0],indices[-1];start=sum(r['emulated_frames'] for r in rows[:first])/60
    duration=sum(r['emulated_frames'] for r in rows[first:last+1])/60
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe();fast=out/(args.kind+f'-{args.speed}x.mp4')
    source_duration=min(duration,80)
    subprocess.run([ffmpeg,'-v','error','-ss',str(start),'-t',str(source_duration),'-i',str(video),
                    '-an','-vf',f'setpts=PTS/{args.speed},fps=30','-c:v','libx264','-crf','18','-preset','fast',str(fast)],check=True)
    checked=verify(fast)
    if abs(checked['playback_seconds']-source_duration/args.speed)>.2:raise ValueError('剪輯速度／時長驗證不符')
    record={'at':utc_now(),'kind':args.kind,'source_run':game.parent.name,'source_video':video.name,
            'source_steps':[rows[first]['step'],rows[last]['step']],
            'source_start_emulated_seconds':start,'source_duration_emulated_seconds':source_duration,
            'editing':f'Original PyBoy pixels; post-production {args.speed}x; inference waits omitted; not wall-clock speed.',
            'published':False,'clips':[checked]}
    # 牆鐘版限單一連續戰鬥；按每步真實耗時重採樣，模型等待以原始遊戲影格定格表達。
    if args.kind=='battle' and first>0:
        import numpy as np
        import imageio.v2 as imageio
        chosen=rows[first:last+1];wall=out/'battle-wall-clock-reconstructed.mp4'
        reader=imageio_ffmpeg.read_frames(str(video),pix_fmt='rgb24',input_params=['-ss',str(start)],output_params=['-t',str(duration)])
        meta=next(reader);writer=imageio.get_writer(str(wall),fps=15,codec='libx264',pixelformat='yuv420p',macro_block_size=1)
        previous=rows[first-1]['timing'];last_frame=None;total_wall=0;written=0
        try:
            for row in chosen:
                n=max(1,round(row['emulated_frames']/4));frames=[]
                for _ in range(n):
                    raw=next(reader,None)
                    if raw is None:break
                    frames.append(np.frombuffer(raw,dtype=np.uint8).reshape(meta['size'][1],meta['size'][0],3))
                if not frames:break
                now=row['timing'];seconds=max(0,now['wall_seconds']-previous['wall_seconds']-(now['review_pause_seconds']-previous['review_pause_seconds']));previous=now;total_wall+=seconds
                amount=max(0,round(total_wall*15)-written)
                for j in range(amount):writer.append_data(frames[min(len(frames)-1,int(j/amount*len(frames)))]);written+=1
        finally:writer.close();reader.close()
        record['clips'].append({**verify(wall),'editing':'Reconstructed from per-action wall times; review pauses omitted. Original frames resampled; waiting position within each action is approximate.','logged_active_wall_seconds':total_wall})
    write_json(out/'receipt.json',record);print(json.dumps(record,ensure_ascii=False))


if __name__=='__main__':main()
