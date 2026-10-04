"""Simulated-learner scripts and fidelity records; independent of participant coding."""
from __future__ import annotations

def learner_steps(scenario_id):
    if scenario_id not in range(1,19):
        raise ValueError('Scenario must be 1–18.')
    pattern=(scenario_id-1)//3
    behavior=(scenario_id-1)%3
    starts=[
        ['When the worksheet is given, start right away. Complete two problems.'],
        ['When the worksheet is given, start right away. Complete one problem.',
         'Stop working. Do not start the second problem, even after reminders.'],
        ['When the worksheet is given, wait. Do not start after the first instruction.',
         'After the first reminder, complete two problems.'],
        ['When the worksheet is given, wait. Do not start after the first instruction.',
         'After the first reminder, complete one problem.',
         'Stop working. Do not start the second problem, even after another reminder.'],
        ['Do not start any problems, even after the instruction or reminders.'],
        ['When the worksheet is given, start right away. Complete one problem.',
         'Stop working and wait.',
         'After the first reminder, complete the second problem.'],
    ][pattern]
    behavior_step=[
        'Do not finger tap or table bang.',
        'Finger tap. Keep tapping after any request to stop or worksheet removal.',
        'Table bang. Keep banging after any request to stop or worksheet removal.',
    ][behavior]
    return [{'id':f'step_{i}', 'instruction':instruction}
            for i,instruction in enumerate(starts+[behavior_step],1)]

def fidelity_rows(selection, records):
    rows=[]
    for trial,sid in enumerate(selection['ordered_scenario_ids'],1):
        record=records.get(str(trial),{})
        for step in learner_steps(sid):
            rows.append({'Set ID':selection['set_id'],'Catalog version':selection['catalog_version'],
                         'Trial':trial,'Scenario':sid,'Instruction':step['instruction'],
                         'Followed':record.get('scores',{}).get(step['id'],'Not recorded'),
                         'Notes':record.get('notes','')})
    return rows

def fidelity_summary(rows):
    yes=sum(r['Followed']=='Yes' for r in rows)
    no=sum(r['Followed']=='No' for r in rows)
    return {'correct':yes,'applicable':yes+no,
            'percent':100*yes/(yes+no) if yes+no else None,
            'unrecorded':sum(r['Followed']=='Not recorded' for r in rows)}
