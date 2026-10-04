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

def fidelity_filename(leader):
    import re
    def identifier(value, prefix):
        value=str(value or '').strip()
        if value[:1].upper()==prefix: value=value[1:]
        return re.sub(r'[^A-Za-z0-9_.-]+','_',value) or 'unknown'
    return f"P{identifier(leader.get('participant_id'),'P')}_S{identifier(leader.get('session_id'),'S')}_Simulated_Learner_Fidelity"

def fidelity_workbook(selection, leader, records):
    from io import BytesIO
    import pandas as pd
    from openpyxl.styles import Alignment, Font
    rows=fidelity_rows(selection,records)
    summary=fidelity_summary(rows)
    fields=[
        ('Participant ID',leader.get('participant_id','')),
        ('Session ID',leader.get('session_id','')),
        ('Session leader',leader.get('session_leader','')),
        ('Simulated Learner',leader.get('simulated_learner','')),
        ('Set ID',selection['set_id']),
        ('Catalog version',selection['catalog_version']),
        ('Selection time',selection['selected_at']),
        ('Exact scenario order',', '.join(map(str,selection['ordered_scenario_ids']))),
        ('Instructions followed (Yes)',summary['correct']),
        ('Learner errors (No)',summary['applicable']-summary['correct']),
        ('Recorded applicable items (Yes + No)',summary['applicable']),
        ('Not observed items (excluded)',sum(r['Followed']=='Not observed' for r in rows)),
        ('Items not yet recorded',summary['unrecorded']),
        ('Simulated Learner fidelity',summary['percent']/100 if summary['percent'] is not None else None),
        ('Calculation','Yes / (Yes + No). Not observed and not recorded items are excluded.'),
    ]
    output=BytesIO()
    with pd.ExcelWriter(output,engine='openpyxl') as writer:
        pd.DataFrame(fields,columns=['Field','Value']).to_excel(writer,sheet_name='Session Summary',index=False)
        pd.DataFrame(rows).to_excel(writer,sheet_name='Trial Checklist',index=False)
        for sheet in writer.book.worksheets:
            sheet.freeze_panes='A2'
            sheet.auto_filter.ref=sheet.dimensions
            for cell in sheet[1]: cell.font=Font(bold=True)
            for column in sheet.columns:
                sheet.column_dimensions[column[0].column_letter].width=min(80,max(18,max(len(str(c.value or '')) for c in column)+2))
                for cell in column:
                    cell.alignment=Alignment(vertical='top',wrap_text=True)
                    if isinstance(cell.value,str) and cell.value.startswith('='):
                        cell.data_type='s'
        writer.book['Session Summary']['B15'].number_format='0.0%'
    return output.getvalue()
