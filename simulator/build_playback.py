"""Prepare small, silent playback copies in a private draft release."""
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.parse
import urllib.request

from media import manifest, prepare_video

settings = manifest()
repository = settings['repository']
token = os.environ['GH_TOKEN']


def api(path, payload=None):
    request = urllib.request.Request('https://api.github.com/repos/' + repository + path,
        data=None if payload is None else json.dumps(payload).encode(), headers={
            'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
            'Content-Type': 'application/json', 'User-Agent': 'DRA-playback-builder'})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def release():
    existing = next((r for r in api('/releases?per_page=100') if r['tag_name']==settings['playback_tag']), None)
    return existing or api('/releases', {'tag_name':settings['playback_tag'],
        'target_commitish':'simulator-playback-mockup', 'draft':True,
        'name':'DRA mockup playback copies',
        'body':'Silent compressed copies of the verified originals for the session mockup. Keep this release as a draft. Original recordings remain in the source archive.'})


if sys.argv[1]=='init':
    r=release()
    with open(os.environ['GITHUB_OUTPUT'],'a') as output:
        output.write('release_id='+str(r['id'])+'\n')
        output.write('matrix='+json.dumps({'recording':[r['id'] for r in settings['recordings']]},separators=(',',':'))+'\n')
else:
    recording=next(r for r in settings['recordings'] if r['id']==sys.argv[2])
    release_id=int(os.environ['PLAYBACK_RELEASE_ID'])
    name='preview-v2-'+recording['sha256']+'.mp4'
    if any(a['name']==name for a in api(f'/releases/{release_id}/assets?per_page=100')):
        print('Playback copy already exists:',recording['id'])
        raise SystemExit()
    os.environ['DRA_BUILD_ORIGINAL']='1'
    target=prepare_video(recording,token)
    data=target.read_bytes()
    url=f'https://uploads.github.com/repos/{repository}/releases/{release_id}/assets?name='+urllib.parse.quote(name)
    request=urllib.request.Request(url,data=data,headers={'Authorization':'Bearer '+token,
        'Content-Type':'video/mp4','User-Agent':'DRA-playback-builder'},method='POST')
    with urllib.request.urlopen(request,timeout=180) as response:
        result=json.load(response)
    assert result['size']==len(data)
    if result.get('digest'):
        assert result['digest']=='sha256:'+hashlib.sha256(data).hexdigest()
    print('Prepared and uploaded:',recording['id'],len(data),'bytes')
