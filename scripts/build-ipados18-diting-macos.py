#!/usr/bin/env python3
"""Build Diting Darwin 24 from this branch's scripts and pinned source feeds."""
import argparse, datetime, json, os, shutil, subprocess, sys, tomllib
from pathlib import Path
import tomllib
DEVICE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(DEVICE/'scripts'))
import diting_paths

def link(src,dst):
    src=src.resolve()
    if dst.is_symlink() and dst.resolve()==src:return
    if dst.exists() or dst.is_symlink():raise RuntimeError(f'Existing path differs: {dst}')
    dst.parent.mkdir(parents=True,exist_ok=True);dst.symlink_to(src,target_is_directory=src.is_dir())

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tree',type=Path,default=diting_paths.build_tree())
    p.add_argument('--developer-dir',type=Path,default=diting_paths.developer_dir())
    p.add_argument('--artifact-dir',type=Path,default=DEVICE/'out/ipados18/kernel')
    p.add_argument('--jobs',type=int,default=4)
    p.add_argument('--debug-symbols',action='store_true',help='also generate the large DWARF dSYM; ordinary kernel symbols are always retained')
    p.add_argument('--volume-layout',type=Path,default=diting_paths.volume_layout())
    p.add_argument('--prepare-only',action='store_true')
    p.add_argument('--config-path',type=Path,help='resolved format2 configuration')
    p.add_argument('--hardware-dtb',type=Path,help='compiled format2 SM8475/Diting hardware description')
    p.add_argument('--skip-image-verification',action='store_true',default=True)
    a=p.parse_args();tree=a.tree.resolve()
    tree.mkdir(parents=True,exist_ok=True)
    local=DEVICE/'local.toml'
    overrides=tomllib.loads(local.read_text()).get('source',[]) if local.exists() else []
    refs=[r for r in tomllib.loads((DEVICE/'feeds.toml').read_text())['source'] if r['kind']=='refer']
    for ref in refs:
        override=next((s for s in overrides if s.get('kind')=='refer' and s.get('name')==ref['name']),{})
        src=Path(override['local']).expanduser() if override.get('local') else DEVICE/'refer/ipados18'/ref['ref']
        if not src.is_absolute():src=DEVICE/src
        rev=subprocess.check_output(['git','rev-parse','HEAD'],cwd=src,text=True).strip()
        if rev!=ref['commit']:raise RuntimeError(f'Wrong source revision for {ref["name"]}')
        link(src,tree/'refer'/ref['name'])
    for name in ('drivers','kits','package'):link(DEVICE/name,tree/name)
    (tree/'scripts').mkdir(exist_ok=True)
    for name in ('build-firehose.sh','prepare-xnu-source.py'):
        shutil.copyfile(DEVICE/'scripts'/name,tree/'scripts'/name)
    shutil.copyfile(DEVICE/'scripts/build-xnu-ipados18.sh',tree/'scripts/build-xnu-ipados18.sh')
    link(DEVICE/'patches/xnu-ipados18',tree/'patches/xnu')
    (tree/'build').mkdir(exist_ok=True);(tree/'.cache').mkdir(exist_ok=True)
    env={k:v for k,v in os.environ.items() if not k.startswith(('XNU_','UNIXNU_'))}
    env.update(DEVELOPER_DIR=str(a.developer_dir),JOBS=str(a.jobs),DITING_NATIVE_DRIVER_SOURCE=str(DEVICE),
        UNIXNU_IOS_TARGET='18.0',SCAN_BUILD='',DO_CTFMERGE='0',CTFINSERT='',CTFCONVERT='',CTFMERGE='',CTFDUMP='')
    if a.hardware_dtb:env['DITING_HARDWARE_DTB']=str(a.hardware_dtb.resolve())
    tools=tree/'.tools';tools.mkdir(exist_ok=True)
    link(Path(sys.executable),tools/'python3')
    env['PATH']=diting_paths.path_with(tools, *(['/opt/local/bin','/opt/local/sbin'] if diting_paths.macports() else []))
    gh=shutil.which('gh',path=env['PATH'])
    if gh:
        credential=subprocess.run([gh,'auth','token'],capture_output=True,text=True)
        if credential.returncode==0:env['GH_TOKEN']=credential.stdout.strip()
    prefixes={'xnu':'XNU','libplatform':'LIBPLATFORM','libdispatch':'LIBDISPATCH','AvailabilityVersions':'AVAILABILITYVERSIONS'}
    for ref in refs:
        # Header-only refer pins (IOStorageFamily) are checked out and
        # revision-checked above. They are not XNU build env vars.
        prefix=prefixes.get(ref['name'])
        if not prefix:
            continue
        env['UNIXNU_'+prefix+'_TAG']=ref['ref'];env['UNIXNU_'+prefix+'_COMMIT']=ref['commit']
        if ref['name']=='xnu':
            for key in ('darwin','version','driverkit_tag','trustcache_tag'):env['UNIXNU_'+('XNU_'+key if key in ('darwin','version') else key).upper()]=ref[key]
    if a.config_path:
        config_path=a.config_path
    else:
        # The board names its defconfig in [kernel] defconfig; do not assume the
        # shipping one (the CI runs the reduced configuration).
        board=tomllib.loads((DEVICE/'board.toml').read_text())
        config_path=DEVICE/'configs'/(board.get('kernel',{}).get('defconfig') or 'diting_ipados18_defconfig')
    resolved=config_path.read_text()
    print(f"recipe config: {config_path}", flush=True)
    for probe in ('CONFIG_XNU_DITING_WIFI=', 'CONFIG_XNU_DITING_BACKLIGHT=', 'CONFIG_XNU_DITING_ADRENO_PLATFORM='):
        hit=[l for l in resolved.splitlines() if l.startswith(probe)]
        print(f"  {probe}{hit[0].split(String:=chr(61),1)[1] if hit else '<absent>'}".replace('String:',''), flush=True)
    for line in resolved.splitlines():
        if line.startswith('CONFIG_XNU_'):
            key,value=line.removeprefix('CONFIG_').split('=',1);env[key]={'y':'1','n':'0'}.get(value,value.strip('"'))
    # Fail at the configuration boundary, before building an archive whose
    # startup entry or platform helper would otherwise be omitted at link.
    dependencies = {
        # Wi-Fi itself needs the shared SMMU lease, which DitingPlatformResources provides;
        # that object is built by the full power archive or by --resources-only when
        # NATIVE_UFS is set, so the power/audio archive is not required to build it.
        'XNU_DITING_WIFI': ('XNU_ARMCPU', 'XNU_NATIVE_UFS'),
        'XNU_DITING_BACKLIGHT': ('XNU_DITING_POWER',),
        'XNU_DITING_POWER': ('XNU_ARM_DT_PLATFORM', 'XNU_ARMCPU'),
        'XNU_ARM_DT_PLATFORM': ('XNU_ARMCPU',),
    }
    for feature, required in dependencies.items():
        if env.get(feature, '0') == '1':
            missing = [key for key in required if env.get(key, '0') != '1']
            if missing: raise SystemExit(feature + ' requires ' + ', '.join(missing))
    if env.get('XNU_SOURCE_CORECRYPTO14', '0') != '0':
        raise SystemExit('22H374 requires its matching prelinked crypto, not the Darwin22 archive recipe')
    # Only the board-specific archive has a matching 22H374 binding profile.
    # Other legacy display/AIR archives remain excluded.
    legacy_gpu = ('XNU_NATIVE_ADRENO',
                  'XNU_NATIVE_OFFLINE_GPU', 'XNU_NATIVE_AIR_INIT',
                  'XNU_NATIVE_MOBILE_DISPLAY', 'XNU_NATIVE_LEGACY_DISPLAY')
    enabled_gpu = [key for key in legacy_gpu if env.get(key, '0') != '0']
    if enabled_gpu:
        raise SystemExit('22H374 GPU ABI adaptation required before enabling: ' + ', '.join(enabled_gpu))
    layout=json.loads(a.volume_layout.read_text())
    env['XNU_BUILD_DSYM']='1' if a.debug_symbols else '0'
    env['XNU_OWNER_ROOT_VOLUME_UUID']=layout['os']['uuid']
    env['XNU_OWNER_DATA_VOLUME_UUID']=layout['data']['uuid']
    env['XNU_OWNER_CACHE_VOLUME_UUID']=layout['systemos']['uuid']
    settings={k:v for k,v in env.items() if k.startswith(('XNU_','UNIXNU_'))}
    report=dict(profile='Diting-iPadOS18-22H374-Darwin24',tree=str(tree),settings=settings,
        debug_symbols_generated=a.debug_symbols,reference_commits={r['name']:r['commit'] for r in refs},image_verification='skipped by request',build_complete=False)
    if a.hardware_dtb:
        report['hardware_dtb']=str(a.hardware_dtb.resolve())
        report['configuration']=str(config_path.resolve())
        report['schema_version']=2
    result=tree.parent/'DITING_BUILD_RESULT.json';result.write_text(json.dumps(report,indent=2)+'\n')
    if a.prepare_only:print(tree);return
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');log=tree.parent/f'build-{stamp}.log'
    print('Building Darwin 24; log:',log,flush=True)
    with log.open('w') as f:r=subprocess.run(['bash','scripts/build-xnu-ipados18.sh'],cwd=tree,env=env,stdout=f,stderr=subprocess.STDOUT)
    report.update(returncode=r.returncode,log=str(log));result.write_text(json.dumps(report,indent=2)+'\n')
    if r.returncode:raise SystemExit(f'Build failed; log retained: {log}')
    kernel=tree/'build/xnu/ios-obj/DEVELOPMENT_ARM64_DITING/mach.development.diting'
    a.artifact_dir.mkdir(parents=True,exist_ok=True);shutil.copyfile(kernel,a.artifact_dir/kernel.name)
    report.update(build_complete=True,kernel=dict(path=str(a.artifact_dir/kernel.name),bytes=kernel.stat().st_size))
    for dest in (result,a.artifact_dir/'DITING_BUILD_RESULT.json'):dest.write_text(json.dumps(report,indent=2)+'\n')
    print(a.artifact_dir/kernel.name)
if __name__=='__main__':main()
