"""保留既有Strata配置；只在開始／檢討後核對策略，不每60秒重載模型。"""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
from laya_pokemon.core import write_json,utc_now,sha256_file
from laya_pokemon.local_planner import PlannerConfig,StrataPlanner,PlannerError
from strata_supervisor import snapshot_from_state

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);parser.add_argument('--rom',default='roms/pokemon_red.gb');parser.add_argument('--state',required=True);parser.add_argument('--plan',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
out=Path(args.output).resolve();config_path=Path(args.config).resolve()
if not out.is_relative_to(root/'outputs') or not config_path.is_relative_to(root/'.local'):raise ValueError('路徑不符')
out.mkdir(parents=True,exist_ok=False)
planner=StrataPlanner(PlannerConfig.load(config_path));planner.verify_model()
snapshot=snapshot_from_state(Path(args.rom).resolve(),Path(args.state).resolve());snapshot['mission']='league_campaign';snapshot['current_goal']='Review guide and battle lessons, then continue to Cerulean gym. Low-health center detours are implemented. A confirmed battle loss MUST pause for evidence, cause, adjustments and validation before resuming; never rewind. Each new badge also requires a pause and engineering review.'
recovery=snapshot['battle']=='trainer' and snapshot['party'] and snapshot['party'][0]['hp']==0
choices=['battle_recovery','review','stop'] if recovery else ['league_campaign','review','stop']
plan=json.loads(Path(args.plan).read_text(encoding='utf-8'))
if plan.get('mode')=='balanced_training' and not recovery:
 choices=['balanced_training','review','stop']
 snapshot['current_goal']='User explicitly requires training all party members. Weakest member leads; normal in-battle switching shares EXP. Nearby Center healing is implemented. Pause for all-member minimum level '+str(plan.get('training_min_level',12))+', any battle loss or unsupported menu.'
if recovery:snapshot['current_goal']='Recover this in-progress trainer battle. Cannot heal or escape during trainer battle. Use healthy-party selection, accept natural loss if it occurs, heal after blackout, then pause for review. Do not travel onward yet.'
t=time.monotonic()
try:
 decision=planner.decide(snapshot,choices)
except PlannerError as error:
 write_json(out/'planner-error.json',{'at':utc_now(),'error':str(error),'latency_seconds':time.monotonic()-t,'guide_sha256':sha256_file(root/'docs/pokemon-red-strategy-guide.md'),'usage':None})
 raise
write_json(out/'initial-strata-decision.json',{'at':utc_now(),**decision,'latency_seconds':time.monotonic()-t,'guide_sha256':sha256_file(root/'docs/pokemon-red-strategy-guide.md'),'configuration_sha256':sha256_file(config_path)})
if decision['stage'] not in {'league_campaign','battle_recovery','balanced_training'}:raise SystemExit('Strata要求檢討，未啟動遊戲')
environment=dict(os.environ)
if planner.config.api_key_env:environment.pop(planner.config.api_key_env,None)
command=[sys.executable,'-X','utf8','-m','laya_pokemon.campaign','--rom',args.rom,'--state',args.state,'--plan',args.plan,'--output',str(out/'game')]
with (out/'game.log').open('w',encoding='utf-8') as log:
 result=subprocess.run(command,cwd=root,stdout=log,stderr=subprocess.STDOUT,env=environment)
raise SystemExit(result.returncode)
