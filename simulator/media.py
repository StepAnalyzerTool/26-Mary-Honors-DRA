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


def transcode(source: Path, target: Path):
    if not shutil.which('ffmpeg'):
        raise RuntimeError('FFmpeg is required. Install the root packages.txt dependency.')
    temporary = target.with_suffix('.working.mp4')
    try:
        subprocess.run([
            'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
            '-threads', '2', '-i', str(source), '-map', '0:v:0', '-an',
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
    target = cache / (profile['sha256'] + '.mp4')
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
        raise RuntimeError('Private video access is not configured. See the deployment instructions below.')
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
