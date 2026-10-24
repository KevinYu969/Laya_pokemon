"""明確核准的夏伯階段邊界：風速狗首次出現即停，不能送出戰鬥鍵。"""
PROFILE='blaine-arcanine-before-action-v1'


def context(state,step):
    if not isinstance(step,dict) or 'opponent_review' not in step:
        return None
    def review(reason):
        return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
                    review_reason=reason,opponent_review_profile=PROFILE)
    if (step.get('opponent_review')!=PROFILE or step.get('kind')!='interact'
            or type(step.get('map_id')) is not int or step['map_id']!=166
            or type(step.get('target')) is not list or step['target']!=[3,4]
            or any(type(v) is not int for v in step['target'])
            or step.get('face')!='up' or step.get('event')!='beat_blaine'):
        return review('opponent_review_intent_unverified')
    if not isinstance(state,dict):return review('opponent_review_state_unverified')
    loc=state.get('location');b=state.get('battle_state');frame=state.get('frame')
    if (type(loc) is not dict or loc!=dict(map_id=166,x=3,y=4)
            or any(type(v) is not int for v in loc.values())
            or type(frame) is not int or frame<0 or not isinstance(b,dict)
            or type(b.get('observation_frame')) is not int or b['observation_frame']!=frame):
        return review('opponent_review_observation_unverified')
    if b.get('active') is False and type(b.get('raw')) is int and b['raw']==0 and b.get('kind')=='none':
        return None
    if b.get('active') is not True or type(b.get('raw')) is not int or b['raw']!=2 or b.get('kind')!='trainer':
        return review('opponent_review_trainer_unverified')
    species=b.get('opponent_species')
    if type(species) is not str or species not in {'GROWLITHE','PONYTA','RAPIDASH','ARCANINE'}:
        return review('opponent_review_identity_unverified')
    if species=='ARCANINE':return review('blaine_arcanine_medicine_calibration')
    return None
