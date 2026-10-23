"""只用合成模擬器驗證人工模式保存；不啟動視窗或模型。"""
import importlib.util
from pathlib import Path


def test_manual_mode_preserves_source_saves_last_state_and_does_not_save_cartridge(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('manual_runner',Path(__file__).resolve().parents[1]/'scripts/play_manual.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'ROOT',tmp_path)
    monkeypatch.setattr(module,'parse_rom_header',lambda _: {'sha256':'synthetic'})
    rom=tmp_path/'game.gb';rom.write_bytes(b'synthetic-rom')
    state=tmp_path/'source.state';state.write_bytes(b'original-state')
    events=[]
    class Emulator:
        def __init__(self,*args,**kwargs):events.append(('window',kwargs['window']))
        def load_state(self,stream):assert stream.read()==b'original-state'
        def set_emulation_speed(self,speed):assert speed==1
        def tick(self,*args):return False
        def save_state(self,stream):stream.write(b'manual-progress')
        def stop(self,save):events.append(('stop',save))
    output=tmp_path/'outputs/manual/test'
    result=module.manual_session(rom,state,output,factory=Emulator)
    assert state.read_bytes()==b'original-state'
    assert (output/'final.state').read_bytes()==b'manual-progress'
    assert result['api_calls']==0 and result['model_loaded'] is False and result['stop_reason']=='window_closed'
    assert events==[('window','SDL2'),('stop',False)]
