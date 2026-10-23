"""獨立人工遊玩入口：無模型、無API；定期及關窗保存，不覆寫來源存檔。"""
import argparse
from datetime import datetime
from pathlib import Path
import time

from laya_pokemon.core import parse_rom_header, sha256_file, write_json, utc_now

ROOT = Path(__file__).resolve().parents[1]


def manual_session(rom, state, output, *, factory=None, clock=time.monotonic):
    rom, state, output = Path(rom).resolve(), Path(state).resolve(), Path(output).resolve()
    if not rom.is_relative_to(ROOT) or not state.is_relative_to(ROOT) or not output.is_relative_to(ROOT/'outputs'):
        raise ValueError('ROM／來源存檔須在專案內，輸出須在outputs內')
    header=parse_rom_header(rom)
    if not state.is_file():raise ValueError('找不到來源存檔')
    output.mkdir(parents=True,exist_ok=False)
    record={'recorded_at':utc_now(),'mode':'manual','model_loaded':False,'api_calls':0,
            'source_state_sha256':sha256_file(state),'rom_sha256':header['sha256'],
            'auto_gameplay_enabled':False,'status':'running','checkpoint_interval_seconds':10}
    write_json(output/'summary.json',record)
    if factory is None:
        from pyboy import PyBoy
        factory=PyBoy
    emulator=None
    def save(name):
        temporary=output/(name+'.tmp')
        with temporary.open('wb') as stream:emulator.save_state(stream)
        temporary.replace(output/name)
    try:
        emulator=factory(str(rom),window='SDL2',scale=4,sound_emulated=False,title_status=True)
        with state.open('rb') as stream:emulator.load_state(stream)
        emulator.set_emulation_speed(1)
        next_save=clock()+10
        while emulator.tick(1,True,False):
            if clock()>=next_save:
                save('checkpoint.state');next_save=clock()+10
        record.update(status='saved',stop_reason='window_closed')
    except KeyboardInterrupt:
        record.update(status='saved',stop_reason='keyboard_interrupt')
    except Exception as error:
        record.update(status='failed',error_type=type(error).__name__)
        raise
    finally:
        try:
            if emulator:
                try:
                    save('final.state')
                    record['final_state_sha256']=sha256_file(output/'final.state')
                finally:emulator.stop(save=False)
        finally:write_json(output/'summary.json',record)
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom',default='roms/pokemon_red.gb')
    parser.add_argument('--state',required=True)
    parser.add_argument('--output',default='outputs/manual/'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    args=parser.parse_args()
    print('人工模式：方向鍵移動，A=A，S=B，Enter=Start，Backspace=Select，P暫停，空白鍵快轉。',flush=True)
    print('不載入Laya或呼叫Strata；每10秒保存checkpoint，關窗保存final.state。請先停止AI程序。',flush=True)
    output=Path(args.output).resolve();print('本輪保存位置：'+str(output),flush=True)
    manual_session(args.rom,args.state,output)


if __name__=='__main__':main()
