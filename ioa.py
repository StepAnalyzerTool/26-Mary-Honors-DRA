"""Exact-score interobserver agreement for independent DRA coding records."""
from io import BytesIO
import pandas as pd
from dra import restore_session
from scoring import TIMED_COMPONENTS, BEHAVIOR_COMPONENTS, trial_records, MISSING, EXCLUDED

NOT_OBSERVED='Not observed'

def compare_records(primary_data,secondary_data):
 if primary_data==secondary_data:
  raise ValueError('Upload two independently coded records, not the same file twice.')
 primary=restore_session(primary_data);secondary=restore_session(secondary_data)
 for key,label in [('participant_id','participant ID'),('session_number','session number'),('date','session date')]:
  first=str(primary['session'].get(key,'')).strip()
  second=str(secondary['session'].get(key,'')).strip()
  if not first or first!=second: raise ValueError(f'The records must have the same nonblank {label}.')
 components=[(c['key'],c['label'],m) for c in TIMED_COMPONENTS for m in ('Occurrence','Timing')]
 components += [(c['key'],c['label'],'Behavior') for c in BEHAVIOR_COMPONENTS]
 maps=[]
 for payload in (primary,secondary):
  maps.append({(r['trial'],r['component'],r['measure']):r['result'] for t in payload['trials'] for r in trial_records(t)})
 rows=[]
 for trial in range(1,11):
  for key,label,measure in components:
   p=maps[0].get((trial,key,measure),NOT_OBSERVED)
   s=maps[1].get((trial,key,measure),NOT_OBSERVED)
   if MISSING in (p,s): outcome='Missing'
   elif p in EXCLUDED|{NOT_OBSERVED} and s in EXCLUDED|{NOT_OBSERVED}: outcome='Excluded'
   else: outcome='Agreement' if p==s else 'Disagreement'
   rows.append({'Trial':trial,'Step':label,'Measure':measure,'Primary score':p,'Secondary score':s,'Comparison':outcome})
 def totals(items):
  agreed=sum(r['Comparison']=='Agreement' for r in items)
  compared=sum(r['Comparison'] in ('Agreement','Disagreement') for r in items)
  return {'Agreements':agreed,'Compared items':compared,
          'Agreement (%)':100*agreed/compared if compared else None,
          'Missing items':sum(r['Comparison']=='Missing' for r in items),
          'Excluded items':sum(r['Comparison']=='Excluded' for r in items)}
 grouped=[]
 for measure in ('Occurrence','Timing','Behavior'):
  grouped.append({'Summary':'All '+measure.lower()+' scores',**totals([r for r in rows if r['Measure']==measure])})
 for key,label,measure in components:
  grouped.append({'Summary':label+' — '+measure,**totals([r for r in rows if r['Step']==label and r['Measure']==measure])})
 return {'primary':primary['session'],'secondary':secondary['session'],'overall':totals(rows),'summary':grouped,'details':rows}

def ioa_workbook(result):
 output=BytesIO()
 metadata={'Participant ID':result['primary']['participant_id'],'Session number':result['primary']['session_number'],
           'Date':result['primary']['date'],'Primary coder':result['primary'].get('data_collector',''),
           'Secondary coder':result['secondary'].get('data_collector','')}
 with pd.ExcelWriter(output,engine='openpyxl') as writer:
  pd.DataFrame([{**metadata,**result['overall']}]).to_excel(writer,sheet_name='IOA Summary',index=False)
  pd.DataFrame(result['summary']).to_excel(writer,sheet_name='Step Agreement',index=False)
  pd.DataFrame(result['details']).to_excel(writer,sheet_name='Trial Comparisons',index=False)
  from openpyxl.styles import Alignment
  for sheet in writer.book.worksheets:
   sheet.freeze_panes='A2';sheet.auto_filter.ref=sheet.dimensions
   for column in sheet.columns:
    sheet.column_dimensions[column[0].column_letter].width=min(55,max(18,max(len(str(c.value or '')) for c in column)+2))
    for cell in column:
     cell.alignment=Alignment(wrap_text=True,vertical='top')
     if isinstance(cell.value,str) and cell.value.startswith('='): cell.data_type='s'
 return output.getvalue()
