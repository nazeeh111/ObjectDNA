/** Derive a small README preview from the actual recorded workbench. Requires FFmpeg. */
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const assets=path.join(root,'docs/assets');
const output=path.join(assets,'workbench-demo.gif');
const pending=path.join(assets,'workbench-demo.pending.gif');
const filter='fps=4,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=64:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle';
const result=spawnSync('ffmpeg',['-hide_banner','-loglevel','error','-y','-i',path.join(assets,'walkthrough.mp4'),'-t','12','-filter_complex',filter,'-loop','0',pending],{encoding:'utf8'});
if(result.status!==0)throw new Error(result.stderr||'FFmpeg unavailable. Install the free FFmpeg CLI to create a README preview.');
const fs=await import('node:fs/promises');await fs.rename(pending,output);console.log(output);
