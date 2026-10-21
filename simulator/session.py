"""Fixed catalogue selection and footage assignment for the mockup session."""
import random
import uuid
from dra import load_catalog, select_session

BEHAVIORS={'No tapping or banging':'none','Finger tapping':'tapping','Table banging':'banging'}
FAMILIES=('together','one','together','one','zero','pause')


def make_session(count, participant, session_id, recordings, set_id=None):
    if isinstance(count,bool) or not isinstance(count,int) or not 1<=count<=10:
        raise ValueError('Choose between 1 and 10 trials.')
    catalog=load_catalog();selected=select_session(catalog,set_id)
    scenarios={s['scenario_id']:s for s in catalog['scenarios']}
    rng=random.SystemRandom();plan=[]
    for number,sid in enumerate(selected['ordered_scenario_ids'][:count],1):
        scenario=scenarios[sid];group=(sid-1)//3;behavior=BEHAVIORS[scenario['behavior']]
        candidates=[r for r in recordings if r['behavior']==behavior and r['family']==FAMILIES[group]]
        if not candidates:
            needed=2 if scenario['completed'] else 1 if group in (1,3) else 0
            candidates=[r for r in recordings if r['behavior']==behavior and r['capacity']>=needed]
        if not candidates: raise ValueError('A required learner behavior has no available footage yet.')
        recording=rng.choice(candidates)
        plan.append({**scenario,'trial':number,'group':group,'recording_id':recording['id'],
            'footage_adapted':recording['family']!=FAMILIES[group]})
    return {**selected,'id':str(uuid.uuid4()),'mode':'video_mockup','participant_id':participant,
        'session_id':session_id,'trial_count':count,'planned_scenario_ids':selected['ordered_scenario_ids'][:count],'plan':plan}
