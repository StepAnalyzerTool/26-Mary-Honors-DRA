"""Private source access and cached browser-compatible playback copies.

Original recordings never enter Git. Local sources take precedence; otherwise
the server fetches the exact draft-release asset with a read-only GitHub token.
The token is never sent to the component or a download.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import urllib.parse

ROOT = Path(__file__).resolve().parent


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, new_url):
        redirected = super().redirect_request(request, fp, code, msg, headers, new_url)
        if redirected is not None and urllib.parse.urlsplit(new_url).netloc != urllib.parse.urlsplit(request.full_url).netloc:
            redirected.remove_header('Authorization')
        return redirected


def manifest():
    return json.loads((ROOT / 'media.json').read_text())


def _json_get(url,token):
    request=urllib.request.Request(url,headers={'Authorization':'Bearer '+token,
        'Accept':'application/vnd.github+json','User-Agent':'DRA-session-mockup'})
    with urllib.request.urlopen(request,timeout=60) as response: return json.load(response)


def available_playback(token=''):
    """Use prepared private assets, without transcoding 18 originals per app request."""
    settings=manifest()
    cache=Path(os.environ.get('DRA_PLAYBACK_CACHE',str(Path(tempfile.gettempdir())/'dra-playback-v1')))
    cache.mkdir(parents=True,exist_ok=True);assets={}
    if token:
        try:
            releases=_json_get(f"https://api.github.com/repos/{settings['repository']}/releases?per_page=100",token)
            release=next((r for r in releases if r['tag_name']==settings['playback_tag']),None)
            if release: assets={a['name']:a for a in _json_get(release['assets_url']+'?per_page=100',token)}
        except urllib.error.HTTPError as exc: raise RuntimeError(f'The session videos could not be accessed (HTTP {exc.code}).') from None
        except urllib.error.URLError: raise RuntimeError('The session videos could not be reached. Please retry.') from None
    available=[]
    for recording in settings['recordings']:
        target=cache/(recording['sha256']+'-audio-v3.mp4');asset=assets.get('preview-v3-audio-'+recording['sha256']+'-audio-v3.mp4')
        if (not target.exists() or target.stat().st_size<=1000) and asset:
            request=urllib.request.Request(asset['url'],headers={'Authorization':'Bearer '+token,
                'Accept':'application/octet-stream','User-Agent':'DRA-session-mockup'})
            temporary=target.with_suffix('.download')
            try:
                digest=hashlib.sha256()
                with urllib.request.build_opener(_SafeRedirect()).open(request,timeout=120) as response,temporary.open('wb') as output:
                    while block:=response.read(1024*1024): digest.update(block);output.write(block)
                if temporary.stat().st_size!=asset['size'] or (asset.get('digest') and asset['digest']!='sha256:'+digest.hexdigest()):
                    raise RuntimeError('A session video failed verification. Please retry.')
                temporary.replace(target)
            except urllib.error.URLError: raise RuntimeError('A session video could not be downloaded. Please retry.') from None
            finally: temporary.unlink(missing_ok=True)
        if target.exists() and target.stat().st_size>1000: available.append((recording,target))
    return available


def static_playback(available):
    """Copy compressed assets into Streamlit's configured static directory."""
    destination=ROOT/'static'/'dra-playback';destination.mkdir(parents=True,exist_ok=True);urls={}
    for recording,source in available:
        target=destination/source.name
        if not target.exists() or target.stat().st_size!=source.stat().st_size: shutil.copy2(source,target)
        urls[recording['id']]='/app/static/dra-playback/'+target.name
    return urls


def transcode(source: Path, target: Path):
    if not shutil.which('ffmpeg'):
        raise RuntimeError('FFmpeg is required. Install the root packages.txt dependency.')
    temporary = target.with_suffix('.working.mp4')
    try:
        subprocess.run([
            'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
            '-threads', '2', '-i', str(source), '-map', '0:v:0', '-map', '0:a:0?',
            '-c:a', 'aac', '-b:a', '128k',
            '-vf', 'scale=960:-2', '-filter_threads', '1', '-r', '30',
            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '26',
            '-threads', '2', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
            str(temporary)], check=True, timeout=900, capture_output=True)
        temporary.replace(target)
    except (subprocess.SubprocessError, OSError) as exc:
        temporary.unlink(missing_ok=True)
        raise RuntimeError('Could not prepare the video playback copy.') from exc


def prepare_video(profile: dict, token: str = '') -> Path:
    cache = Path(os.environ.get('DRA_PLAYBACK_CACHE', str(Path(tempfile.gettempdir()) / 'dra-playback-v1')))
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / (profile['sha256'] + '-audio-v3.mp4')
    if target.exists() and target.stat().st_size > 1000:
        return target
    local = os.environ.get('DRA_SOURCE_DIR', '')
    source = Path(local) / profile['filename'] if local else None
    if source is not None and source.is_file():
        if source.stat().st_size != profile['source_bytes']:
            raise RuntimeError('The local source size does not match the verified recording.')
        transcode(source, target)
        return target
    if not token:
        raise RuntimeError('The session videos are not available yet.')
    settings = manifest()
    url = f"https://api.github.com/repos/{settings['repository']}/releases/assets/{profile['asset_id']}"
    request = urllib.request.Request(url, headers={
        'Authorization': 'Bearer ' + token, 'Accept': 'application/octet-stream',
        'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'Mary-DRA-playback-mockup'})
    source = cache / (profile['id'] + '.download.mov')
    try:
        digest = hashlib.sha256()
        with urllib.request.build_opener(_SafeRedirect()).open(request, timeout=120) as response, source.open('wb') as output:
            while block := response.read(4 * 1024 * 1024):
                digest.update(block)
                output.write(block)
        if source.stat().st_size != profile['source_bytes'] or digest.hexdigest() != profile['sha256']:
            raise RuntimeError('The recording did not match its verified size and checksum.')
        transcode(source, target)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'GitHub could not supply the private recording (HTTP {exc.code}). Check the app token’s repository access.') from None
    except urllib.error.URLError:
        raise RuntimeError('The recording could not be downloaded. Please retry.') from None
    finally:
        source.unlink(missing_ok=True)
    return target
