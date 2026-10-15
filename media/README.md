# DRA video and audio files

## Upload original recordings here

Open [GitHub Releases](https://github.com/StepAnalyzerTool/26-Mary-Honors-DRA/releases) and edit the draft named **DRA source recordings** (tag: `dra-source-recordings-v1`). Its **Attach binaries** area is the upload destination for original .mov, .mp4, and audio recordings.

If the draft is not visible, sign in with an account that has repository write access. The [Prepare media archive workflow](https://github.com/StepAnalyzerTool/26-Mary-Honors-DRA/actions/workflows/prepare-media-archive.yml) creates it automatically when this setup is committed; it can also be run manually.

1. Open the draft and click Edit.
2. Drag original recordings into **Attach binaries by dropping them here or selecting them**. Keep the original filenames. Each file must be under 2 GiB.
3. Wait for every upload to finish, then click **Save draft**. Work in small batches if uploading several large videos.
4. Reopen the draft and confirm each filename and file size. Download a copy and open it to verify the recording before removing the local original.
5. Keep another verified copy in Dropbox, SharePoint, or an external drive before clearing the local files.

This repository is public. Draft releases are visible to people with repository write access. Publishing this release makes its files publicly downloadable. Leave it as a draft while collecting and checking footage. A draft's files are not yet suitable as public playback URLs for the future program.

Do not use the repository's **Add file > Upload files** button for these large originals. That uploads ordinary Git files and has a much smaller limit.

The workflow does not upload recordings, publish the draft, overwrite an existing release, or delete local files.

## Organization for the future simulator

| Location | Purpose |
| --- | --- |
| Draft release: DRA source recordings | Full original filming takes, with original filenames retained |
| `media/video/` | Downloaded, edited video segments for playback when the simulator is built |
| `media/audio/` | Downloaded spoken instruction, stop-statement, and optional praise clips |
| `media/source_recordings.json` | Index of the seven new Dropbox-linked recordings discussed in this chat; upload status starts unverified |
| Existing `video_inventory.json` at repository root | Earlier footage inventory; preserved separately |

The seven-recording index is not a complete inventory of all filmed or planned recordings. A Dropbox link or prior review is not evidence of a GitHub upload. Release asset IDs, sizes, SHA-256 checksums, and download URLs can be recorded after upload verification. Do not replace or delete an original with a new take under the same name; append `_take02`, `_take03`, etc.

The video and audio folders contain instructions now. They are reserved for later playback assets; no simulator, clip cuts, event tags, or scoring behavior is implemented by this setup. Large media are excluded from ordinary Git commits. We will choose how to distribute the smaller playback assets when editing is complete.

Different worksheets across trials are acceptable. When combining segments within a trial, preserve its worksheet and completed-answer state. Exact completion tags and edited playback transitions still need verification.
